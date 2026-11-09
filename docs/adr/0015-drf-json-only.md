# 0015. Django REST Framework, JSON only

- Status: Accepted
- Date: 2026-11-09
- Supersedes: [0002](0002-django-rest-framework-for-the-api.md)

## Context
ADR 0002 chose DRF 3.18 and described it as "8 releases in 2026, 3 security fixes in
October". The pillar research (`docs/research/pillar-2-brands-api.md`) corrected this,
and the correction was checked against PyPI and GitHub's advisory list on this date:

- **7 releases in 2026:** 3.17.0, 3.17.1, 3.17.2, 3.18.0, 3.18.1, 3.18.2, 3.18.3.
- **5 advisories in 2026:**
  - 2026-08-05, fixed after 3.17.1: CVE-2026-73228 (`DATA_UPLOAD_MAX_MEMORY_SIZE`
    bypass while parsing) and CVE-2026-73229 (`AdminRenderer` disclosure).
  - 2026-10-06, fixed in 3.18.2: CVE-2026-114136 (`JSONParser` applies an
    attacker-named codec), CVE-2026-114137 (`TokenProxy.delete()` revokes nothing) and
    CVE-2026-114138 (CPU burn from a crafted `Accept` header).

The `>=3.18.3` floor covers all five. Most of them sit in parsers, renderers and
content negotiation. Django's CVE-2026-108147 (ADR 0014) is in `MultiPartParser`, which
DRF enables by default. Neither service needs form or multipart input. Neither needs the
browsable API either: tokens come from the auth service by `curl` (CHALLENGE.md allows
this), and the main app has no login.

## Options considered
- **DRF defaults** (JSON, form and multipart parsers; JSON and browsable-API
  renderers). Rejected: attack surface for features neither service uses.
- **JSON-only in production, browsable API in development.** Rejected: two
  configurations to keep in step, for a convenience `curl` already gives.
- **JSON-only everywhere.** Chosen.
- Django Ninja and plain views were weighed and rejected in 0002; nothing here changes
  that.

## Decision
- `djangorestframework>=3.18.3,<3.19` in both services.
- `DEFAULT_PARSER_CLASSES = ["rest_framework.parsers.JSONParser"]` and
  `DEFAULT_RENDERER_CLASSES = ["rest_framework.renderers.JSONRenderer"]` in both.
- Unchanged from 0002: page-number pagination with a unique tie-breaker on every sort,
  allow-listed filter and sort parameters, capped page size (details in ADR 0022).

## Consequences
- Requests with other content types get 415, and other `Accept` values get 406.
- Serializers still give no static types (`validated_data` is `Any`); see ADR 0013.
- DRF is in maintenance mode but still ships security fixes. That's acceptable for the
  auth layer and is the revisit trigger.

## Revisit when
DRF stops shipping security fixes, async views become a requirement, or a client needs
another content type.

## Sources
- [PyPI djangorestframework release history](https://pypi.org/project/djangorestframework/#history), checked 2026-11-09.
- [GitHub security advisories for encode/django-rest-framework](https://github.com/encode/django-rest-framework/security/advisories), checked 2026-11-09.
- `docs/research/pillar-2-brands-api.md` §8 and Conflicts; `docs/research/stack-decisions.md` §2a.
