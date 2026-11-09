# 0014. Django 5.2 LTS with a security floor, not a compatibility floor

- Status: Accepted
- Date: 2026-11-09
- Supersedes: [0001](0001-django-5-2-lts-on-python-3-14.md)

## Context
ADR 0001 chose Django 5.2 LTS on Python 3.14 with `Django>=5.2.8,<5.3`. 5.2.8 was
picked because it is the first patch release that supports Python 3.14, not for
security. The pillar research (`docs/research/pillar-1-django-backend.md` §9,
`pillar-2-brands-api.md` §3.3) found that the floor and two statements in 0001 were
wrong. Each fact below was checked against djangoproject.com and PyPI on this date.

- **The floor admits vulnerable releases.** 5.2.8 (2025-11-05) lacks CVE-2025-13372
  (SQL injection in `FilteredRelation` column aliases on PostgreSQL, fixed in 5.2.9 on
  2025-12-02) and the February 2026 fixes (5.2.11, 2026-02-03). Only the lockfile kept
  us off them.
- **0001 said three February 2026 SQL injection CVEs came "through `order_by` and
  aliases".** Only two did: CVE-2026-1287 (`FilteredRelation` aliases with control
  characters) and CVE-2026-1312 (`QuerySet.order_by()`), and the alias CVEs need
  attacker-controlled alias names. The third, CVE-2026-1207, is in PostGIS raster
  lookups. The allow-list rule stands either way.
- **0001 called 5.2.19 "a GIS-only security fix".** 5.2.19 (2026-11-03 15:22 UTC) fixes
  five CVEs on 5.2. Three are GIS (CVE-2026-111211, -111362, -114582). Two are not:
  CVE-2026-108147 (memory exhaustion in `MultiPartParser`) and CVE-2026-113593
  (`cache_page`/`UpdateCacheMiddleware` give the same cache key for empty and missing
  `Vary` headers). Both are rated low.
- 5.2.18 (2026-10-06) is the newest release past the 7-day cooldown (ADR 0012). 5.2.19
  clears it on 2026-11-10 at 15:22 UTC.

## Options considered
- **Keep `>=5.2.8` and rely on the lockfile.** Rejected: a resolve without the lock, a
  downgrade or a copied pin can land on a vulnerable release. The floor should say what
  is safe, not only what runs.
- **Floor at 5.2.19 now, as a security exception (ADR 0012).** Rejected: neither non-GIS
  fix is reachable here. Multipart parsing is off (ADR 0015) and neither `cache_page` nor
  `UpdateCacheMiddleware` is used. An exception is for fixes we need before the
  cooldown ends.
- **Floor at the newest release past the cooldown, raised as each security release
  clears.** Chosen.

## Decision
- `Django>=5.2.18,<5.3` and `requires-python = ">=3.14,<3.15"`.
- Raise the floor to `>=5.2.19` in the change that locks 5.2.19, on or after
  2026-11-10 15:22 UTC. From then on, the floor follows each security release once it
  clears the cooldown.
- Unchanged from 0001: 5.2 LTS, not 6.x. User input never reaches `order_by()`,
  `annotate()`/`alias()` names, `values()` or `extra()`; sort and filter parameters
  map through allow-lists.

## Consequences
- Until 5.2.19 is locked, don't enable multipart parsing, `cache_page` or
  `UpdateCacheMiddleware`.
- The `django-lts` skill and AGENTS.md carry the new floor.
- Docs lookups still target 5.2, not latest.

## Revisit when
Django 6.2 LTS ships (expected April 2027), a needed package drops 5.2, or a security
release fixes something reachable here (then ADR 0012's exception path applies).

## Sources
- Django security releases: [2025-12-02](https://www.djangoproject.com/weblog/2025/dec/02/security-releases/),
  [2026-02-03](https://www.djangoproject.com/weblog/2026/feb/03/security-releases/),
  [2026-11-03](https://www.djangoproject.com/weblog/2026/nov/03/security-releases/).
- [PyPI Django release files](https://pypi.org/project/Django/#history), upload times checked 2026-11-09.
- `docs/research/pillar-1-django-backend.md` §9 and Conflicts;
  `docs/research/pillar-2-brands-api.md` §3.3 and Conflicts.
