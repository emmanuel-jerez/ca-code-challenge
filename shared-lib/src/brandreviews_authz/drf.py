"""The DRF adapter: bearer authentication and scope permissions (needs the [drf] extra).

The one module allowed to import Django and DRF (Ruff TID251 bans them
everywhere else), so the core stays usable and testable without either.
"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import APIException, AuthenticationFailed
from rest_framework.permissions import BasePermission

from brandreviews_authz.claims import AccessClaims, is_claims
from brandreviews_authz.errors import KeySetUnavailable, TokenRejected

if TYPE_CHECKING:
    import uuid

    from rest_framework.request import Request
    from rest_framework.views import APIView

    from brandreviews_authz.verify import TokenVerifier

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Principal:
    """request.user for a verified token: the auth service's user id, nothing more.

    The main app has no user table (AGENTS.md). DRF reads is_authenticated
    (IsAuthenticated) and pk (UserRateThrottle).
    """

    subject: uuid.UUID

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    @property
    def pk(self) -> str:
        return str(self.subject)


class KeysUnavailable(APIException):
    """503: the auth service's keys can't be fetched (ADR 0016)."""

    status_code = 503
    default_detail = "Token verification is temporarily unavailable. Retry later."
    default_code = "keys_unavailable"


class BearerAuthentication(BaseAuthentication):
    """Authorization: Bearer <access token>, verified locally (ADR 0016).

    DRF builds authentication classes with no arguments, so each service
    subclasses this and overrides get_verifier() to return a verifier built
    from its own settings. The library never reads settings.
    """

    def get_verifier(self) -> TokenVerifier:
        # Not @abstractmethod: BaseAuthentication isn't an ABC, so it
        # wouldn't be enforced.
        raise NotImplementedError("subclass BearerAuthentication and override get_verifier()")

    def authenticate(self, request: Request) -> tuple[Principal, AccessClaims] | None:
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != b"bearer":
            # No credentials tried: let public views stay public, and let a
            # protected one answer 401 (RFC 6750 §3.1).
            return None
        if len(parts) != 2:
            raise AuthenticationFailed("Malformed bearer token.", code="invalid_token")
        try:
            claims = self.get_verifier().verify(parts[1].decode("ascii"))
        except UnicodeDecodeError, TokenRejected:
            # The reason goes to the logs only; never the token itself.
            logger.info("bearer token rejected", exc_info=True)
            raise AuthenticationFailed("Invalid or expired token.", code="invalid_token") from None
        except KeySetUnavailable:
            logger.warning("cannot verify tokens: signing keys unavailable", exc_info=True)
            raise KeysUnavailable from None
        return Principal(claims.subject), claims

    def authenticate_header(self, request: Request) -> str:
        # Makes DRF answer 401 with a challenge rather than 403.
        return 'Bearer realm="api"'


def require_scopes(*required: str) -> type[BasePermission]:
    """A permission class that lets through only tokens holding every scope.

    Use as permission_classes=[require_scopes(scopes.BRANDS_WRITE)]. With no
    token, DRF answers 401; with a token lacking a scope, 403.
    """
    if not required:
        raise ValueError("require_scopes() needs at least one scope")

    class RequireScopes(BasePermission):
        message = "This token lacks a scope this action needs."
        code = "insufficient_scope"

        def has_permission(self, request: Request, view: APIView) -> bool:
            # request.auth is typed loosely by DRF; narrow it.
            return is_claims(request.auth) and request.auth.has_scopes(*required)

    RequireScopes.__qualname__ = f"require_scopes({', '.join(map(repr, required))})"
    return RequireScopes
