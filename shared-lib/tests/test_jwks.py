"""Publishing a key (public_jwk) and fetching keys back (JwksClientKeyProvider)."""

import base64
import time
from importlib.metadata import version
from typing import TYPE_CHECKING

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PrivateKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from brandreviews_authz import (
    JwksClientKeyProvider,
    KeySetUnavailable,
    TokenRejected,
    public_jwk,
)

from jwks_server import JwksServer

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

# RFC 8037 Appendix A.1 (the private key's d), A.2 (its public x) and A.3
# (that key's RFC 7638 thumbprint): an independent source for the expected values.
RFC8037_D = "nWGxne_9WmC6hEr0kuwsxERJxWl7MmkZcDusAxyuf2A"
RFC8037_X = "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo"
RFC8037_KID = "kPrK_qmxVWaYVA9wwBF6Iuo3vVzz7TxHCTwXBygrS4k"


def test_the_public_jwk_and_its_thumbprint_kid_match_the_rfc_8037_example() -> None:
    raw = base64.urlsafe_b64decode(RFC8037_D + "=")
    key = Ed25519PrivateKey.from_private_bytes(raw).public_key()

    assert public_jwk(key) == {
        "kty": "OKP",
        "crv": "Ed25519",
        "x": RFC8037_X,
        "kid": RFC8037_KID,
        "use": "sig",
        "alg": "EdDSA",
    }


def test_a_private_key_can_never_be_published() -> None:
    with pytest.raises(TypeError):
        public_jwk(Ed25519PrivateKey.generate())  # type: ignore[arg-type]


@pytest.fixture
def server() -> Iterator[JwksServer]:
    yield from JwksServer().run()


@pytest.fixture
def key() -> dict[str, str]:
    return public_jwk(Ed25519PrivateKey.generate().public_key())


def test_a_published_key_is_found_by_its_kid(server: JwksServer, key: dict[str, str]) -> None:
    server.serve(key)

    found = JwksClientKeyProvider(server.url).get(key["kid"])

    assert found.key_id == key["kid"]


def test_the_fetch_names_the_library_version(server: JwksServer, key: dict[str, str]) -> None:
    server.serve(key)

    JwksClientKeyProvider(server.url).get(key["kid"])

    # Whatever version is installed, so the test survives every bump.
    assert server.requests[0]["User-Agent"] == f"brandreviews-authz/{version('brandreviews-authz')}"


def test_keys_are_cached_between_lookups(server: JwksServer, key: dict[str, str]) -> None:
    server.serve(key)
    keys = JwksClientKeyProvider(server.url)

    for _ in range(5):
        keys.get(key["kid"])

    assert len(server.requests) == 1


def test_a_flood_of_unknown_kids_costs_no_extra_fetches(
    server: JwksServer, key: dict[str, str]
) -> None:
    server.serve(key)
    keys = JwksClientKeyProvider(server.url)

    for n in range(5):
        with pytest.raises(TokenRejected):
            keys.get(f"unknown-{n}")

    # One fetch; the 30 s cooldown blocks a refetch per forged kid.
    assert len(server.requests) == 1


def test_a_rotated_key_is_picked_up_by_its_new_kid(server: JwksServer, key: dict[str, str]) -> None:
    server.serve(key)
    keys = JwksClientKeyProvider(server.url, cooldown=0)
    keys.get(key["kid"])
    rotated = public_jwk(Ed25519PrivateKey.generate().public_key())
    server.serve(rotated)

    assert keys.get(rotated["kid"]).key_id == rotated["kid"]


def test_a_withdrawn_key_stops_being_trusted_once_the_cache_expires(
    server: JwksServer, key: dict[str, str]
) -> None:
    server.serve(key)
    keys = JwksClientKeyProvider(server.url, lifespan=0.05)
    keys.get(key["kid"])
    # Revoking every token at once: the auth service drops the old key (ADR 0016).
    server.serve(public_jwk(Ed25519PrivateKey.generate().public_key()))
    time.sleep(0.1)

    with pytest.raises(TokenRejected):
        keys.get(key["kid"])


def test_auth_service_down_with_nothing_cached_is_unavailable_not_rejected(
    server: JwksServer,
) -> None:
    server.stop()

    with pytest.raises(KeySetUnavailable):
        JwksClientKeyProvider(server.url, timeout=1).get("x" * 43)


def test_auth_service_down_past_the_cache_lifespan_fails_closed(
    server: JwksServer, key: dict[str, str]
) -> None:
    server.serve(key)
    keys = JwksClientKeyProvider(server.url, lifespan=0.05, timeout=1)
    keys.get(key["kid"])
    server.stop()
    time.sleep(0.1)

    # ADR 0016: no stale keys; the main app answers 503 until auth is back.
    with pytest.raises(KeySetUnavailable):
        keys.get(key["kid"])


@pytest.mark.parametrize(
    ("status", "body"),
    [
        pytest.param(500, b"{}", id="server error"),
        pytest.param(200, b"<html>proxy error</html>", id="HTML, not JSON"),
        pytest.param(200, b"[]", id="JSON, not an object"),
        pytest.param(200, b'{"keys": []}', id="no keys"),
        pytest.param(200, b"[" * 100_000, id="deeply nested"),
    ],
)
def test_a_broken_jwks_response_is_unavailable_not_rejected(
    server: JwksServer, status: int, body: bytes
) -> None:
    server.status, server.body = status, body

    with pytest.raises(KeySetUnavailable):
        JwksClientKeyProvider(server.url).get("x" * 43)


def _private_jwk(kid: str) -> dict[str, str]:
    key = Ed25519PrivateKey.generate()
    d = key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    return public_jwk(key.public_key()) | {"d": _b64url(d), "kid": kid}


def _ed448_jwk(kid: str) -> dict[str, str]:
    raw = (
        Ed448PrivateKey.generate()
        .public_key()
        .public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    )
    return {"kty": "OKP", "crv": "Ed448", "x": _b64url(raw), "kid": kid, "use": "sig"}


def _hmac_jwk(kid: str) -> dict[str, str]:
    return {"kty": "oct", "k": _b64url(b"s" * 32), "kid": kid, "use": "sig"}


@pytest.mark.parametrize(
    "make_jwk",
    [
        # A JWKS carrying d would put a signing key in the main app's memory.
        pytest.param(_private_jwk, id="private Ed25519 key"),
        # EdDSA also names Ed448 (RFC 9864).
        pytest.param(_ed448_jwk, id="Ed448 key"),
        pytest.param(_hmac_jwk, id="HMAC secret"),
    ],
)
def test_a_key_that_is_not_an_ed25519_public_key_is_refused(
    server: JwksServer, make_jwk: Callable[[str], dict[str, str]]
) -> None:
    kid = "k" * 43
    server.serve(make_jwk(kid))

    with pytest.raises(KeySetUnavailable):
        JwksClientKeyProvider(server.url).get(kid)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
