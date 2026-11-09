"""Settings for the auth service.

Secrets and hosts come from environment variables; nothing secret is committed.
DEBUG defaults to off, so a missing variable fails safe.

This service holds every password and the token signing key, so it runs the
least code (ADR 0033): no admin, sessions, messages, staticfiles, CSRF or
templates. Login is the only unauthenticated write and no cookie is ever set.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


# Required: there is no fallback key, so a forgotten variable stops startup.
# Tokens don't use it; Django still needs one.
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = env_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "accounts",
    "wp_import",
]

# No session, auth or CSRF middleware: there are no cookies, so no ambient
# credential for CSRF to protect. `check --deploy` still warns (W003).
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    # JSON can't be usefully framed, but the header costs nothing.
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
# JSON only; error pages fall back to Django's built-in plain responses.
TEMPLATES: list[dict[str, object]] = []

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.environ.get("AUTH_DB_HOST", "localhost"),
        "PORT": os.environ.get("AUTH_DB_PORT", "5434"),
        "NAME": os.environ.get("AUTH_DB_NAME", "brandreviews_auth"),
        "USER": os.environ.get("AUTH_DB_USER", "brandreviews_auth"),
        "PASSWORD": os.environ.get("AUTH_DB_PASSWORD", ""),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    },
}

# 5.2 doesn't default to BigAutoField yet (django-lts skill).
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

AUTH_USER_MODEL = "accounts.User"
# Username or email, case-insensitive, like WordPress (ADR 0033).
AUTHENTICATION_BACKENDS = ["accounts.backends.UsernameOrEmailBackend"]
# scrypt first: memory-hard, standard library only. PBKDF2 second, so hashes
# made before the switch still verify and are upgraded on login (ADR 0024).
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.ScryptPasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
# Run by `manage.py changepassword`, the only way a password gets set.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# A login body is tiny; refuse anything larger before parsing it.
DATA_UPLOAD_MAX_MEMORY_SIZE = 16 * 1024

# Throttle counters must be shared by every gunicorn worker; the default
# per-process cache would multiply each limit by the worker count. The table
# is made by `createcachetable`, which isn't a migration.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "throttle_cache",
    },
}

REST_FRAMEWORK = {
    # JSON in and out only, as in the main app (ADR 0015).
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    # Nothing here authenticates by header or cookie; the login view checks
    # credentials itself.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    # Deny by default; public views opt in with AllowAny.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    # Key throttles on the socket address. DRF's default (None) trusts a
    # client-sent X-Forwarded-For, which would let a guesser pick its own IP.
    # Behind a proxy, set this to the number of proxies.
    "NUM_PROXIES": int(os.environ.get("DJANGO_NUM_PROXIES", "0")),
    "DEFAULT_THROTTLE_RATES": {
        "login_ip": os.environ.get("AUTH_LOGIN_RATE_IP", "20/min"),
        "login_username": os.environ.get("AUTH_LOGIN_RATE_USERNAME", "5/min"),
    },
}

# Access tokens (ADR 0016). The private key is a mounted file, never an
# environment variable (those show up in `docker inspect`) or the image.
JWT_SIGNING_KEY_FILE = Path(os.environ.get("JWT_SIGNING_KEY_FILE", "/run/secrets/jwt_signing_key"))
JWT_ISSUER = os.environ.get("JWT_ISSUER", "http://auth-service:8000")
# One audience string per resource server, so the verifier can be strict.
JWT_AUDIENCE = os.environ.get("JWT_AUDIENCE", "brands-api")
# RFC 9068 requires client_id. There's no client registry, so it's a constant.
JWT_CLIENT_ID = os.environ.get("JWT_CLIENT_ID", "brands-cli")
ACCESS_TOKEN_LIFETIME_SECONDS = 600

# Production hardening. Behind a TLS-terminating proxy, set
# DJANGO_SECURE_PROXY_SSL_HEADER=true and DJANGO_SECURE_SSL_REDIRECT=true.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=False)
if env_bool("DJANGO_SECURE_PROXY_SSL_HEADER", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
