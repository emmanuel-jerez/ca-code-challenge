"""Settings for the main app.

Secrets and hosts come from environment variables; nothing secret is committed.
DEBUG defaults to off, so a missing variable fails safe.
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
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = env_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")

# No django.contrib.auth, admin or sessions: the auth service owns users and
# roles (AGENTS.md), and the admin is out of scope (CHALLENGE.md).
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "catalog",
    "wp_import",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Above everything else except SecurityMiddleware, as whitenoise documents.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "config.csp.ContentSecurityPolicyMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.environ.get("MAIN_DB_HOST", "localhost"),
        "PORT": os.environ.get("MAIN_DB_PORT", "5433"),
        "NAME": os.environ.get("MAIN_DB_NAME", "brandreviews"),
        "USER": os.environ.get("MAIN_DB_USER", "brandreviews"),
        "PASSWORD": os.environ.get("MAIN_DB_PASSWORD", ""),
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

# Static files: theme.css and the <BrandList /> build, compiled in the image's
# Node stage and served by whitenoise (ADRs 0008, 0031). The build lands in
# ../frontend in a checkout and in /app/frontend in the image.
FRONTEND_DIR = Path(os.environ.get("DJANGO_FRONTEND_DIR", BASE_DIR.parent / "frontend"))
STATIC_URL = "static/"
STATIC_ROOT: Path | None = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    ("css", FRONTEND_DIR / "dist-css"),
    ("frontend", FRONTEND_DIR / "dist"),
]
# Read by the vite_entry template tag. collectstatic skips the dot directory,
# so the manifest isn't served.
VITE_MANIFEST_PATH = FRONTEND_DIR / "dist" / ".vite" / "manifest.json"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Hashed names, so browsers can cache forever, plus gzipped copies. Brotli
    # would need the optional Brotli package, which isn't installed.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

REST_FRAMEWORK = {
    # JSON in and out only: most 2026 DRF and Django advisories sat in the
    # form/multipart parsers and the browsable API (ADR 0015).
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    # No session or basic auth: this app has no passwords. The bearer-token
    # class from the shared library arrives with the auth service (Pillar 5).
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    # Deny by default; public views opt in with AllowAny. With no
    # authentication classes, IsAuthenticated refuses everyone.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    # DRF's default (AnonymousUser) imports django.contrib.auth, which this
    # app doesn't install.
    "UNAUTHENTICATED_USER": None,
}

# Content Security Policy (ADR 0017): scripts and styles from our origin only,
# no 'unsafe-inline'. Report-only until reports are clean.
CSP_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
    "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
)
CSP_REPORT_ONLY = env_bool("DJANGO_CSP_REPORT_ONLY", default=True)

# Production hardening. Behind a TLS-terminating proxy, set
# DJANGO_SECURE_PROXY_SSL_HEADER=true and DJANGO_SECURE_SSL_REDIRECT=true.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=False)
# Served over HTTPS whenever the redirect is on, so the cookie can require it.
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
if env_bool("DJANGO_SECURE_PROXY_SSL_HEADER", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
