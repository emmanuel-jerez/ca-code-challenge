"""PATCH /api/brands/<slug>/: editors change a brand's short description (ADR 0034).

Tokens are signed here with a throwaway key, the way the auth service signs
them; the verifier's keys are swapped for that key, so no auth service runs.
Signing in tests is fine; signing in the main app's code never is (AGENTS.md).
"""

import json
import logging
import time
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

import jwt
import pytest
from brandreviews_authz import (
    AccessClaims,
    KeySetUnavailable,
    StaticKeyProvider,
    TokenVerifier,
    public_jwk,
)
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog.models import Brand, Status

if TYPE_CHECKING:
    from django.test import Client
    from django.test.client import _MonkeyPatchedWSGIResponse as TestResponse
    from jwt import PyJWK

type MakeBrand = Callable[..., Brand]
type Mint = Callable[..., str]

EDITOR = uuid.UUID("6a0f8a0e-3f6e-4c1b-9b7e-2f1f5f0b9d11")
pytestmark = pytest.mark.django_db


@pytest.fixture
def mint(monkeypatch: pytest.MonkeyPatch) -> Mint:
    """Sign tokens with a fresh key that the main app's verifier trusts."""
    key = Ed25519PrivateKey.generate()
    kid = public_jwk(key.public_key())["kid"]
    verifier = TokenVerifier(
        StaticKeyProvider([key.public_key()]),
        issuer="http://auth-service:8000",
        audience="brands-api",
    )
    monkeypatch.setattr("catalog.api.authentication.token_verifier", lambda: verifier)

    def sign(*scopes: str) -> str:
        now = int(time.time())
        claims = AccessClaims(
            subject=EDITOR,
            client_id="brands-cli",
            scopes=frozenset(scopes),
            token_id="jti-1",
            issued_at=now,
            expires_at=now + 600,
        )
        payload = claims.to_payload(issuer="http://auth-service:8000", audience="brands-api")
        return jwt.encode(payload, key, algorithm="EdDSA", headers={"typ": "at+jwt", "kid": kid})

    return sign


def patch(client: Client, slug: str, body: object, token: str | None = None) -> TestResponse:
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    return client.patch(
        f"/api/brands/{slug}/",
        data=json.dumps(body),
        content_type="application/json",
        headers=headers,
    )


def listed_description(client: Client, slug: str) -> str:
    """What the public listing shows: the edit's observable effect."""
    results = client.get("/api/brands/").json()["results"]
    description: str = next(r["short_description"] for r in results if r["slug"] == slug)
    return description


def test_an_editor_changes_the_short_description(
    client: Client, make_brand: MakeBrand, mint: Mint
) -> None:
    make_brand(slug="acme", short_description="Old text.")

    response = patch(
        client, "acme", {"short_description": "  New text.  "}, mint("brands:read", "brands:write")
    )

    assert response.status_code == 200
    # Trimmed, like every other CharField DRF parses.
    assert response.json() == {"slug": "acme", "short_description": "New text."}
    assert listed_description(client, "acme") == "New text."


def test_each_edit_is_logged_with_who_made_it(
    client: Client, make_brand: MakeBrand, mint: Mint, caplog: pytest.LogCaptureFixture
) -> None:
    # Last write wins; the log is how an overwritten edit is traced (ADR 0034).
    make_brand(slug="acme")

    with caplog.at_level(logging.INFO, logger="catalog.api.views"):
        patch(client, "acme", {"short_description": "New."}, mint("brands:write"))

    assert f"brand edited slug=acme sub={EDITOR} jti=jti-1" in caplog.messages


def test_without_a_token_it_is_401_and_nothing_changes(
    client: Client, make_brand: MakeBrand
) -> None:
    make_brand(slug="acme", short_description="Old text.")

    response = patch(client, "acme", {"short_description": "Hacked."})

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == 'Bearer realm="api"'
    assert listed_description(client, "acme") == "Old text."


def test_an_invalid_token_is_401(client: Client, make_brand: MakeBrand, mint: Mint) -> None:
    make_brand(slug="acme")

    response = patch(client, "acme", {"short_description": "x"}, mint("brands:write") + "x")

    assert response.status_code == 401


def test_a_reader_is_403_and_nothing_changes(
    client: Client, make_brand: MakeBrand, mint: Mint
) -> None:
    make_brand(slug="acme", short_description="Old text.")

    response = patch(client, "acme", {"short_description": "Hacked."}, mint("brands:read"))

    assert response.status_code == 403
    assert listed_description(client, "acme") == "Old text."


class UnreachableKeys:
    def get(self, kid: str) -> PyJWK:
        raise KeySetUnavailable("connection refused")


def test_auth_keys_unavailable_is_503_not_401(
    client: Client, make_brand: MakeBrand, mint: Mint, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_brand(slug="acme")
    token = mint("brands:write")
    verifier = TokenVerifier(UnreachableKeys(), issuer="http://auth-service:8000", audience="x")
    monkeypatch.setattr("catalog.api.authentication.token_verifier", lambda: verifier)

    response = patch(client, "acme", {"short_description": "x"}, token)

    # A 401 would make the client discard a token that may be valid (ADR 0016).
    assert response.status_code == 503


def test_an_unknown_or_unpublished_brand_is_404_for_an_editor(
    client: Client, make_brand: MakeBrand, mint: Mint
) -> None:
    make_brand(slug="draft", status=Status.DRAFT)
    token = mint("brands:write")

    assert patch(client, "nope", {"short_description": "x"}, token).status_code == 404
    assert patch(client, "draft", {"short_description": "x"}, token).status_code == 404


def test_without_a_token_an_unknown_brand_is_401_not_404(client: Client) -> None:
    # Checking credentials first means the endpoint can't be used to probe slugs.
    assert patch(client, "nope", {"short_description": "x"}).status_code == 401


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({}, id="missing"),
        pytest.param({"short_description": ""}, id="empty"),
        pytest.param({"short_description": "   "}, id="blank"),
        pytest.param({"short_description": "x" * 301}, id="over 300 characters"),
        pytest.param({"short_description": 5}, id="not a string"),
        pytest.param({"short_description": None}, id="null"),
        # Strict: a client that thinks it can change the name must hear no.
        pytest.param({"short_description": "x", "name": "Renamed"}, id="another field"),
        pytest.param(["short_description"], id="not an object"),
    ],
)
def test_a_bad_body_is_400_and_nothing_changes(
    client: Client, make_brand: MakeBrand, mint: Mint, body: object
) -> None:
    make_brand(slug="acme", name="Acme", short_description="Old text.")

    response = patch(client, "acme", body, mint("brands:write"))

    assert response.status_code == 400
    assert listed_description(client, "acme") == "Old text."


def test_300_characters_is_allowed(client: Client, make_brand: MakeBrand, mint: Mint) -> None:
    make_brand(slug="acme")

    response = patch(client, "acme", {"short_description": "x" * 300}, mint("brands:write"))

    assert response.status_code == 200


def test_the_listing_stays_public_whatever_authorization_header_is_sent(
    client: Client, make_brand: MakeBrand
) -> None:
    # An expired or junk token must not turn the public listing into a 401.
    make_brand(slug="acme")

    response = client.get("/api/brands/", headers={"Authorization": "Bearer junk"})

    assert response.status_code == 200
