# Decision records

Each record states the decision as it stood on its date, with the context and the
options that lost (see 0000). Superseded records stay, marked with their replacement. Factual
errors that don't change a decision are corrected in a separate record, linked from the
original's status line (0018).

| # | Decision | Status |
|---|---|---|
| [0000](0000-record-decisions-with-context.md) | Record decisions with their context | Accepted |
| [0001](0001-django-5-2-lts-on-python-3-14.md) | Django 5.2 LTS on Python 3.14 | Superseded by 0014 |
| [0002](0002-django-rest-framework-for-the-api.md) | Django REST Framework for the API | Superseded by 0015 |
| [0003](0003-eddsa-jwt-verified-locally.md) | EdDSA JWTs verified locally | Superseded by 0016 |
| [0004](0004-nh3-html-sanitizer.md) | nh3 for WordPress HTML | Accepted (corrected in 0018) |
| [0005](0005-custom-csp-middleware.md) | Custom CSP middleware | Superseded by 0017 |
| [0006](0006-postgres-per-service.md) | Postgres per service | Accepted |
| [0007](0007-pymysql-for-the-wp-import.md) | Read WordPress from MariaDB with PyMySQL | Accepted |
| [0008](0008-gunicorn-whitenoise-base-image.md) | gunicorn + whitenoise on python:3.14-slim | Accepted (corrected in 0018) |
| [0009](0009-mypy-django-stubs-ruff.md) | mypy strict + django-stubs + Ruff | Accepted |
| [0010](0010-api-contract-zod-fixture.md) | Zod schema + contract fixture, no OpenAPI generator | Accepted |
| [0011](0011-frontend-toolchain.md) | React 19 + Vite 8, client-only, TS 6 | Accepted |
| [0012](0012-dependency-cooldown-and-security-exceptions.md) | 7-day cooldown with approved security exceptions | Accepted (corrected in 0018) |
| [0013](0013-validation-and-typing-patterns.md) | Validation and typing patterns | Accepted |
| [0014](0014-raise-the-django-floor.md) | Django 5.2 LTS with a security floor (`>=5.2.18`) | Accepted |
| [0015](0015-drf-json-only.md) | Django REST Framework, JSON only | Accepted |
| [0016](0016-token-lifetime-revocation-and-outages.md) | EdDSA JWTs: 10-minute lifetime, revocation, outages | Accepted |
| [0017](0017-csp-covers-styles-and-the-vite-build.md) | CSP for scripts and styles | Accepted |
| [0018](0018-factual-corrections-to-0004-0008-0012.md) | Factual corrections to 0004, 0008 and 0012 | Accepted |
| [0019](0019-brand-rating-computed-from-reviews.md) | Brand rating computed from reviews, stored at import | Accepted |
| [0020](0020-reviewer-identity-across-services.md) | Reviewer identity across the two services | Accepted |
| [0021](0021-postmeta-triage.md) | Postmeta triage | Accepted |
| [0022](0022-brand-listing-query-parameters.md) | Brand listing query parameters | Accepted |
| [0023](0023-scss-naming-and-brandlist-styling.md) | SCSS naming, `<BrandList />` styling, Sass as the linter | Accepted |
| [0024](0024-imported-passwords-and-hashing.md) | Imported passwords and password hashing | Accepted |
| [0025](0025-shared-library-packaging.md) | Shared library packaging, name and upgrade path | Accepted |
| [0026](0026-pillar-1-import-and-pages.md) | Pillar 1: industry FK, removals, sanitizing, writes, views | Accepted |
| [0027](0027-pillar-2-listing-contract-details.md) | Pillar 2: top review, validation, errors, versioning, fixture, caching | Accepted |

Template: Status · Date · Context · Options considered · Decision · Consequences ·
Revisit when · Sources.
