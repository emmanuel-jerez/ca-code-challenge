# 0008. gunicorn + whitenoise on python:3.14-slim-trixie

- Status: Accepted (gunicorn approved by the user without a Python 3.14 classifier)
- Date: 2026-11-09

## Context
Both services run in containers with `DEBUG=False`, so they need an application server
and something to serve static files (compiled SCSS, the React bundle). Views are
synchronous.

## Options considered
| Server | Latest (date) | Python 3.14 | Notes |
|---|---|---|---|
| **gunicorn** | 26.2.0 (2026-08-24) | Not declared; CI stops at 3.13 | Pure Python, zero deps, Django 5.2's documented WSGI path. **Chosen** |
| granian | 2.8.7 (2026-10-28) | Declared, cp314 wheels | Rust binary, mostly one maintainer. **Fallback** |
| uvicorn | 0.54.0 (2026-09-25) | Declared | ASGI only, "beta"; sync Django gains nothing |
| waitress | 3.0.2 (2024-11-16) | Not declared | No release in two years |
| uWSGI | 2.0.31 | No classifiers | Maintenance-only |

Static files: **whitenoise** chosen over an nginx container (one less service).

## Decision
- `gunicorn>=26.2.0,<27`, sync workers. Approved without the 3.14 classifier because
  it is pure Python with no dependencies; backed by a test that boots gunicorn and
  fetches `/api/brands/`, plus container healthchecks.
- `whitenoise>=6.12.0,<7`.
- Base image `python:3.14-slim-trixie` pinned by digest; uv copied in from its official
  image. Containers run as non-root and never mount the Docker socket.

## Consequences
GitHub has gunicorn tags 26.2.1/26.2.2 (HTTP/2 and ASGI hardening, 2026-09-05/06) that
never reached PyPI; the reason is unknown. They don't affect the sync worker.

## Revisit when
gunicorn declares Python 3.14, a 3.14-specific bug appears (switch to granian), or the
app needs async.

## Sources
`docs/research/stack-validation.md` §3.3–3.4; PyPI JSON checked 2026-11-09.
