# 0005. A custom middleware for Content Security Policy

- Status: Superseded by [0017](0017-csp-covers-styles-and-the-vite-build.md)
- Date: 2026-11-09

## Context
CSP is defense in depth against XSS (ADR 0004 is the first line). Django 5.2 has no
built-in CSP; `SECURE_CSP` arrived in 6.0. The React bundle is served as a static file
and its initial data goes through `json_script`, so no inline scripts are needed.

## Options considered
- **django-csp 4.x.** Nonce support, well known. Rejected: no declared Python 3.14
  support and its tests don't run on 3.14, so it fails dependency vetting.
- **Header set at a reverse proxy.** Rejected: there is no proxy in this stack
  (ADR 0008 serves static files with whitenoise).
- **A small custom middleware.** Chosen.

## Decision
A ~20-line middleware sets the header from a settings value, starting with
`Content-Security-Policy-Report-Only` and `script-src 'self'`, then switching to
enforcing once reports are clean. No nonces.

## Consequences
It's our own security code, so it needs tests (header present, policy value, report
mode). Adding nonces later would mean either extending it or adopting django-csp.

## Revisit when
Inline scripts or nonces become necessary, django-csp declares Python 3.14, or the
project moves to Django 6.2 LTS (built-in CSP).

## Sources
`docs/research/stack-decisions.md` §1.
