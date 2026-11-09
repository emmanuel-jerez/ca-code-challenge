# Brand Reviews: WordPress → Django migration

This repository holds a WordPress → Django migration challenge ([CHALLENGE.md](CHALLENGE.md)) and the work on it. The WordPress site is the migration source. The deliverables are:
- a Django app;
- a REST API;
- a React `<BrandList />` component;
- an SCSS source tree;
- a separate auth service;
- a shared Python library.

## Project status (2026-11-09)

**Planning is done and no application code exists yet.** Every design decision is researched, decided and recorded before code is written, so each line can be traced to a reason.

### Done

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
- **Decision records.** [docs/adr/](docs/adr/README.md) holds 26 records (0000–0025). Each gives the context, the options that lost and why, and when to revisit. Records are never rewritten: changed decisions are superseded, and factual errors are corrected in a linked record. Decided so far:
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
    - postmeta triaged into typed columns plus two SEO fields.
  - **Pillar 2:**
    - repeated `industry` keys;
    - a closed `ordering` enum that always ends in `id`;
    - `page_size` from 1 to 50 (default 12).
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
| Pillar 1: Django app (models, re-runnable WordPress import, homepage, `/brand/<slug>/`, `/review/<slug>/`) | Not started |
| Pillar 2: `GET /api/brands/` (filter, sort, paginate) | Not started |
| Pillar 3: React `<BrandList />` | Not started |
| Pillar 4: SCSS source tree under `frontend/scss/` | Not started |
| Pillar 5: auth service (users, login, roles, JWKS) and the editor-only `PATCH /api/brands/<slug>/` | Not started |
| Pillar 6: shared library with its own tests | Not started |
| Docker Compose services for the two Django projects and their databases | Not started |
| README sections the challenge requires: running each part, getting a token, running the import and the library tests, how a library version reaches each service, and a half-page on modeling decisions and AI defaults | Not written. Each is added with the code it describes |
| CI | None |

Still open, with options in the research notes:
- whether an unknown industry slug gets 400 or an empty page;
- what the "top review" snippet is;
- the API error format, versioning and `PATCH` concurrency;
- whether the auth service has an admin;
- extra pnpm hardening.

Time-bound: Django 5.2.19 clears the cooldown on 2026-11-10. Raise the floor to it once the services have lockfiles (ADR 0014).

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

The DB is auto-imported from `db/dump.sql` on first boot. No manual setup required for candidates.

### Stack

| Service     | Image                            | Port  | Purpose                                |
|-------------|----------------------------------|-------|----------------------------------------|
| `db`        | `mariadb:11`                     | -     | Database; auto-imports `db/dump.sql`   |
| `wordpress` | `wordpress:6.9-php8.3-apache`    | 8080  | WP + Apache + PHP                      |
| `wpcli`     | `wordpress:cli-php8.3`           | -     | Helper for re-seeding / dumping        |
| `phpmyadmin`| `phpmyadmin:5`                   | 8081  | Optional DB browser                    |

### What's committed

```
docker-compose.yml          # the stack
.env.example                # config defaults
Makefile                    # make targets
db/dump.sql                 # seeded database snapshot
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
make up         # start db + wordpress + phpmyadmin
make down       # stop containers (keeps volumes)
make reset      # stop AND wipe volumes (next 'up' re-imports dump.sql)
make logs       # tail wordpress + db
make wp ARGS="plugin list"   # run wp-cli inside the stack
make bootstrap  # full re-seed: WP core install + plugin install + content seed
make dump       # export the current DB to db/dump.sql
make status     # show running services
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
