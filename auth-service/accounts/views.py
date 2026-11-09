"""The auth service's three endpoints. Function views, like the main app's (ADR 0026)."""

import hashlib
import logging
from typing import TYPE_CHECKING

from django.contrib.auth import authenticate
from django.db import DatabaseError, connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import cache_control, never_cache
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_GET
from rest_framework import serializers
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.models import User
from accounts.roles import scopes_for
from accounts.throttles import LoginIpThrottle, LoginUsernameThrottle
from accounts.tokens import SigningKeyError, mint_access_token, signing_key

if TYPE_CHECKING:
    from rest_framework.request import Request

logger = logging.getLogger(__name__)


class LoginSerializer(serializers.Serializer[dict[str, str]]):
    # Long enough for any email address (RFC 5321 caps a path at 254).
    username = serializers.CharField(max_length=254)
    # WordPress refuses passwords over 4096 characters; so do we. Not
    # trimmed: spaces are part of a password.
    password = serializers.CharField(max_length=4096, trim_whitespace=False)


# One body for every reason a login fails (unknown user, wrong password,
# inactive account, no usable password), so the response reveals nothing.
_INVALID_CREDENTIALS = {"error": "invalid_credentials"}


# no-store: RFC 6749 §5.1 forbids caching any response that carries a token.
@never_cache
@sensitive_variables("password")
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LoginIpThrottle, LoginUsernameThrottle])
def token(request: Request) -> Response:
    """Exchange a username (or email) and password for an access token.

    A first-party credential exchange for our own CLI, deliberately not the
    OAuth password grant, which RFC 9700 forbids (ADR 0033).
    """
    body = LoginSerializer(data=request.data)
    body.is_valid(raise_exception=True)
    username = body.validated_data["username"]
    password = body.validated_data["password"]
    user = authenticate(request._request, username=username, password=password)
    if not isinstance(user, User):
        # Never log the input itself: people type passwords into the
        # username box. A hash still links repeated attempts.
        logger.info(
            "login failed ip=%s username_sha256=%s",
            request.META.get("REMOTE_ADDR"),
            hashlib.sha256(username.strip().casefold().encode()).hexdigest()[:16],
        )
        return Response(_INVALID_CREDENTIALS, status=401)
    access = mint_access_token(user.external_id, scopes_for(user))
    logger.info(
        "login ok sub=%s jti=%s ip=%s",
        user.external_id,
        access.jti,
        request.META.get("REMOTE_ADDR"),
    )
    return Response(
        {
            "access_token": access.token,
            "token_type": "Bearer",
            "expires_in": access.expires_in,
            "scope": access.scope,
        }
    )


# Verifiers cache keys for 300 s (ADR 0016); a proxy in front may do the same.
@require_GET
@cache_control(public=True, max_age=300)
def jwks(request: HttpRequest) -> JsonResponse:
    """The public signing key(s), as an RFC 7517 JWK Set."""
    return JsonResponse(
        {"keys": [dict(signing_key().public_jwk)]},
        content_type="application/jwk-set+json",
    )


@never_cache
@require_GET
def healthz(request: HttpRequest) -> JsonResponse:
    """Ready only when the database answers and the signing key loads."""
    try:
        connection.ensure_connection()
        signing_key()
    except DatabaseError, SigningKeyError:
        logger.exception("health check failed")
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
