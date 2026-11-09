"""The DRF adapter, through a tiny view: 200, 401, 403 and 503 (ADR 0016).

Django is configured here with no project, no database and no
django.contrib.auth, the way the main app runs (docs/research/
pillar-6-shared-library.md §4).
"""

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        SECRET_KEY="test-only",
        INSTALLED_APPS=["rest_framework"],
        ROOT_URLCONF=[],
        REST_FRAMEWORK={
            "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
            # DRF's default AnonymousUser needs django.contrib.auth.
            "UNAUTHENTICATED_USER": None,
        },
    )
    django.setup()

from typing import TYPE_CHECKING  # noqa: E402 - Django must be configured first

import pytest  # noqa: E402
from rest_framework.decorators import (  # noqa: E402
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.response import Response  # noqa: E402
from rest_framework.test import APIRequestFactory  # noqa: E402

from brandreviews_authz import (  # noqa: E402
    KeySetUnavailable,
    TokenVerifier,
    is_claims,
    scopes,
)
from brandreviews_authz.drf import BearerAuthentication, require_scopes  # noqa: E402

from conftest import AUDIENCE, ISSUER, SUBJECT  # noqa: E402

if TYPE_CHECKING:
    from collections.abc import Callable

    from jwt import PyJWK
    from rest_framework.request import Request

    from conftest import Issuer

type View = Callable[..., Response]


def protected_view(verifier: TokenVerifier) -> View:
    """A view the way a service writes one: its own one-method subclass."""

    class ServiceAuthentication(BearerAuthentication):
        def get_verifier(self) -> TokenVerifier:
            return verifier

    @api_view(["PATCH"])
    @authentication_classes([ServiceAuthentication])
    @permission_classes([require_scopes(scopes.BRANDS_WRITE)])
    def view(request: Request) -> Response:
        assert is_claims(request.auth)
        return Response({"sub": str(request.auth.subject)})

    return view


def call(view: View, authorization: str | None = None) -> Response:
    headers = {} if authorization is None else {"HTTP_AUTHORIZATION": authorization}
    return view(APIRequestFactory().patch("/", {}, format="json", **headers))


def test_a_token_with_the_scope_gets_through(issuer: Issuer, verifier: TokenVerifier) -> None:
    response = call(protected_view(verifier), f"Bearer {issuer.mint()}")

    assert response.status_code == 200
    assert response.data == {"sub": str(SUBJECT)}


@pytest.mark.parametrize(
    "authorization",
    [
        pytest.param(None, id="no header"),
        pytest.param("Basic dXNlcjpwYXNz", id="another scheme"),
        pytest.param("Bearer", id="no token"),
        pytest.param("Bearer a b", id="two tokens"),
        pytest.param("Bearer not.a.token", id="bad token"),
    ],
)
def test_no_usable_token_is_401_with_a_bearer_challenge(
    verifier: TokenVerifier, authorization: str | None
) -> None:
    response = call(protected_view(verifier), authorization)

    assert response.status_code == 401
    # RFC 6750 §3: a 401 names the scheme to use. Without the header, DRF
    # would downgrade it to a 403.
    assert response["WWW-Authenticate"] == 'Bearer realm="api"'


def test_an_expired_token_is_401(issuer: Issuer, verifier: TokenVerifier) -> None:
    token = issuer.mint(iat=1_000, nbf=1_000, exp=1_600)

    assert call(protected_view(verifier), f"Bearer {token}").status_code == 401


def test_a_valid_token_without_the_scope_is_403(issuer: Issuer, verifier: TokenVerifier) -> None:
    # A reader: authenticated, not allowed.
    response = call(protected_view(verifier), f"Bearer {issuer.mint(scope='brands:read')}")

    assert response.status_code == 403
    assert response.data["detail"].code == "insufficient_scope"


class UnreachableKeys:
    def get(self, kid: str) -> PyJWK:
        raise KeySetUnavailable("connection refused")


def test_keys_that_cannot_be_fetched_are_503_not_401(issuer: Issuer) -> None:
    verifier = TokenVerifier(UnreachableKeys(), issuer=ISSUER, audience=AUDIENCE)

    response = call(protected_view(verifier), f"Bearer {issuer.mint()}")

    # A 401 would make the client discard a token that may be valid.
    assert response.status_code == 503


def test_a_permission_that_requires_nothing_is_refused() -> None:
    # It would let any valid token through, which is IsAuthenticated by another name.
    with pytest.raises(ValueError, match="at least one scope"):
        require_scopes()
