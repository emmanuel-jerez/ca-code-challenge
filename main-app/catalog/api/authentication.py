"""Bearer tokens for the API, verified by the shared library (ADRs 0016, 0034)."""

from functools import cache

from brandreviews_authz import JwksClientKeyProvider, TokenVerifier
from brandreviews_authz.drf import BearerAuthentication as LibraryBearerAuthentication
from django.conf import settings


@cache
def token_verifier() -> TokenVerifier:
    """One verifier per process, so its JWKS cache outlives a request.

    Built on first use, not at import: settings are read once they're final,
    and a process that serves no protected request never fetches keys.
    """
    return TokenVerifier(
        JwksClientKeyProvider(settings.AUTH_JWKS_URL),
        issuer=settings.JWT_ISSUER,
        audience=settings.JWT_AUDIENCE,
    )


class BearerAuthentication(LibraryBearerAuthentication):
    """The library's class, given this app's verifier. DRF builds it with no arguments."""

    def get_verifier(self) -> TokenVerifier:
        return token_verifier()
