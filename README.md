# Brand Reviews: WordPress → Django migration

This repository holds a WordPress → Django migration challenge ([CHALLENGE.md](CHALLENGE.md)) and the work on it. The WordPress site is the migration source. The deliverables are:
- a Django app;
- a REST API;
- a React `<BrandList />` component;
- an SCSS source tree;
- a separate auth service;
- a shared Python library.

## Project status (2026-11-09)

**Pillars 1–3 (the Django app, its brand listing API and the React `<BrandList />`) are built, and the SCSS tree (Pillar 4) has every block, checked against `reference/theme.css`. The Docker build compiles both, and Django serves them: every page uses the theme, and `/brand/` hosts the component. The auth service (Pillar 5) runs in its own container with its own database: it imports the WordPress users, logs them in and publishes its signing key. The shared library (Pillar 6) holds the token contract: the auth service mints through it, and the main app uses it to protect the editor-only `PATCH /api/brands/<slug>/`.** Every design decision is researched, decided and recorded before code is written, so each line can be traced to a reason.

### Done

- **Pillar 1: Django app** in [main-app/](main-app/): models, the re-runnable WordPress import, and the homepage, brand and review pages. See [Main app](#main-app-pillar-1) below.
- **Pillar 2: `GET /api/brands/`**: filtered, sorted and paginated brand cards, plus a contract fixture for the frontend. See [Brand listing API](#brand-listing-api-pillar-2) below.
- **Pillar 3: `<BrandList />`** in [frontend/](frontend/): the React component, its tests, a dev page, and the part of the SCSS tree it needs. See [`<BrandList />`](#brandlist--pillar-3) below.
- **Pillar 4: the SCSS tree** in [frontend/scss/](frontend/scss/): tokens, tools and every block the pages and the component use, with a test that compares the output with `reference/theme.css`. The image's Node stage builds it and the component, and `/brand/` mounts the component. See [SCSS](#scss-pillar-4) below.
- **Pillar 5: the auth service** in [auth-service/](auth-service/): users imported from WordPress, `reader` and `editor` roles, `POST /api/token/` and the JWKS. See [Auth service](#auth-service-pillar-5) below.
- **Pillar 6: the shared library** in [shared-lib/](shared-lib/): `brandreviews-authz`, which verifies tokens and checks scopes and is installed into both services. It has its own tests, which need neither Django project. The main app's editor-only `PATCH /api/brands/<slug>/` uses it. See [Shared library](#shared-library-pillar-6) below.
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
- **Decision records.** [docs/adr/](docs/adr/README.md) holds 35 records (0000–0034). Each gives the context, the options that lost and why, and when to revisit. Records are never rewritten: changed decisions are superseded, and factual errors are corrected in a linked record. Decided so far:
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
    - a 7-day dependency cooldown with approved security exceptions;
    - pnpm hardening: strict release age, no trust downgrades, no install scripts.
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
  - **Pillar 3:**
    - filter, sort and page state in the URL, read with `useSyncExternalStore`, no router;
    - a small fetch hook that aborts stale requests and `safeParse`s responses, no query library;
    - native controls: industry checkboxes in a fieldset, a sort `<select>`, pagination links;
    - the industry list passed in by the page (`json_script`), not fetched;
    - mounting into a Django page deferred to Pillar 4.
  - **Pillar 3/4:**
    - BEM with `l-`/`c-`/`u-` prefixes;
    - `<BrandList />` styled by a global partial;
    - Sass deprecations as build errors, plus a test on the compiled CSS, in place of stylelint;
    - `sass` pinned exactly;
    - one folder per cascade layer, role-named tokens, getters that fail the build on a typo.
  - **Pillar 4:**
    - the Sass CLI builds `theme.css` and Vite the component, both in a Node stage of the Docker build, so the runtime image has no Node;
    - `<BrandList />` mounts on a new `/brand/` page, WordPress's archive URL;
    - a test compares the output with `reference/theme.css`, declaration by declaration, and every difference has a listed reason;
    - two PRs: the blocks and the comparison first, then build, delivery and mounting.
  - **Pillar 5:**
    - EdDSA JWTs (10-minute lifetime) verified locally;
    - revocation within one token lifetime;
    - 503 when keys can't be fetched;
    - imported users get no usable password;
    - scrypt for new passwords;
    - roles are Groups, and a `Scope` model holds the token's scope strings;
    - login by username or email, one `401 invalid_credentials` for every failure;
    - per-address and per-account throttles on a shared cache, no lockout;
    - no admin: roles change with management commands;
    - the signing key is a Compose file secret, generated in the auth image;
    - this pull request is the auth service only; the `PATCH` arrives with the library.
  - **Pillar 6:**
    - `brandreviews-authz`, built with `uv_build`;
    - installed by local path;
    - a version bump required on every change;
    - this pull request is the library, both services adopting it, and the `PATCH`; the user map comes separately;
    - the auth service mints through the library's claims, profile and JWK, and a contract test verifies what it mints;
    - the `PATCH`: last write wins, with a log line naming the editor;
    - a strict body (`short_description` only, 1–300 characters) and a minimal reply.

### Not done yet

| Deliverable | State |
|---|---|
| The main-app import reading the auth service's user map (ADR 0020) | Not started. `make auth-map` writes the map; it gets its own pull request (ADR 0034) |
| CI | None. `make test-shared` and `make check-shared` are what it would run for the library |

### With more time

- **Performance.** Build prototypes and benchmarks to improve query performance, overall database performance and app performance.
- **Accessibility.** Test the accessibility features and run a full audit, so the site complies with the most up-to-date standard.
- **Security.** Carry on with a security audit, backed by more security tools, so security is tested exhaustively.

Time-bound: Django 5.2.19 clears the cooldown on 2026-11-10. Raise the floor to it in `main-app/` and `auth-service/` in its own change after it clears (ADR 0014).

## Main app (Pillar 1)

The Django app in [main-app/](main-app/) replaces the WordPress site: models, a re-runnable import from WordPress's MariaDB, and four server-rendered pages at the same paths as WordPress's permalinks. The image also builds the stylesheet and `<BrandList />` in a Node stage, and whitenoise serves them (ADRs 0031, 0032).

### Run it

```bash
cp .env.example .env        # once; the defaults work locally
make up                     # WordPress, MariaDB, the main app, the auth service, their Postgres
make import                 # copy WordPress content into the main app
```

Then open <http://localhost:8000>, <http://localhost:8000/brand/> (the `<BrandList />` component), <http://localhost:8000/brand/acme-insurance/> or <http://localhost:8000/review/online-portal-feels-like-2010/>. After changing the frontend or SCSS, rebuild with `docker compose up -d --build main-app`.

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

**AI defaults accepted** (ADR 0026, items 5–10): skipping unchanged rows by comparing stored values instead of a hash column; any bad row stops the run instead of being skipped; function views; no `/review/` or `/about/` pages yet (`/brand/` came with Pillar 4), so the nav shows only Home and Brands; no `django.contrib.auth` or admin in the main app.

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

**The contract with the frontend** (ADR 0010): a pytest test writes real responses to [contracts/brand-list.example.json](contracts/brand-list.example.json). It has one case per shape the UI must handle: rows with every field set, an unrated brand, markup-like text in a snippet, first and last pages, an empty page, a 400 and a 404. The test fails when the API drifts from the committed file. After an intended change, run `make contracts` and commit the result. `<BrandList />`'s Vitest test parses the same file with the Zod schema.

**AI defaults accepted** (ADR 0027, items 7–9):
- the query serializer is the only parser of `page_size`, so DRF can't clamp a value the serializer rejected;
- ETag revalidation instead of a server-side cache;
- no throttling in the app, because DRF's is per process and not a security control.

## `<BrandList />` (Pillar 3)

The React component in [frontend/src/brand-list/](frontend/src/brand-list/) lists brands from `GET /api/brands/`, with an industry filter, a sort control and pagination. It's client-only React 19, built with Vite 8 (ADR 0011).

### Run it

In the app, it's at <http://localhost:8000/brand/> after `make up` and `make import`; the Docker build compiles it. To work on it with hot reload, you need Node 24.15+ and pnpm (the version is pinned in `package.json`), with the main app running:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm dev                      # http://localhost:5173, /api proxied to localhost:8000
```

The dev page ([frontend/index.html](frontend/index.html)) imitates the Django page that hosts the component: a root element with `data-api-url`, and the industries in a `json_script` block. On Django, the `/brand/` template renders both, and `{% vite_entry %}` reads Vite's manifest to load the hashed bundle (ADR 0032).

### Tests and checks

```bash
cd frontend
pnpm test                     # Vitest: contract, URL functions, component, mount, compiled CSS
pnpm typecheck
pnpm build                    # dist/ plus .vite/manifest.json for a Django template tag
```

The component tests drive it through roles and the keyboard, with `fetch` stubbed, so responses can arrive out of order. They cover loading, empty, error and Retry, the URL and Back button, a 404 past the last page, and focus, and run axe in each state. Colour contrast, target size and screen-reader announcements need a real browser; jsdom can't check them.

### How it works

- **State lives in the URL** (`?industry=finance&industry=telecom&ordering=review_count&page=2`, the API's names), so a view can be shared and Back works. Filters and pages push a history entry; repeated sort changes share one. Unknown values are dropped and the URL corrected in place. Other parameters, such as `utm_source`, are kept.
- **Fetching:** a change aborts the request in flight, so a slow old response can't replace a newer one. Responses are parsed with the Zod schema, and anything unexpected becomes the error state, with Retry.
- **Loading:** skeleton cards on first load, then the previous results dimmed while the next ones load. One polite status region announces counts after a change ("3 brands. Telecom. Sorted by highest rated. Page 1 of 1."), not on page load.
- **Accessibility:** native controls only: checkboxes in a fieldset inside `<search>`, a labelled `<select>`, links for pages. Focus stays put on filter and sort changes, and moves to the results heading when the focused button disappears (Clear filters, Retry, a page link). Each card is one tab stop.
- **Responsive:** the grid reflows down to 320px without a media query, and the filters stack in narrow slots through a container query, so the component fits wherever Django puts it.

**AI defaults accepted** (ADR 0028, items 6–14; ADR 0030, item 6):
- `page_size=12` sent explicitly;
- `aria-label` names on pagination links;
- announcements start only after the first change;
- a page past the end goes back to page 1;
- a 10-second timeout, with one message per error kind;
- stars drawn like the server's;
- one stretched link per card, with the top review as a quote without its own link;
- the build entry set under `build.rolldownOptions`;
- full Zod rather than `zod/mini`;
- accessibility fixes to the WordPress CSS: no forced root font size, a focus ring, motion only when not reduced, a 3:1 border on the select.

It's styled by the shared SCSS tree; see [SCSS](#scss-pillar-4).

## SCSS (Pillar 4)

The SCSS source for the whole site is in [frontend/scss/](frontend/scss/). One stylesheet, `theme.css`, serves both the Django pages and `<BrandList />`, so a brand card looks the same in both (ADR 0023).

### Compile it

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm scss                     # scss/theme.scss → dist-css/theme.css
pnpm test                     # includes the architecture and equivalence checks
```

`pnpm scss` runs `sass --no-source-map --no-error-css --fatal-deprecation=1.107.0`: every deprecation is an error, and a failed compile writes no CSS. The Vite dev server compiles with the same policy.

In Docker, none of this is needed: the main app's image compiles `theme.css` in a Node stage, and every page links it (ADRs 0031, 0032). To run Django outside Docker, run `pnpm scss` and `pnpm build` first; the settings read the output from `frontend/dist-css/` and `frontend/dist/`.

### Structure

One folder per cascade layer, in the order `_layers.scss` declares them:

| Folder | Emits CSS | Holds |
|---|---|---|
| `tokens/` | Only `_custom-properties.scss` (`:root`) | Sass maps: colors (private palette, public roles), type, space, radius, shadow, motion, layout, breakpoints |
| `tools/` | No | Getters such as `t.color("text-muted")`, which return the custom property and stop the build on an unknown name; mixins `below()`, `container-below()`, `motion-safe`, `focus-ring`, `surface`, `visually-hidden` |
| `base/` | `@layer reset, base` | Box sizing, body type, links, focus ring |
| `layout/` (`l-`) | `@layer layout` | `l-container`, `l-section`, `l-grid` |
| `components/` (`c-`) | `@layer components` | One block per file: site header, nav and footer, heroes, card, badge, stars, review, byline, panel, prose, pagination, `<BrandList />`'s parts |
| `utilities/` (`u-`) | `@layer utilities` | `u-visually-hidden`, `u-skip-link` |

Later layers win regardless of specificity, so a utility beats a component without `!important`. Values that recur are tokens; one-off WordPress values stay in their block, marked `WP value, off-scale`.

**Adding a component:** one partial in `components/` with one `@layer components` block, `@use "../tools" as t;` for tokens, and one `@use` line in `components/_index.scss`. Name classes `c-block__element--modifier`. The tests enforce the rest.

### What the tests check

- **`scss/theme.test.ts`** (architecture): one layer-order statement first, every rule in a layer, prefixed BEM class names, raw colors only in the tokens layer, no `!important`, no ids and at most two classes or states per selector, and that a token typo fails the build (ADRs 0023, 0030). It stands in for stylelint, whose SCSS setup pulls a hijacked dependency chain.
- **`scss/equivalence.test.ts`** (equivalence): compiles `theme.scss` and compares every declaration in `reference/theme.css`. It resolves custom properties on both sides and maps selectors through [scss/wp-mapping.ts](frontend/scss/wp-mapping.ts). It fails on an unmapped WordPress selector, on a difference with no listed reason, or on a listed reason that no longer applies (ADR 0031). The intended differences are:
  - the `html` rule is folded into `body`;
  - no forced 16px root font size;
  - an intrinsic grid column that needs no mobile media query;
  - the about page's margin moves to its section.

  Hover motion now waits for `prefers-reduced-motion: no-preference`.

### WordPress → BEM

The full table is `WP_TO_BEM` in [scss/wp-mapping.ts](frontend/scss/wp-mapping.ts). The main renames:

| WordPress | Ours |
|---|---|
| `.container`, `.grid`, `.section`, `.section h2`, `.section-header` | `.l-container`, `.l-grid`, `.l-section`, `.l-section__title`, `.l-section__header` |
| `.brand-body`, `.reviews-section` | `.l-section--article`, `.l-section--reviews` |
| `.site-header`, `.site-title`, `.site-nav a`, `.site-footer` | `.c-site-header`, `.c-site-header__title`, `.c-site-nav__link`, `.c-site-footer` |
| `.hero h1`, `.hero p` | `.c-hero__title`, `.c-hero__lead` |
| `.brand-hero`, `.brand-meta`, `.brand-meta strong` | `.c-brand-hero`, `.c-brand-facts`, `.c-brand-facts__label` |
| `.review-hero .brand-link` | `.c-review-hero__back` |
| `.card h3 a`, `.card .meta`, `.card .excerpt` | `.c-card__link`, `.c-card__meta`, `.c-card__excerpt` |
| `.stars .star-empty`, `.stars .rating-value`, `.badge` | `.c-stars__star--empty`, `.c-stars__value`, `.c-badge` |
| `.review-item`, `.review-byline`, `.review-body` | `.c-review`, `.c-byline` + `.c-review__byline`, `.c-review__body` |
| `.brand-body .content`, `.page-body` | `.c-panel--article` + `.c-prose`, `.c-panel` |
| `.pagination .page-numbers.current` | `.c-pagination__link[aria-current="page"]` |

WordPress's seven inline styles became modifiers (`l-section--alt`, `c-hero--compact`) or elements (`c-brand-hero__count`, `c-review-hero__byline`), because the CSP allows no inline styles (ADR 0017).

**AI defaults accepted** (ADR 0031, items 5–15):
- `motion-guarded` and `initial` reported as their own statuses, not as deviations;
- a `surface` mixin rather than a shared class;
- `c-byline` as its own block;
- `c-panel` + `c-prose` for long-form content;
- the about page's margin on the section;
- new color roles, a `2xl` font size and two letter-spacing tokens;
- underlined links in prose, a skip link, a stretched title link on review cards;
- WordPress's unstyled `.meta` leaks fixed with `c-empty` and a `<dl>` for brand facts;
- unstyled `l-page` and `l-main` hooks;
- the specificity counter no longer counts `:not()` itself;
- one shared compile helper for the tests.

**AI defaults accepted** for delivery (ADR 0032):
- pnpm through Corepack;
- Node 24.22.1, the latest security release, past the cooldown;
- a named Compose build context shared by both services that build the image;
- no type check in the image;
- the Vite manifest read from disk, not served;
- whitenoise's defaults, with no Brotli;
- no `modulepreload` links;
- a `<noscript>` note on `/brand/`;
- every industry in the filter, even one with no brands;
- Zod without its JIT compiler, so parsing never compiles code from strings, which the CSP forbids.

## Auth service (Pillar 5)

The Django project in [auth-service/](auth-service/) owns users, passwords and roles, and mints the access tokens. It has its own container and its own Postgres. The main app never gets its database credentials and stores only each user's random `external_id` (ADRs 0006, 0020, 0033).

### Run it

```bash
make up                     # also generates secrets/jwt_ed25519.pem the first time
make auth-import            # copy the 9 WordPress users (safe to re-run)
docker compose exec auth-service python manage.py changepassword admin
```

Imported users have no usable password (ADR 0024), so set one for each account you want to log in with. `changepassword` prompts and runs the password validators (at least 12 characters).

### Get a token

```bash
curl -s -X POST http://localhost:8001/api/token/ \
  -H 'Content-Type: application/json' \
  -d '{"username": "admin", "password": "<the password you set>"}'
```

```json
{"access_token": "eyJhbGciOiJFZERTQSIs…", "token_type": "Bearer", "expires_in": 600, "scope": "brands:read brands:write"}
```

- `username` also accepts the email address, in any case, as WordPress does.
- Every failure (unknown user, wrong password, inactive, no password set) returns the same `401 {"error": "invalid_credentials"}`.
- Too many attempts return `429`: 20 per minute per address, 5 per minute per account.
- The token is an EdDSA JWT (`typ: at+jwt`) that lives 10 minutes. It carries `sub` (the user's `external_id`), `scope`, `iss`, `aud: brands-api`, `client_id`, `iat`, `nbf`, `exp` and `jti`, and no username, email or role (ADR 0016).
- The public key is at <http://localhost:8001/.well-known/jwks.json>. The main app verifies tokens locally against it and never calls the auth service per request.

### Call the protected endpoint

`PATCH /api/brands/<slug>/` changes a brand's short description, and only a token with the `brands:write` scope (the `editor` role) can call it. The imported `admin` is an editor.

```bash
TOKEN=$(curl -s -X POST http://localhost:8001/api/token/ \
  -H 'Content-Type: application/json' \
  -d '{"username": "admin", "password": "<the password you set>"}' \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])')

curl -s -X PATCH http://localhost:8000/api/brands/acme-insurance/ \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"short_description": "A general-lines insurer in 38 US states."}'
```

```json
{"slug": "acme-insurance", "short_description": "A general-lines insurer in 38 US states."}
```

| Request | Response |
|---|---|
| No token, another scheme, or a bad or expired token | `401`, with `WWW-Authenticate: Bearer realm="api"` |
| A valid token without `brands:write` (a `reader`) | `403` |
| The auth service's keys can't be fetched | `503`: the token may be fine, so retry later (ADR 0016) |
| An unknown or unpublished brand | `404`, but only after the token checks out |
| A body that isn't exactly `{"short_description": "<1–300 characters>"}` | `400`, with DRF's field map |

- **Verified locally.** The main app checks the token against the auth service's JWKS, cached for 5 minutes in each gunicorn worker, and never calls the auth service per request. Pages and `GET /api/brands/` work while the auth service is down.
- **Last write wins.** Each edit is logged as `brand edited slug=… sub=… jti=…`, which is how an overwritten edit is traced (ADR 0034).
- **Plain text.** The value is trimmed and never treated as HTML. The listing and the brand cards show it straight away.

### Roles

`reader` grants `brands:read`; `editor` grants `brands:read brands:write`. The import maps WordPress's administrator to `editor` (not superuser) and subscribers to `reader`. The main app checks scopes, never role names.

```bash
docker compose exec auth-service python manage.py grant_role sarah_k editor
docker compose exec auth-service python manage.py revoke_role sarah_k editor
```

A change shows up in the user's next token, so within 10 minutes. There's no admin site: it would bring sessions, cookies, CSRF and a second login form into the service that holds the passwords (ADR 0033).

### The user import

- **Re-running is safe.** Users upsert on their WordPress id. A re-run follows a login or email changed in WordPress, and never touches a password, a role or `is_active` set here since. A second run reports `0 created, 0 updated, 9 unchanged`.
- **Preview first** with `make auth-import-dry-run`.
- **Least privilege.** The importer's MariaDB user can read one view: each user's id, login, email and `wp_capabilities` value. It can't read password hashes, or the session tokens WordPress keeps in `wp_usermeta`. On a MariaDB volume created before this change, run `make wp-import-user` once.
- **For the main app:** `make auth-map` writes `secrets/user-map.json`, which maps WordPress ids to `external_id`s with no names, emails or hashes (ADR 0020).

### The signing key

`make auth-key` (run by `make up` when the key is missing) generates an Ed25519 key inside the auth image, so it needs only Docker. The file belongs to the container's user (uid 10001) with mode `0400`, and `secrets/` is gitignored. If the key is missing or wrong, gunicorn refuses to start. To rotate it, follow the runbook in ADR 0033. Rotating logs everyone out within 5 minutes.

### Tests and checks

The tests use the compose Postgres on `127.0.0.1:5434` (`docker compose up -d auth-db`).

```bash
cd auth-service
uv run pytest               # or `make test-auth` from the repo root
uv run mypy .
uv run ruff check . && uv run ruff format --check .
```

One test imports the real WordPress users. It skips itself when MariaDB isn't reachable.

**AI defaults accepted** (ADR 0033, items 9–18): a MariaDB view instead of column grants; the key generated in the image and owned by uid 10001; the key loaded in `wsgi.py`, so only the web server needs it; a re-import that follows logins and emails but never passwords or roles; a role-less user gets an empty-scope token; no `WWW-Authenticate` header on the 401; the throttle rates; the clickjacking middleware; the main app reading the user map deferred to Pillar 6.

## Shared library (Pillar 6)

[shared-lib/](shared-lib/) is `brandreviews-authz`, the token contract both services share (ADRs 0016, 0025, 0034). Its [README](shared-lib/README.md) lists each module and which service uses it.

- **In:**
  - the token profile (`alg`, `typ`, required claims);
  - the claims dataclass;
  - the scope names;
  - the error types;
  - the JWK format and the key providers;
  - the verifier;
  - a DRF authentication class and permission factory.
- **Out:**
  - signing (only the auth service may mint tokens);
  - the role → scope map (the auth service's data);
  - models and settings.
- **The auth service** builds `AccessClaims`, signs `to_payload()` with the profile's `alg` and `typ`, and publishes `public_jwk()`. A contract test verifies what it mints with the library's `TokenVerifier`, so the issuer and the verifier can't drift apart unnoticed.
- **The main app** subclasses `BearerAuthentication` to hand it a verifier built from its settings, and guards the `PATCH` with `require_scopes(scopes.BRANDS_WRITE)`.
- **The core is framework-free.** Ruff bans Django and DRF imports outside `drf.py`, and a test imports the core in a fresh interpreter and checks neither loaded.

### Run its tests

No Django project, database or network is needed. The JWKS tests run a real HTTP server on `127.0.0.1`.

```bash
make test-shared            # pytest, mypy strict and Ruff, in shared-lib/
```

### How a new version reaches each service

Both services install it from its directory as a uv path source (`{ path = "../shared-lib", editable = true }`), so uv never looks the name up on PyPI. Docker builds pass `shared-lib/` as a named build context and install it with `--no-editable`, so the runtime image holds a copy and no source.

1. Change `shared-lib/src/`, add a `CHANGELOG.md` entry, and run `uv version --bump <patch|minor|major>` in `shared-lib/`.
2. Run `uv lock` in `main-app/` and `auth-service/`. The version bump is what makes each service re-lock: `uv.lock` records a path source's version, not its code.
3. Run both services' tests, and commit the library and both lockfiles together. `make check-shared` fails if `src/` changed without a bump, or if a lockfile is stale.
4. Deploy each service on its own schedule. A breaking token change goes expand → migrate → contract: verifiers accept old and new, then the auth service switches, then, one token lifetime later, a major release drops the old shape. No step needs both services deployed together.

Never run `uv lock --no-sources` or pip against the services: both would look the name up on PyPI, where anyone can register it (ADR 0025).

**AI defaults accepted** (ADR 0034, items 5–18):
- seven small modules, with no separate `permissions.py`;
- one `TokenRejected` with a reason, instead of nine subclasses;
- header checks before any key lookup;
- loading the key set first to tell 503 from 401;
- a table of malformed tokens instead of Hypothesis;
- one dev group;
- the DRF adapter's details: a plain `Bearer realm="api"` challenge and none on the 403;
- the RFC 8037 test moved to the library;
- a lazily built verifier, one per process;
- `PATCH` edits published brands only, checks credentials before the lookup, and refuses numbers;
- named build contexts with `--no-editable`;
- the version-bump script;
- version 1.0.0;
- `<4` for DRF in the `[drf]` extra.

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
main-app/                   # the Django app (Pillars 1 and 2)
frontend/                   # <BrandList /> (Pillar 3) and the SCSS tree (Pillar 4)
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
make up         # start db + wordpress + phpmyadmin + main app + auth service (and their Postgres)
make down       # stop containers (keeps volumes)
make reset      # stop AND wipe volumes (next 'up' re-imports dump.sql)
make logs       # tail wordpress + db
make wp ARGS="plugin list"   # run wp-cli inside the stack
make bootstrap  # full re-seed: WP core install + plugin install + content seed
make dump       # export the current DB to db/dump.sql
make status     # show running services
make import     # import WordPress content into the main app (safe to re-run)
make import-dry-run  # same checks and counts, then roll back
make wp-import-user  # create the read-only import users on an existing db volume
make test       # run the main app's tests
make auth-key   # generate the auth service's signing key (once; `make up` does it)
make auth-import     # import WordPress users into the auth service (safe to re-run)
make auth-import-dry-run  # same checks and counts, then roll back
make auth-map   # write secrets/user-map.json for the main app
make test-auth  # run the auth service's tests
make test-shared     # run the shared library's tests, mypy and Ruff
make check-shared    # check the library's version was bumped and both services re-locked
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
