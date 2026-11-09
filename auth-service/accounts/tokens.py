"""The signing key, its public JWK, and access-token minting.

Only this service signs; the shared library only verifies (AGENTS.md).
Token format and claims: ADR 0016 and docs/research/pillar-5-auth-service.md §7.
"""

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.conf import settings
from django.utils import timezone

if TYPE_CHECKING:
    import uuid
    from collections.abc import Mapping, Sequence
    from datetime import datetime
    from pathlib import Path


class SigningKeyError(Exception):
    """The signing key is missing, unreadable, or not an Ed25519 private key."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _jwk_thumbprint(x: str) -> str:
    """RFC 7638 thumbprint of an Ed25519 public key, used as its `kid`.

    For OKP keys the hash covers exactly crv, kty and x, in that order, as
    compact JSON (RFC 8037 §2). The result is always 43 base64url characters,
    which gives verifiers a cheap format check.
    """
    canonical = json.dumps(
        {"crv": "Ed25519", "kty": "OKP", "x": x}, separators=(",", ":"), sort_keys=True
    )
    return _b64url(hashlib.sha256(canonical.encode("ascii")).digest())


@dataclass(frozen=True, slots=True)
class SigningKey:
    private_key: Ed25519PrivateKey
    kid: str
    # What the JWKS publishes. Never contains the private part `d`.
    public_jwk: Mapping[str, str]

    @classmethod
    def from_pem(cls, pem: bytes) -> SigningKey:
        try:
            key = serialization.load_pem_private_key(pem, password=None)
        except ValueError, TypeError:
            # `from None`: nothing about the key's bytes goes into the error.
            raise SigningKeyError("the signing key is not an unencrypted PEM private key") from None
        if not isinstance(key, Ed25519PrivateKey):
            raise SigningKeyError("the signing key must be an Ed25519 private key")
        x = _b64url(
            key.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            )
        )
        kid = _jwk_thumbprint(x)
        return cls(
            private_key=key,
            kid=kid,
            # `alg` and `use` pin the key to one algorithm and purpose
            # (draft-ietf-oauth-rfc8725bis §3.1).
            public_jwk={
                "kty": "OKP",
                "crv": "Ed25519",
                "x": x,
                "kid": kid,
                "use": "sig",
                "alg": "EdDSA",
            },
        )


def signing_key() -> SigningKey:
    """The key from JWT_SIGNING_KEY_FILE, read once per process.

    A new key needs a restart; the rotation runbook is in ADR 0033.
    """
    return _load(settings.JWT_SIGNING_KEY_FILE)


@cache
def _load(path: Path) -> SigningKey:
    try:
        pem = path.read_bytes()
    except OSError as error:
        raise SigningKeyError(f"cannot read the signing key at {path}: {error.strerror}") from None
    return SigningKey.from_pem(pem)


@dataclass(frozen=True, slots=True)
class AccessToken:
    token: str
    scope: str
    expires_in: int
    jti: str


def mint_access_token(
    subject: uuid.UUID, scopes: Sequence[str], *, now: datetime | None = None
) -> AccessToken:
    """Sign an RFC 9068-style access token for `subject` with `scopes`.

    The token carries no username, email or role: clients can read its
    claims (RFC 9068 §6), and the main app must authorize by scope.
    """
    key = signing_key()
    issued_at = int((now or timezone.now()).timestamp())
    lifetime: int = settings.ACCESS_TOKEN_LIFETIME_SECONDS
    scope = " ".join(scopes)
    jti = secrets.token_urlsafe(16)
    claims = {
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "sub": str(subject),
        "client_id": settings.JWT_CLIENT_ID,
        "scope": scope,
        "iat": issued_at,
        "nbf": issued_at,
        "exp": issued_at + lifetime,
        "jti": jti,
    }
    # Always name the algorithm: PyJWT signs HS256 when it's omitted.
    token = jwt.encode(
        claims, key.private_key, algorithm="EdDSA", headers={"typ": "at+jwt", "kid": key.kid}
    )
    return AccessToken(token=token, scope=scope, expires_in=lifetime, jti=jti)
