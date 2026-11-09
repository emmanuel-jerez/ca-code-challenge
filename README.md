# Brand Reviews: WordPress → Django migration

This repository replaces a small WordPress reviews site with a Django app, a REST API, a React `<BrandList />` component, an SCSS source tree, a separate auth service and a shared Python library. The brief is in [CHALLENGE.md](CHALLENGE.md).

This README gives an overview and the commands to run. The code, tests and records hold the detail:
- **Decisions:** [docs/adr/](docs/adr/README.md) has one record per decision: its context, the options that lost and when to revisit it.
- **Research:** [docs/research/](docs/research/) has cited notes, one per pillar plus the stack.
- **Agent rules:** [AGENTS.md](AGENTS.md) has the rules every AI agent here follows, each with its reason.

## Status (2026-11-09)

All six pillars are built and tested. Still open:

| Item | State |
|---|---|
| The main app linking reviewers to auth-service users through `secrets/user-map.json` (ADR 0020) | Not started. `make auth-map` already writes the map |
| CI | None. Run the commands under [Tests and checks](#tests-and-checks) locally |
| Django 5.2.19 | Clears the 7-day cooldown on 2026-11-10. Raise the floor in both services then (ADR 0014) |

## How it fits together

```
WordPress + MariaDB ──(read-only import)──► main app + Postgres ◄── browser (pages, /api/brands/, <BrandList />)
        │                                          ▲
        └──(read-only user import)──► auth service + Postgres
                                                   │
                         JWKS (public keys) ───────┘  main app verifies tokens locally
```

| Part | Where | Port | Role |
|---|---|---|---|
| WordPress site | `wp-content/`, `db/dump.sql` | 8080 (admin `admin`/`admin`), phpMyAdmin 8081 | The migration source |
| Main app | [main-app/](main-app/) | 8000 | Pages, the brand API and the editor-only `PATCH`. Stores no passwords or roles |
| Auth service | [auth-service/](auth-service/) | 8001 | Users, passwords and roles. Issues tokens and publishes its public keys (JWKS) |
| Shared library | [shared-lib/](shared-lib/) | – | `brandreviews-authz`: the token contract both services install |
| Frontend | [frontend/](frontend/) | 5173 in dev | `<BrandList />` and the SCSS tree. The main app's image builds both |

Each service has its own Postgres 18 database (ADR 0006). The databases listen only on `127.0.0.1`: MariaDB on 3307, the main app's Postgres on 5433, the auth service's on 5434.

## Quick start

You need Docker. Node and uv are needed only to work on the code outside containers.

```bash
cp .env.example .env        # once; the defaults work locally
make up                     # every service; generates the token signing key the first time
make import                 # WordPress content → main app (safe to re-run)
make auth-import            # WordPress users → auth service (safe to re-run)
```

Then open:
- <http://localhost:8000>: the homepage;
- <http://localhost:8000/brand/>: `<BrandList />`;
- <http://localhost:8000/brand/acme-insurance/>: a brand page;
- <http://localhost:8000/review/online-portal-feels-like-2010/>: a review page.

`make help` lists every target. On a MariaDB volume created before the import users existed, run `make wp-import-user` once, or `make reset` to start again from the dump.

## Pillar 1: Django app and WordPress import

[main-app/](main-app/) has four tables: `Industry`, `Brand`, `Review` and `Reviewer`. It renders the homepage, `/brand/`, `/brand/<slug>/` and `/review/<slug>/` at WordPress's permalink paths.

**Running the migration.** `make import` runs `manage.py import_wp` against WordPress's MariaDB (ADR 0007). `make import-dry-run` runs the same checks, prints the counts and rolls back.
- **Re-runnable.** Rows upsert on their WordPress id, and unchanged rows aren't written. A second run reports `0 created, 0 updated, N unchanged`.
- **All or nothing.** Every row is checked before the first write. The run is one transaction behind an advisory lock, so a bad row or a second concurrent run changes nothing.
- **Nothing deleted.** A post deleted or unpublished in WordPress is hidden from the site, not deleted.
- **Least privilege.** The importer's MariaDB user can't read password hashes or emails.
- **At 100x** the design holds: reads are keyset-paginated inside one snapshot. Beyond that, batched lookups and bulk upserts would replace the in-memory comparison (ADR 0026).

## Pillar 2: `GET /api/brands/`

A public, paginated list of published brands. Each row has what a card needs: name, slug, industry, average rating, review count, short description and the top review.

```bash
curl 'http://localhost:8000/api/brands/?industry=finance&industry=telecom&ordering=-review_count&page_size=2'
```

| Parameter | Values | Default |
|---|---|---|
| `industry` | An industry slug; repeat it to match any of several | All |
| `ordering` | `-average_rating`, `average_rating`, `-review_count`, `review_count` | `-average_rating` |
| `page_size` | 1–50 | 12 |
| `page` | 1, 2, … | 1 |

- **Response:** DRF's page envelope (`count`, `next`, `previous`, `results`). Bad values get a 400 with a message per parameter. Unknown parameter names are ignored, so newer clients keep working (ADRs 0022, 0027).
- **Top review:** the brand's highest-rated published review, then the newest (ADR 0027).
- **Stable pages:** every ordering ends in `id`, so pages never repeat or skip a brand. A page costs a fixed number of queries whatever its size, and tests pin the count.
- **Contract with the frontend:** a pytest test writes real responses to [contracts/brand-list.example.json](contracts/brand-list.example.json), and the frontend's Zod schema is tested against that file (ADR 0010). After an intended API change, run `make contracts` and commit the result.

## Pillar 3: `<BrandList />`

The React 19 component in [frontend/src/brand-list/](frontend/src/brand-list/) has an industry filter, a sort control, pagination, and loading, empty and error states (ADRs 0011, 0028).
- **State in the URL:** filters, sort and page are shareable, and Back works.
- **No stale results:** a newer request aborts the one in flight.
- **Accessible:** native controls (checkboxes, a `<select>`, links), managed focus, and a polite status message after each change.
- **Responsive:** the layout reflows down to 320px wide.

The main app serves it at `/brand/`. To work on it with hot reload, keep the main app running and use Node 24.15+ and pnpm:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm dev                    # http://localhost:5173, /api proxied to :8000
```

## Pillar 4: SCSS

[frontend/scss/](frontend/scss/) compiles to one `theme.css`, which styles both the Django pages and `<BrandList />` (ADRs 0023, 0030, 0031).

```bash
cd frontend
pnpm scss                   # scss/theme.scss → dist-css/theme.css
```

- **Layout:** one folder per cascade layer: `tokens/`, `tools/`, `base/`, `layout/` (`l-`), `components/` (`c-`), `utilities/` (`u-`). Tokens are Sass maps emitted as CSS custom properties. A mistyped token name fails the build.
- **Adding a component:** add one partial in `components/` with BEM class names, and one `@use` line in `components/_index.scss`. Tests enforce the conventions.
- **Equivalence:** a test compares the compiled CSS with [reference/theme.css](reference/theme.css), declaration by declaration, through the WordPress → BEM selector map in [frontend/scss/wp-mapping.ts](frontend/scss/wp-mapping.ts). Every intended difference has a listed reason.

In Docker, the main app's image compiles the CSS and the component in a Node stage, so the runtime image has no Node (ADR 0032).

## Pillar 5: Auth service

[auth-service/](auth-service/) owns users, passwords and roles. The main app stores none of them (ADRs 0016, 0024, 0033).
- **Users:** `make auth-import` copies the 9 WordPress users. They get no usable password, so set one before logging in.
- **Roles:** `reader` grants `brands:read`; `editor` grants `brands:read brands:write`. The imported `admin` is an editor. The main app checks scopes, never role names.
- **Tokens:** 10-minute EdDSA JWTs. The main app verifies them locally against the auth service's public keys and never calls the auth service per request.

**Get a token and call the protected endpoint:**

```bash
docker compose exec auth-service python manage.py changepassword admin   # at least 12 characters

TOKEN=$(curl -s -X POST http://localhost:8001/api/token/ \
  -H 'Content-Type: application/json' \
  -d '{"username": "admin", "password": "<the password you set>"}' \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])')

curl -s -X PATCH http://localhost:8000/api/brands/acme-insurance/ \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"short_description": "A general-lines insurer in 38 US states."}'
```

| Case | Response |
|---|---|
| No token, or a bad or expired one | 401 |
| A valid token without `brands:write` (a reader) | 403 |
| The auth service's keys can't be fetched | 503, so the client retries instead of discarding a valid token |

**Auth service down:** pages and `GET /api/brands/` keep working. The `PATCH` keeps working while the cached keys last (5 minutes).

**Revoking access or changing a role:** run `docker compose exec auth-service python manage.py grant_role <user> editor` (or `revoke_role`). The change reaches the main app within one token lifetime (10 minutes). There is no admin site, so the service that holds the passwords has no second login form (ADR 0033).

## Pillar 6: Shared library

[shared-lib/](shared-lib/) is `brandreviews-authz`: token verification, the claims dataclass, scope names, the public-key fetcher and a thin DRF adapter (ADRs 0025, 0034). Its [README](shared-lib/README.md) lists each module and which service uses it.
- **Kept out:** signing (only the auth service may issue tokens), the role → scope map, models and settings.
- **Contract test:** the auth service issues tokens through the library's claims, and a test verifies them with the library's verifier, so the issuer and the verifier can't drift apart.

**Run its tests** (no Django project, database or network needed): `make test-shared`.

**How a new version reaches each service.** Both services install the library from its directory as a uv path source, so the name is never looked up on PyPI.
1. Change the library, add a `CHANGELOG.md` entry, and run `uv version --bump <patch|minor|major>` in `shared-lib/`.
2. Run `uv lock` in `main-app/` and `auth-service/`, run their tests, and commit everything together. `make check-shared` fails on a missing version bump or a stale lockfile.
3. Deploy each service on its own schedule. A breaking change goes expand → migrate → contract, so the two services never have to deploy together.

## Tests and checks

| Part | Command | Needs |
|---|---|---|
| Main app | `make test`, then `uv run mypy .` and `uv run ruff check .` in `main-app/` | `docker compose up -d main-db` |
| Auth service | `make test-auth`, then `uv run mypy .` and `uv run ruff check .` in `auth-service/` | `docker compose up -d auth-db` |
| Shared library | `make test-shared` (pytest, mypy strict, Ruff), `make check-shared` | Nothing |
| Frontend and SCSS | `pnpm test`, `pnpm typecheck` in `frontend/` | Node 24.15+, pnpm |

The import tests run against the real WordPress database, and skip themselves when MariaDB isn't reachable.

## Decisions

The [ADR index](docs/adr/README.md) lists every decision.

### Modeling

- **Four tables instead of posts + postmeta,** with real foreign keys and check constraints. Every imported row keeps its WordPress id under a unique constraint.
- **Ratings are stored and derived.** `average_rating` and `review_count` are computed from published reviews at import time and stored, so sorting is cheap. WordPress's own value is kept as `legacy_average_rating` for audit, because it was too high for 4 of the 5 brands (ADR 0019).
- **Reviewers** are a thin `Reviewer` table, plus name and location snapshots on each review, because the same person reviewed from different cities. Passwords and roles live only in the auth service (ADR 0020).
- **Postmeta:** four ACF fields and two Yoast fields became typed columns. ACF's internal field-key rows were dropped. Any key nobody has sorted yet stops the import (ADR 0021).
- **HTML** is sanitized once at import with nh3, and the raw source is kept so it can be cleaned again later (ADRs 0004, 0018).

### With more time

- **Performance.** Build prototypes and benchmarks to improve query performance, overall database performance and app performance.
- **Accessibility.** Test the accessibility features and run a full audit, so the site complies with the most up-to-date standard.
- **Security.** Carry on with a security audit, backed by more security tools, so security is tested exhaustively.

### AI defaults accepted

Where the AI's suggestion was good enough, it was accepted and recorded rather than replaced with a personal preference. Each record lists these defaults with its reasons:

| Area | Record | Examples |
|---|---|---|
| Import and pages | [0026](docs/adr/0026-pillar-1-import-and-pages.md), items 5–10 | Compare stored values instead of a hash column; stop the run on any bad row; function views |
| API | [0027](docs/adr/0027-pillar-2-listing-contract-details.md), items 7–9 | ETag revalidation instead of a server-side cache; no in-app throttling |
| `<BrandList />` | [0028](docs/adr/0028-pillar-3-brandlist-component.md), items 6–14; [0030](docs/adr/0030-scss-tree-started-for-brandlist.md), item 6 | A 10-second request timeout; full Zod rather than `zod/mini` |
| SCSS | [0031](docs/adr/0031-pillar-4-delivery-equivalence-and-blocks.md), items 5–15; [0032](docs/adr/0032-pillar-4-delivery-defaults.md) | A `surface` mixin rather than a shared class; whitenoise's defaults |
| Auth service | [0033](docs/adr/0033-pillar-5-auth-service.md), items 9–18 | A MariaDB view for the user import; the throttle rates |
| Shared library | [0034](docs/adr/0034-pillar-6-shared-library-and-patch.md), items 5–18 | Seven small modules; one `TokenRejected` error carrying a reason |

## The WordPress source site

A small, reproducible consumer-reviews site: 5 brands (one per industry), 60 reviews by 8 reviewer users, 3 static pages and 1 admin. Brands and reviews are custom post types with ACF fields and Yoast SEO metadata, defined in [cpt.php](wp-content/mu-plugins/cpt.php) and [acf-fields.php](wp-content/mu-plugins/acf-fields.php). MariaDB loads `db/dump.sql` on first boot, and the REST API is at <http://localhost:8080/wp-json/wp/v2/>.

**Rebuilding the dump** after changing the seed data: `make reset && make up && make bootstrap && make dump`, then commit `db/dump.sql`.

**Maintainer notes:**
- ACF and Yoast are committed under `wp-content/plugins/` so the first boot needs no internet.
- The site URL `http://localhost:8080` is hard-coded in the dump. To change the port, search and replace in `db/dump.sql`, or set `WP_HOME` and `WP_SITEURL`.
