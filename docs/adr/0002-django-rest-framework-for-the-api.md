# 0002. Django REST Framework for the API

- Status: Accepted
- Date: 2026-11-09

## Context
The main app needs `GET /api/brands/` (filter, sort, paginate) and an editor-only
`PATCH /api/brands/<slug>/`. CHALLENGE.md says the shared library should hold "a DRF
authentication class and permission class, or a decorator for plain views".

## Options considered
- **DRF 3.18.** Most widely deployed; pagination, filtering and auth/permission hooks
  built in; well known to reviewers and AI tools. Officially "feature-complete", but
  patched (8 releases in 2026, 3 security fixes in October). Chosen.
- **Django Ninja 1.7.** Pydantic types, built-in OpenAPI, async. Rejected: no
  permission classes, so more of the auth layer is hand-built; smaller ecosystem.
- **Plain views returning JSON.** No dependency. Rejected: reinvents pagination,
  validation and the auth hooks the challenge names.

## Decision
`djangorestframework>=3.18.3,<3.19`. Page-number pagination with a unique tie-breaker
on every sort; allow-listed filter and sort params; capped page size.

## Consequences
- Serializers validate requests but give no static types (`validated_data` is `Any`);
  see ADR 0013.
- DRF's slower pace is a stability argument for an auth layer, but it is a dependency
  on a project in maintenance mode.

## Revisit when
DRF stops shipping security fixes, or async views become a requirement.

## Sources
`docs/research/stack-decisions.md` §2a; `docs/research/best-practices-2026.md` §5.
