"""The signing key and the JWKS that publishes it (ADR 0016).

The JWK format and its kid are the shared library's, tested there against RFC 8037.
"""

from typing import TYPE_CHECKING

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PrivateKey

from accounts.tokens import SigningKey, SigningKeyError

if TYPE_CHECKING:
    from pathlib import Path

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from django.test import Client
    from pytest_django import Settings


def pem(key: Ed25519PrivateKey | Ed448PrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def test_only_ed25519_keys_can_sign() -> None:
    # EdDSA also names Ed448 (RFC 9864); only Ed25519 is accepted.
    with pytest.raises(SigningKeyError, match="Ed25519"):
        SigningKey.from_pem(pem(Ed448PrivateKey.generate()))


def test_a_file_that_is_not_a_key_is_refused() -> None:
    with pytest.raises(SigningKeyError, match="not an unencrypted PEM"):
        SigningKey.from_pem(b"not a key")


def test_jwks_publishes_the_public_key_only(client: Client, signing_key_file: Path) -> None:
    response = client.get("/.well-known/jwks.json")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/jwk-set+json"
    assert "max-age=300" in response["Cache-Control"]
    expected = SigningKey.from_pem(signing_key_file.read_bytes()).public_jwk
    assert response.json() == {"keys": [expected]}
    assert "d" not in response.json()["keys"][0]


@pytest.mark.django_db
def test_healthz_is_ok_with_a_database_and_a_key(client: Client) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_healthz_fails_without_a_key(client: Client, settings: Settings, tmp_path: Path) -> None:
    settings.JWT_SIGNING_KEY_FILE = tmp_path / "missing.pem"

    response = client.get("/healthz")

    assert response.status_code == 503
