"""A fresh Ed25519 key per test and a mint() helper.

Signing lives here and in the auth service only, never in src/ (AGENTS.md).
"""

import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from brandreviews_authz import StaticKeyProvider, TokenVerifier, public_jwk

if TYPE_CHECKING:
    from collections.abc import Mapping

ISSUER = "http://auth-service:8000"
AUDIENCE = "brands-api"
SUBJECT = uuid.UUID("0b6f3c1e-5d0a-4c55-9d43-3c8c2f2d7a10")


@dataclass(frozen=True, slots=True)
class Issuer:
    """Plays the auth service: signs tokens with one Ed25519 key."""

    private_key: Ed25519PrivateKey
    kid: str

    def claims(self, **overrides: object) -> dict[str, object]:
        now = int(time.time())
        claims: dict[str, object] = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": str(SUBJECT),
            "client_id": "brands-cli",
            "scope": "brands:read brands:write",
            "iat": now,
            "nbf": now,
            "exp": now + 600,
            "jti": "test-jti",
        }
        claims.update(overrides)
        return {k: v for k, v in claims.items() if v is not None}

    def mint(self, **overrides: object) -> str:
        """A token as the auth service mints it; overrides replace claims (None drops one)."""
        return self.mint_with_headers({}, **overrides)

    def mint_with_headers(self, headers: Mapping[str, object], **overrides: object) -> str:
        all_headers: dict[str, object] = {"typ": "at+jwt", "kid": self.kid}
        all_headers.update(headers)
        return jwt.encode(
            self.claims(**overrides), self.private_key, algorithm="EdDSA", headers=all_headers
        )


@pytest.fixture
def issuer() -> Issuer:
    key = Ed25519PrivateKey.generate()
    return Issuer(private_key=key, kid=public_jwk(key.public_key())["kid"])


@pytest.fixture
def verifier(issuer: Issuer) -> TokenVerifier:
    keys = StaticKeyProvider([issuer.private_key.public_key()])
    return TokenVerifier(keys, issuer=ISSUER, audience=AUDIENCE)
