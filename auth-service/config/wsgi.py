"""WSGI entry point for gunicorn."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

# Load the signing key before serving anything, so a missing or wrong key
# stops the web container at boot instead of failing the first login.
# Only gunicorn imports this module: management commands, which never sign,
# run without the key.
from accounts.tokens import signing_key  # noqa: E402

signing_key()
