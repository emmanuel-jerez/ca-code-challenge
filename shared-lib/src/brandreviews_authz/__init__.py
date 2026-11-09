"""Verify the auth service's access tokens and check their scopes.

The core imports neither Django nor DRF; the DRF adapter is
brandreviews_authz.drf, behind the [drf] extra. Nothing here signs tokens:
only the auth service may mint them (AGENTS.md).
"""

from brandreviews_authz.claims import AccessClaims, is_claims
from brandreviews_authz.errors import (
    AuthzError,
    InsufficientScope,
    KeySetUnavailable,
    TokenRejected,
)
from brandreviews_authz.jwks import (
    JwksClientKeyProvider,
    KeyProvider,
    StaticKeyProvider,
    public_jwk,
)
from brandreviews_authz.verify import TokenVerifier

__all__ = [
    "AccessClaims",
    "AuthzError",
    "InsufficientScope",
    "JwksClientKeyProvider",
    "KeyProvider",
    "KeySetUnavailable",
    "StaticKeyProvider",
    "TokenRejected",
    "TokenVerifier",
    "is_claims",
    "public_jwk",
]
