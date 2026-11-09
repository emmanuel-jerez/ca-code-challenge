"""Test settings: the production settings plus local defaults for required variables.

Tests run against the compose `auth-db` Postgres (bound to localhost:5434).
"""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-a-secret")
os.environ.setdefault("AUTH_DB_PASSWORD", "brandreviews_auth")

from config.settings import *  # noqa: E402, F403

# Per-process is fine in tests, and needs no createcachetable.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
# Tests make many users; the real hasher would make each one cost ~100 ms.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
