"""The signing key, its public JWK, and access-token minting.

Only this service signs; the shared library only verifies (AGENTS.md).
Token format and claims: ADR 0016 and docs/research/pillar-5-auth-service.md §7.
The claim set, the token profile and the JWK format come from the shared
library, which the main app verifies with; signing stays here (ADR 0034).
"""

import secrets
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

import jwt
from brandreviews_authz import AccessClaims, public_jwk
from brandreviews_authz.profile import ALGORITHM, TOKEN_TYPE
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
        # The library builds the JWK and its kid, so what we publish is
        # exactly what the main app's verifier parses.
        jwk = public_jwk(key.public_key())
        return cls(private_key=key, kid=jwk["kid"], public_jwk=jwk)


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
    claims = AccessClaims(
        subject=subject,
        client_id=settings.JWT_CLIENT_ID,
        scopes=frozenset(scopes),
        token_id=secrets.token_urlsafe(16),
        issued_at=issued_at,
        expires_at=issued_at + lifetime,
    )
    payload = claims.to_payload(issuer=settings.JWT_ISSUER, audience=settings.JWT_AUDIENCE)
    # Always name the algorithm: PyJWT signs HS256 when it's omitted.
    token = jwt.encode(
        payload, key.private_key, algorithm=ALGORITHM, headers={"typ": TOKEN_TYPE, "kid": key.kid}
    )
    return AccessToken(
        token=token, scope=str(payload["scope"]), expires_in=lifetime, jti=claims.token_id
    )
