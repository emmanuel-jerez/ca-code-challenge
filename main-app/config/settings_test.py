"""Test settings: the production settings plus local defaults for required variables.

Tests run against the compose `main-db` Postgres (bound to localhost:5433).
"""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-a-secret")
os.environ.setdefault("MAIN_DB_PASSWORD", "brandreviews")

from config.settings import *  # noqa: E402, F403
