# Brand Reviews: WordPress → Django migration

This repository holds a WordPress → Django migration challenge ([CHALLENGE.md](CHALLENGE.md)) and the work on it. The WordPress site is the migration source. The deliverables are:
- a Django app;
- a REST API;
- a React `<BrandList />` component;
- an SCSS source tree;
- a separate auth service;
- a shared Python library.

## Project status (2026-11-09)

**Pillars 1 and 2 (the Django app and its brand listing API) are built; Pillars 3–6 are not started.** Every design decision is researched, decided and recorded before code is written, so each line can be traced to a reason.

### Done

- **Pillar 1: Django app** in [main-app/](main-app/): models, the re-runnable WordPress import, and the homepage, brand and review pages. See [Main app](#main-app-pillar-1) below.
- **Pillar 2: `GET /api/brands/`**: filtered, sorted and paginated brand cards, plus a contract fixture for the frontend. See [Brand listing API](#brand-listing-api-pillar-2) below.
- **Agent guidance.**
  - [AGENTS.md](AGENTS.md) (loaded through `CLAUDE.md`) holds the project rules, each with its reason: the accepted stack, security rules, code style, and the auth and frontend rules.
  - Project skills live in `.agents/skills/`. Run `make skills` once per checkout so Claude Code can load them.
- **Research.** [docs/research/](docs/research/) has cited notes on:
  - the stack and its compatibility;
  - 2026 best practices and threats;
  - typing and validation;
  - the dependency cooldown;
  - one deeper note per pillar ([1](docs/research/pillar-1-django-backend.md), [2](docs/research/pillar-2-brands-api.md), [3](docs/research/pillar-3-brandlist-component.md), [4](docs/research/pillar-4-scss-architecture.md), [5](docs/research/pillar-5-auth-service.md), [6](docs/research/pillar-6-shared-library.md)).

  Every option is weighed by its security cost and its long-term stability, and data facts are measured from `db/dump.sql`.
- **Decision records.** [docs/adr/](docs/adr/README.md) holds 28 records (0000–0027). Each gives the context, the options that lost and why, and when to revisit. Records are never rewritten: changed decisions are superseded, and factual errors are corrected in a linked record. Decided so far:
  - **Stack:**
    - Django 5.2 LTS on Python 3.14, with a security floor (`>=5.2.18`);
    - DRF, JSON only;
    - Postgres 18 per service;
    - PyMySQL for reading WordPress;
    - nh3 for its HTML;
    - a custom CSP middleware covering scripts and styles;
    - gunicorn + whitenoise on a digest-pinned image;
    - mypy strict + Ruff;
    - React 19 + Vite 8 client-only, TypeScript 6, `sass`;
    - a 7-day dependency cooldown with approved security exceptions.
  - **Pillar 1:**
    - brand ratings computed from reviews and stored at import, with WordPress's (wrong) value kept for audit;
    - a thin `Reviewer` model linked to the auth service later;
    - postmeta triaged into typed columns plus two SEO fields;
    - industry as a foreign key, and the import stops on anything but one per brand;
    - rows gone from WordPress marked `removed`, never deleted;
    - HTML sanitized at import, with the raw source kept.
  - **Pillar 2:**
    - repeated `industry` keys;
    - a closed `ordering` enum that always ends in `id`;
    - `page_size` from 1 to 50 (default 12);
    - the top review is the highest-rated, then newest;
    - an unknown industry is a 400, while unknown parameter names are ignored;
    - DRF's default error bodies, no URL version, additive changes only;
    - a contract fixture with named cases.
  - **Pillar 3/4:**
    - BEM with `l-`/`c-`/`u-` prefixes;
    - `<BrandList />` styled by a global partial;
    - Sass deprecations as build errors in place of stylelint;
    - `sass` pinned exactly.
  - **Pillar 5:**
    - EdDSA JWTs (10-minute lifetime) verified locally;
    - revocation within one token lifetime;
    - 503 when keys can't be fetched;
    - imported users get no usable password;
    - scrypt for new passwords.
  - **Pillar 6:**
    - `brandreviews-authz`, built with `uv_build`;
    - installed by local path;
    - a version bump required on every change.

### Not done yet

| Deliverable | State |
|---|---|
| Pillar 3: React `<BrandList />` | Not started |
| Pillar 4: SCSS source tree under `frontend/scss/` | Not started |
| Pillar 5: auth service (users, login, roles, JWKS) and the editor-only `PATCH /api/brands/<slug>/` | Not started |
| Pillar 6: shared library with its own tests | Not started |
| Docker Compose services for the auth service and its database | Not started (the main app's are done) |
| README sections the challenge requires: getting a token, running the React component and the library tests, how a library version reaches each service | Not written. Each is added with the code it describes (running the main app, the import and the modeling decisions are written) |
| CI | None |

Still open, with options in the research notes:
- how `<BrandList />` gets the list of industries for its filter (a second endpoint, or a list in the frontend; ADR 0027);
- `PATCH` concurrency;
- whether the auth service has an admin;
- extra pnpm hardening.

Time-bound: Django 5.2.19 clears the cooldown on 2026-11-10. Raise the floor to it in `main-app/` in its own change after it clears (ADR 0014).

## Main app (Pillar 1)

The Django app in [main-app/](main-app/) replaces the WordPress site: models, a re-runnable import from WordPress's MariaDB, and three server-rendered pages at the same paths as WordPress's permalinks.

### Run it

```bash
cp .env.example .env        # once; the defaults work locally
make up                     # WordPress, MariaDB, the main app and its Postgres
make import                 # copy WordPress content into the main app
```

Then open <http://localhost:8000>, <http://localhost:8000/brand/acme-insurance/> or <http://localhost:8000/review/online-portal-feels-like-2010/>.

On a MariaDB volume created before this change, the read-only import user doesn't exist yet. Run `make wp-import-user` once, or `make reset` to start from the dump again.

### The WordPress import

`make import` runs `manage.py import_wp` in a one-off container. It's the only container that gets the WordPress credentials.

- **Re-running is safe.** Every row upserts on its WordPress id, and rows whose stored values already match aren't written. A second run reports `0 created, 0 updated, N unchanged`.
- **Nothing is half-written.** Every row is checked before the first write. The run is one transaction behind a Postgres advisory lock, so a bad row or a second concurrent run changes nothing.
- **Preview first** with `make import-dry-run`: the same checks and counts, then a rollback.
- **Deleted or unpublished in WordPress?** The row takes WordPress's status (or `removed`) and disappears from the site. It's never deleted.
- **Editors' changes survive.** `short_description` is set only when a brand is first imported.
- **Least privilege.** The importer's MariaDB user can read the five content tables and only the `ID` and `display_name` columns of `wp_users`, so it can't read password hashes or emails.
- **At 100x** (about 7,000 posts) the same design holds. Reads are keyset-paginated inside one consistent snapshot. At larger scale, per-batch lookups and bulk upserts would replace the in-memory comparison (ADR 0026).

To run it from the host instead (MariaDB is bound to `127.0.0.1:3307`):

```bash
cd main-app
DJANGO_SECRET_KEY=dev MAIN_DB_PASSWORD=brandreviews WP_IMPORT_DB_PASSWORD=wp_import \
  uv run manage.py import_wp --dry-run
```

### Tests and checks

The tests use the compose Postgres on `127.0.0.1:5433`, so start it first (`make up`, or `docker compose up -d main-db`).

```bash
cd main-app
uv run pytest               # or `make test` from the repo root
uv run mypy .
uv run ruff check . && uv run ruff format --check .
```

One test runs the real import against the WordPress MariaDB, checking the counts and the computed ratings. It skips itself when MariaDB isn't reachable.

### Modeling decisions

- **Four tables, not posts + postmeta:** `Industry`, `Brand`, `Review` and `Reviewer`, with real foreign keys and check constraints. Every imported row keeps its WordPress id under a unique constraint.
- **Rating: stored and derived.** `average_rating` and `review_count` are computed from published reviews and stored at the end of each import, so sorting is cheap (ADR 0019). WordPress's own `average_rating` is kept as `legacy_average_rating` for audit, because it was too high for 4 of 5 brands (Acme: 4.2 in WordPress, 3.92 from its 12 reviews).
- **Reviewers:** a thin `Reviewer` row (WordPress user id, display name, and a nullable auth-service id for later), plus name and location snapshots on each review. The same person reviewed from different cities (ADR 0020).
- **Postmeta:** 10 rows per brand, not ~30. Four ACF values and two Yoast fields became typed columns, and the ACF field-key pointers were dropped. An untriaged key stops the import (ADR 0021).
- **Industry is a foreign key.** Every brand has exactly one, and the import stops if that changes (ADR 0026).
- **Content:** sanitized once at import with nh3. The raw HTML is kept for re-cleaning, and templates can't use `|safe` (a test enforces it). `website_url` must be http(s), checked in Python and by a database constraint.

**AI defaults accepted** (ADR 0026, items 5–10): skipping unchanged rows by comparing stored values instead of a hash column; any bad row stops the run instead of being skipped; function views; no `/brand/`, `/review/` or `/about/` pages yet, so the nav shows only Home; no `django.contrib.auth` or admin in the main app.

## Brand listing API (Pillar 2)

`GET /api/brands/` serves the data behind `<BrandList />`: published brands as cards, 12 per page by default. It's public and JSON only.

```bash
curl 'http://localhost:8000/api/brands/?industry=finance&industry=telecom&ordering=-review_count&page_size=2'
```

| Parameter | Values | Default |
|---|---|---|
| `industry` | An industry slug. Repeat it for several (`?industry=a&industry=b`), meaning any of them; at most 10 | All industries |
| `ordering` | `-average_rating`, `average_rating`, `-review_count`, `review_count` | `-average_rating` |
| `page_size` | 1–50 | 12 |
| `page` | 1, 2, … | 1 |

The response is DRF's page envelope. Each row has what a card needs:

```json
{
  "count": 5,
  "next": "http://localhost:8000/api/brands/?page=2&page_size=2",
  "previous": null,
  "results": [
    {
      "slug": "acme-insurance",
      "name": "Acme Insurance Co.",
      "industry": {"slug": "insurance", "name": "Insurance"},
      "average_rating": 3.92,
      "review_count": 12,
      "short_description": "Acme Insurance is a long-running general-lines insurer…",
      "top_review": {
        "slug": "umbrella-policy-was-easy-to-add",
        "title": "Umbrella policy was easy to add",
        "rating": 5,
        "reviewer_name": "Sarah K.",
        "snippet": "Added a $1M umbrella policy. The process was completely painless…"
      }
    }
  ]
}
```

- **Ratings** are computed from published reviews (ADR 0019). `average_rating` is a JSON number, or `null` for a brand with no reviews; such brands sort last in both directions. Every ordering ends in `id`, so pages never repeat or skip a brand.
- **The top review** is the brand's highest-rated published review, then the newest, then the last added. A 3-star brand still quotes its best review; the review closest to the average was the alternative (ADR 0027). The `snippet` is plain text, cut to 160 characters.
- **Errors.** An unknown `ordering`, an unknown industry slug or a `page_size` outside 1–50 gets a 400 with a message per parameter, for example `{"ordering": ["\"name\" is not a valid choice."]}`. An empty `ordering` or `page_size` counts as a bad value, not as "use the default"; a repeated one uses its last value. `page` follows DRF: empty means 1, `last` means the last page, and anything else that isn't a page number, or is past the end, gets a 404. Parameter names the API doesn't know are ignored, so a newer client keeps working against an older server.
- **Caching.** Responses carry an ETag and `Cache-Control: public, no-cache`, so a repeat request for an unchanged page gets a 304. There's no server-side cache.
- **Cost.** A page is three queries whatever its size (count, brands, top reviews), plus one to check the industry slugs when filtering. Tests pin this.
- **Compatibility.** The URL has no version. Changes are additive only; a breaking change would add `/api/v2/brands/` and keep this one until clients move.

**The contract with the frontend** (ADR 0010): a pytest test writes real responses to [contracts/brand-list.example.json](contracts/brand-list.example.json). It has one case per shape the UI must handle: rows with every field set, an unrated brand, markup-like text in a snippet, first and last pages, an empty page, a 400 and a 404. The test fails when the API drifts from the committed file. After an intended change, run `make contracts` and commit the result. Pillar 3's Vitest test parses the same file with the Zod schema.

**AI defaults accepted** (ADR 0027, items 7–9):
- the query serializer is the only parser of `page_size`, so DRF can't clamp a value the serializer rejected;
- ETag revalidation instead of a server-side cache;
- no throttling in the app, because DRF's is per process and not a security control.

## The WordPress source site

Self-contained, reproducible WordPress site used as the migration source.

The site is a small consumer-reviews directory: **brands** with profile pages plus user-submitted **reviews** linked to each brand. Two custom post types, one taxonomy, ACF fields, Yoast SEO metadata.

### Quick start

```bash
cp .env.example .env
make up
```

After ~20 seconds:

- Public site: <http://localhost:8080>
- WP admin:    <http://localhost:8080/wp-admin> (`admin` / `admin`)
- phpMyAdmin:  <http://localhost:8081>
- REST root:   <http://localhost:8080/wp-json/wp/v2/>
- Main app:    <http://localhost:8000> (empty until `make import`)

The DB is auto-imported from `db/dump.sql` on first boot. No manual setup required for candidates.

### Stack

| Service     | Image                            | Port  | Purpose                                |
|-------------|----------------------------------|-------|----------------------------------------|
| `db`        | `mariadb:11`                     | 127.0.0.1:3307 | Database; auto-imports `db/dump.sql` and creates the read-only import user |
| `wordpress` | `wordpress:6.9-php8.3-apache`    | 8080  | WP + Apache + PHP                      |
| `wpcli`     | `wordpress:cli-php8.3`           | -     | Helper for re-seeding / dumping        |
| `phpmyadmin`| `phpmyadmin:5`                   | 8081  | Optional DB browser                    |
| `main-db`   | `postgres:18-alpine` (by digest) | 127.0.0.1:5433 | The main app's own database |
| `main-app`  | built from `main-app/`           | 8000  | Django app (gunicorn), non-root, read-only filesystem |
| `wp-import` | built from `main-app/`           | -     | One-off WordPress import (`make import`) |

### What's committed

```
docker-compose.yml          # the stack
.env.example                # config defaults
Makefile                    # make targets
db/dump.sql                 # seeded database snapshot
db/initdb/                  # MariaDB init script for the read-only import user
contracts/                  # API responses the frontend's schema is tested against
main-app/                   # the Django app (Pillar 1)
scripts/seed.sh             # bootstrap script (install + plugins + seed)
wp-content/plugins/         # WP default plugins + ACF + Yoast (committed for offline reproducibility)
wp-content/mu-plugins/
  cpt.php                   # registers `brand` and `review` CPTs and `industry` taxonomy
  acf-fields.php            # registers ACF field groups in code
wp-content/themes/
  consumer-reviews/         # custom theme used by the site
```

WP core files and the default themes (e.g. twentytwentyfour) live inside the `wp_files` named volume and are recreated from the image on first boot. Only the custom `consumer-reviews` theme is committed to the repo.

### Make targets

```
make up         # start db + wordpress + phpmyadmin + main-db + main-app
make down       # stop containers (keeps volumes)
make reset      # stop AND wipe volumes (next 'up' re-imports dump.sql)
make logs       # tail wordpress + db
make wp ARGS="plugin list"   # run wp-cli inside the stack
make bootstrap  # full re-seed: WP core install + plugin install + content seed
make dump       # export the current DB to db/dump.sql
make status     # show running services
make import     # import WordPress content into the main app (safe to re-run)
make import-dry-run  # same checks and counts, then roll back
make wp-import-user  # create the read-only import user on an existing db volume
make test       # run the main app's tests
```

### Rebuilding the dump from scratch

If you change the schema or seed data:

```bash
make reset
make up
make bootstrap
make dump
git add db/dump.sql wp-content/plugins
git commit -m "Refresh seed data"
```

`make bootstrap` is idempotent enough to re-run, but the cleanest path is reset → up → bootstrap → dump.

### Content model

**`brand` CPT** at `/brand/<slug>/`
- Standard fields: title, content (body), featured image (optional)
- ACF fields: `website_url`, `founded_year`, `headquarters`, `average_rating`
- Taxonomy: `industry`
- Yoast: `_yoast_wpseo_title`, `_yoast_wpseo_metadesc` in postmeta

**`review` CPT** at `/review/<slug>/`
- Standard fields: title, content (review body), post_author (mapped to a real WP user)
- ACF fields: `rating` (1-5), `reviewer_name`, `reviewer_location`, `brand` (post object → brand id)

Seeded volume: 5 brands (one per industry), 60 reviews (12 per brand) authored by 8 reviewer users, 3 static pages (Home/About/Contact), 1 admin user.

### Theme

The active theme is a custom one at `wp-content/themes/consumer-reviews/` (committed to the repo). It renders:

- Homepage with featured brands and recent reviews
- Brand archive (`/brand/`) — card grid
- Single brand page (`/brand/<slug>/`) — hero with industry badge, star rating, website / founded / HQ metadata, body content, and full list of customer reviews
- Review archive (`/review/`) — paginated list
- Single review (`/review/<slug>/`) — back-link to brand, star rating, reviewer name/location, body
- Page template for About / Contact / Home pages

The theme is intentionally small (~10 PHP files + one stylesheet) and is meant to show candidates what the data renders as. They are not expected to clone the theme — just to migrate the underlying data.

### Endpoints worth knowing

- `/wp-json/wp/v2/brands` — list brands (note: `rest_base` is `brands` even though post type is `brand`)
- `/wp-json/wp/v2/brands/<id>` — single brand with ACF fields under `acf`
- `/wp-json/wp/v2/reviews` — list reviews
- `/wp-json/wp/v2/industry` — taxonomy terms
- `/wp-json/wp/v2/users` — reviewer users
- `/wp-json/wp/v2/pages` — static pages

ACF fields are exposed natively via `show_in_rest: true` set in `wp-content/mu-plugins/acf-fields.php`.

### Notes for the maintainer

- The `wp-content/plugins/advanced-custom-fields/` and `wp-content/plugins/wordpress-seo/` plugin code is GPL and committed to the repo so candidates don't need internet on first boot.
- `wp-content/plugins/akismet/` and `hello.php` are WP defaults — left in place but inactive.
- The site URL is hardcoded as `http://localhost:8080` in the dump (in `wp_options.siteurl` and `home`). Changing the port requires a search/replace in `db/dump.sql` before commit, or just override via `WP_HOME` / `WP_SITEURL` constants.
- `_yoast_wpseo_*` postmeta is seeded for brand posts only.
