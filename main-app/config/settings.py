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
    "catalog",
    "wp_import",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
