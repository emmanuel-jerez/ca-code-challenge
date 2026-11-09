"""POST /api/token/: credentials in, an EdDSA access token out (ADRs 0016, 0033)."""

import json
from typing import TYPE_CHECKING, Any

import jwt
import pytest

from conftest import PASSWORD

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.test import Client
    from django.test.client import _MonkeyPatchedWSGIResponse as TestResponse

    from accounts.models import User

pytestmark = pytest.mark.django_db


def login(client: Client, username: str, password: str = PASSWORD) -> TestResponse:
    return client.post(
        "/api/token/",
        data=json.dumps({"username": username, "password": password}),
        content_type="application/json",
    )


def verify(client: Client, token: str) -> dict[str, Any]:
    """Verify the way a resource server would: only from the published JWKS."""
    keys = jwt.PyJWKSet.from_dict(client.get("/.well-known/jwks.json").json())
    header = jwt.get_unverified_header(token)
    key = next(k for k in keys.keys if k.key_id == header["kid"])
    claims: dict[str, Any] = jwt.decode(
        token,
        key,
        algorithms=["EdDSA"],
        audience="brands-api",
        issuer="http://auth-service:8000",
        options={"require": ["iss", "aud", "sub", "exp", "iat", "nbf", "jti"]},
    )
    return claims


def test_an_editor_gets_a_token_carrying_its_scopes(
    client: Client, make_user: Callable[..., User]
) -> None:
    editor = make_user("editor")

    response = login(client, editor.username)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 600
    assert body["scope"] == "brands:read brands:write"
    claims = verify(client, body["access_token"])
    assert claims["sub"] == str(editor.external_id)
    assert claims["scope"] == "brands:read brands:write"
    assert claims["client_id"] == "brands-cli"
    assert claims["exp"] - claims["iat"] == 600
    assert jwt.get_unverified_header(body["access_token"])["typ"] == "at+jwt"


def test_login_accepts_email_or_username_in_any_case(
    client: Client, make_user: Callable[..., User]
) -> None:
    make_user("reader", username="Sarah_K", email="Sarah@Example.com")

    by_username = login(client, "sarah_k")
    by_email = login(client, "sarah@example.COM")

    assert by_username.status_code == 200
    assert by_email.status_code == 200
    assert by_email.json()["scope"] == "brands:read"


@pytest.mark.parametrize(
    "case",
    ["unknown user", "wrong password", "inactive", "unusable password"],
)
def test_every_failed_login_looks_the_same(
    client: Client, make_user: Callable[..., User], case: str
) -> None:
    user = make_user("editor")
    username, password = user.username, PASSWORD
    match case:
        case "unknown user":
            username = "nobody"
        case "wrong password":
            password = "not the password"
        case "inactive":
            user.is_active = False
            user.save()
        case "unusable password":
            user.set_unusable_password()
            user.save()

    response = login(client, username, password)

    assert response.status_code == 401
    assert response.json() == {"error": "invalid_credentials"}


def test_token_responses_are_never_cached(client: Client, make_user: Callable[..., User]) -> None:
    response = login(client, make_user().username)

    assert "no-store" in response["Cache-Control"]


def test_a_user_without_a_role_gets_a_token_that_grants_nothing(
    client: Client, make_user: Callable[..., User]
) -> None:
    response = login(client, make_user().username)

    assert response.status_code == 200
    assert verify(client, response.json()["access_token"])["scope"] == ""


def test_malformed_bodies_are_rejected_before_any_lookup(client: Client) -> None:
    response = client.post(
        "/api/token/", data=json.dumps({"username": "x"}), content_type="application/json"
    )

    assert response.status_code == 400
    assert "password" in response.json()


def test_guessing_one_account_is_throttled_across_addresses(
    client: Client, make_user: Callable[..., User]
) -> None:
    user = make_user()
    statuses = [
        client.post(
            "/api/token/",
            # Varying case and padding: they are all the same account.
            data=json.dumps({"username": spelling, "password": f"guess {n}"}),
            content_type="application/json",
            REMOTE_ADDR=f"203.0.113.{n}",
        ).status_code
        for n, spelling in enumerate(
            [user.username, user.username.upper(), f" {user.username} "] * 2
        )
    ]

    assert statuses == [401] * 5 + [429]


def test_one_address_is_throttled_across_accounts(client: Client) -> None:
    statuses = [login(client, f"user-{n}", "guess").status_code for n in range(21)]

    assert statuses == [401] * 20 + [429]


def test_a_spoofed_forwarded_for_header_does_not_reset_the_address_limit(
    client: Client,
) -> None:
    statuses = [
        client.post(
            "/api/token/",
            data=json.dumps({"username": f"user-{n}", "password": "guess"}),
            content_type="application/json",
            HTTP_X_FORWARDED_FOR=f"198.51.100.{n}",
        ).status_code
        for n in range(21)
    ]

    assert statuses[-1] == 429
