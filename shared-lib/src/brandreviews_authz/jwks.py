"""Both sides of the JWKS: publishing a public key and getting keys back by kid.

public_jwk() is what the auth service serves at /.well-known/jwks.json, and
it decides the kid. The key providers are what the verifier looks keys up
in. Keeping them together means the publisher and the parser can't disagree
on what a key looks like.
"""

import base64
import hashlib
import json
from importlib.metadata import version
from typing import TYPE_CHECKING, Protocol

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from brandreviews_authz.errors import KeySetUnavailable, TokenRejected
from brandreviews_authz.profile import ALGORITHM

if TYPE_CHECKING:
    from collections.abc import Iterable


def public_jwk(key: Ed25519PublicKey) -> dict[str, str]:
    """The JWK for an Ed25519 public key, with its RFC 7638 thumbprint as kid.

    Takes a public key only, so the private part `d` can never be published:
    PyJWT's to_jwk() would include it if handed a private key.
    """
    # Checked at runtime too: a caller without a type checker could pass a
    # private key, and Ed25519PrivateKey isn't a subclass of the public one.
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("public_jwk() takes an Ed25519 public key")
    x = _b64url(key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    return {
        "kty": "OKP",
        "crv": "Ed25519",
        "x": x,
        "kid": _thumbprint(x),
        # alg and use pin the key to one algorithm and purpose
        # (draft-ietf-oauth-rfc8725bis §3.1).
        "use": "sig",
        "alg": ALGORITHM,
    }


class KeyProvider(Protocol):
    """Looks up a verification key by kid. The verifier depends only on this."""

    def get(self, kid: str) -> jwt.PyJWK:
        """The key, or TokenRejected (unknown kid) or KeySetUnavailable."""
        ...


class StaticKeyProvider:
    """Fixed keys: for tests, and for any caller that already holds the keys."""

    def __init__(self, keys: Iterable[Ed25519PublicKey]) -> None:
        jwks = (public_jwk(key) for key in keys)
        self._keys = {jwk["kid"]: jwt.PyJWK(jwk, algorithm=ALGORITHM) for jwk in jwks}

    def get(self, kid: str) -> jwt.PyJWK:
        try:
            return self._keys[kid]
        except KeyError:
            raise TokenRejected("unknown kid") from None


class JwksClientKeyProvider:
    """Keys from the auth service's JWKS, through PyJWT's PyJWKClient (ADR 0016).

    PyJWKClient caches the set for `lifespan` seconds and refetches at most
    once per `cooldown` seconds for an unknown kid. Past the lifespan, with
    the auth service down, every lookup fails: the main app fails closed
    (503) rather than trust keys the auth service may have withdrawn.
    """

    def __init__(
        self, url: str, *, lifespan: float = 300, cooldown: float = 30, timeout: float = 3
    ) -> None:
        # The URL comes from configuration only, never from a token header
        # (jku/x5u are ignored).
        self._client = jwt.PyJWKClient(
            url,
            # Off: its LRU has no expiry, so a withdrawn key would stay trusted.
            cache_keys=False,
            lifespan=lifespan,
            cooldown_duration=cooldown,
            timeout=timeout,
            # The auth service's logs then show which library versions are
            # still verifying, before a breaking release (ADR 0025).
            headers={"User-Agent": f"brandreviews-authz/{version('brandreviews-authz')}"},
        )

    def get(self, kid: str) -> jwt.PyJWK:
        # Load the set first: PyJWKClient raises the same PyJWKClientError
        # for a broken set as for an unknown kid. A failure here is ours or
        # the network's, never the token's.
        try:
            self._client.get_signing_keys()
        except (jwt.PyJWTError, ValueError, RecursionError) as error:
            # ValueError covers a non-JSON body; RecursionError a deeply
            # nested one (GHSA for PyJWT 2.15.0). PyJWKClient lets both escape.
            raise KeySetUnavailable(f"cannot load the JWKS: {error}") from error
        try:
            key = self._client.get_signing_key(kid)
        except jwt.PyJWKClientConnectionError as error:
            raise KeySetUnavailable(f"cannot refresh the JWKS: {error}") from error
        except jwt.PyJWKClientError:
            raise TokenRejected("unknown kid") from None
        except (jwt.PyJWTError, ValueError, RecursionError) as error:
            raise KeySetUnavailable(f"cannot refresh the JWKS: {error}") from error
        # PyJWKClient accepts any usable key: HMAC secrets, Ed448, and OKP
        # keys carrying a private `d`. Only an Ed25519 public key is ours.
        if not isinstance(key.key, Ed25519PublicKey):
            raise KeySetUnavailable(f"the JWKS key {kid!r} is not an Ed25519 public key")
        return key


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _thumbprint(x: str) -> str:
    """RFC 7638 thumbprint of an Ed25519 public key.

    For OKP keys the hash covers exactly crv, kty and x, in that order, as
    compact JSON (RFC 8037 §2). Always 43 base64url characters (profile.KID).
    """
    canonical = json.dumps(
        {"crv": "Ed25519", "kty": "OKP", "x": x}, separators=(",", ":"), sort_keys=True
    )
    return _b64url(hashlib.sha256(canonical.encode("ascii")).digest())
