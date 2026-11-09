"""Shared fixtures: a throwaway signing key, users, and a clean throttle cache."""

import itertools
from typing import TYPE_CHECKING, Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.contrib.auth.models import Group
from django.core.cache import cache

from accounts.models import User

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from pytest_django import Settings

_ids = itertools.count(1)
PASSWORD = "correct horse battery staple"  # noqa: S105 - test-only password


@pytest.fixture(autouse=True)
def signing_key_file(tmp_path: Path, settings: Settings) -> Path:
    """Every test signs with its own freshly generated Ed25519 key."""
    path = tmp_path / "jwt_signing_key.pem"
    path.write_bytes(
        Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    settings.JWT_SIGNING_KEY_FILE = path
    return path


@pytest.fixture(autouse=True)
def clear_throttles() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def make_user() -> Callable[..., User]:
    """A user with PASSWORD and the given roles (Group names)."""

    def make(*roles: str, **fields: Any) -> User:  # noqa: ANN401 - forwards model field values
        n = next(_ids)
        fields.setdefault("username", f"user{n}")
        fields.setdefault("email", f"user{n}@example.com")
        password = fields.pop("password", PASSWORD)
        user = User.objects.create_user(password=password, **fields)
        user.groups.set(Group.objects.filter(name__in=roles))
        return user

    return make
