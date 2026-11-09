# Stack validation: compatibility, open items, unchosen pieces, weak spots

> **Corrected later (2026-11-09).** Parts of this note were superseded by the pillar research: the Django floor in §5 and the Sass compile command in §3.5: see ADRs 0014 and 0023. The text below is kept as it was written.

Researched 2026-11-09. This note builds on `stack-decisions.md`, `typing-and-validation.md` and `best-practices-2026.md`, and does not repeat them.
**Cooldown cut-off:** a version counts as safe only if it was uploaded **before 2026-11-02**.
Sources:
- Python packages: PyPI JSON (`pypi.org/pypi/<name>/<ver>/json`), giving earliest upload, classifiers, `requires_dist` and wheel filenames.
- npm packages: `npm view <pkg>@<ver> time peerDependencies engines dependencies`.
- Everything else: GitHub raw files and the GitHub API.

Claims marked *(secondary)* come from non-primary sources. Release-age policy for security fixes is out of scope (see `cooldown-vs-security-fixes.md`).

## Compatibility matrix

| Package | Latest safe (uploaded) | Newer, still in cooldown | Py 3.14 | Other compatibility | Verdict |
|---|---|---|---|---|---|
| Django | **5.2.18** (2026-10-06) | 5.2.19 (11-03, security) | Classifier ✅, pure | 5.2.8+ needed for 3.14 | ✅ |
| djangorestframework | **3.18.3** (2026-10-06) | — | Classifiers 3.10–3.15 | `django>=5.2`; classifiers Dj 5.2/6.0/6.1 | ✅ |
| PyJWT[crypto] | **2.15.1** (2026-09-28) | — | Classifiers to 3.15, pure | Extra pulls `cryptography>=3.4.0` | ✅ |
| cryptography | **50.0.2** (2026-09-30) | — | `cp311-abi3` manylinux x86_64/aarch64 + musllinux; `cp314t` | Needs `cffi>=2.0.0` (2.1.1 has cp314 wheels) | ✅ |
| nh3 | **0.3.7** (2026-08-23) | — | No classifiers. `cp38-abi3` manylinux/musllinux x86_64+aarch64, plus `cp314t` | No deps | ✅ |
| mypy | 2.4.1 (10-28); **2.3.1** (08-15) | — | cp314 wheels | See the stubs row | ⚠️ cap |
| django-stubs (+ext) | **6.1.2** (2026-10-05) | — | 3.11–3.14 | Targets Dj **6.1**, "partial" 5.2; `compatible-mypy` extra: mypy 1.13–<2.5 | ⚠️ §2.4 |
| djangorestframework-stubs | **3.18.1** (08-25) | 3.18.2 (11-02 23:46 UTC) | ✅ | `django-stubs>=6.1.0`. `compatible-mypy` extra: **mypy<2.4**. 3.18.2: `<2.5`, `django-stubs>=6.1.2` | ⚠️ until 3.18.2 clears ≈2026-11-09 23:46 UTC |
| ruff | **0.17.3** (10-27) | 0.17.4 | Classifiers to 3.15 | — | ✅ |
| drf-spectacular | **0.30.0** (2026-07-06) | — | Classifier ✅ | Classifiers Dj ≤6.0; `djangorestframework>=3.10.3` with no upper bound. **CI never runs DRF 3.18** (§2.1) | ⚠️ untested |
| pytest / pytest-django | **9.2.0** (10-27) / **4.14.0** (08-10) | — | ✅ / ✅ | pytest-django classifiers Dj 5.2/6.0 | ✅ |
| react / react-dom | **19.3.1** (2026-10-14) | — | — | `react-dom` peers `react ^19.3.1` | ✅ |
| vite | **8.3.5** (2026-10-21) | 8.3.6, 8.3.7 (+ 6.4.6/7.3.8/8.1.7/8.2.6 all on 11-09) | — | Node `^20.19 \|\| >=22.12`. Rolldown-based. Optional peers `sass`/`sass-embedded ^1.70`. ≥8.3.3 covers the Oct 2026 GHSAs ([advisories](https://github.com/vitejs/vite/security/advisories)) | ✅ **Vite 8** |
| @vitejs/plugin-react | **6.1.2** (2026-10-05) | 6.2.x, 6.3.0 | — | Peer `vite ^8.0.0`, so plugin 6 forces Vite 8 | ✅ |
| typescript | **6.0.3** (2026-04-16). `latest` tag is 7.0.2 | — | — | `typescript-eslint@8.72.1` peer `>=4.8.4 <6.1.0`. 7.0 has no JS API (see earlier note) | ✅ on 6 |
| openapi-typescript | **7.13.0** (2026-02-11) | — | — | **Peer `typescript ^5.x`, conflicts with TS 6** (§2.2) | ❌ conflict |
| zod | **4.6.7** (2026-10-12) | — | — | No deps, no peers | ✅ |
| vitest | **5.0.5** (2026-10-15) | 5.1.0 | — | Peer `vite ^6.4 \|\| ^7 \|\| ^8`. **Node `^22.12 \|\| ^24 \|\| >=26`** | ✅ |
| jsdom | **30.1.3** (2026-10-15) | 31.0.0 | — | **Node `^22.22.2 \|\| ^24.15.0 \|\| >=26`** | ✅ |
| @testing-library/react / dom / user-event | **16.3.3** / **10.4.2** / **14.6.8** | — | — | RTL peers `react ^18 \|\| ^19`, `@testing-library/dom ^10` | ✅ |
| axe-core | **4.14.0** (2026-10-05) | — | — | Deque, 4 maintainers | ✅ |
| sass | **1.107.1** (2026-10-30) | 1.108.x | — | Node ≥20.19. Optional `@parcel/watcher` has an `install` script that pnpm will flag | ✅ |

**Node:** the intersection of the engine ranges is **Node 24.15+ or 26**. Node 24 "Krypton" is LTS (24.22.2) and Node 26 "Lithium" became LTS in October 2026 ([nodejs dist index](https://nodejs.org/dist/index.json)). Node 20 is excluded by vitest 5 and jsdom 30.

**Conflicts found:**
- (1) openapi-typescript ↔ TypeScript 6 (peer dependency).
- (2) djangorestframework-stubs 3.18.1 ↔ mypy 2.4. This only applies through the `compatible-mypy` extra; the plain package has no mypy bound.
- (3) djangorestframework-stubs 3.18.x requires `django-stubs>=6.1`, so you can't fall back to django-stubs 6.0.x to get fewer 6.1-only APIs.
- (4) *Optional* `eslint-plugin-jsx-a11y@6.10.2` (last release 2024-10) peers `eslint ≤9`, which clashes with ESLint 10.14.0. If you lint, use the `eslint@9.39.5` maintenance line.

Nothing else conflicts.

## 1. Notes on the matrix

- **Compiled Python packages on 3.14:**
  - cryptography, nh3, psycopg-binary and granian all ship Linux wheels for 3.14 (abi3 or cp314), both glibc and musl.
  - **mysqlclient 2.3.0 ships no Linux wheels at all**: its cp314 wheels are Windows-only, plus an sdist (see §3.1).
- **Python packages with no 3.14 classifier:**
  - nh3: no classifiers at all.
  - PyMySQL: no version classifiers, but CI tests 3.14 and 3.15 ([test.yaml](https://github.com/PyMySQL/PyMySQL/blob/main/.github/workflows/test.yaml)).
  - gunicorn: classifiers and CI matrix stop at 3.13 ([tox.yml](https://github.com/benoitc/gunicorn/blob/master/.github/workflows/tox.yml)).
  - The `uv-only` vetting rule therefore needs explicit approval for gunicorn, as it did for django-csp.
- **PyJWT detail the earlier note left out:**
  - `jwt.decode` does **not** check the `typ` header. `PyJWS.header_typ` is only used when encoding ([api_jws.py](https://github.com/jpadilla/pyjwt/blob/2.15.1/jwt/api_jws.py)).
  - To enforce `at+jwt`, call `jwt.decode_complete(...)` and check `header["typ"] == "at+jwt"` yourself. Sign with `headers={"typ": "at+jwt"}`.
  - `PyJWKClient` uses only stdlib `urllib`, so no `requests` dependency comes in ([jwks_client.py](https://github.com/jpadilla/pyjwt/blob/2.15.1/jwt/jwks_client.py)).

## 2. Open items from earlier notes

### 2.1 drf-spectacular with DRF 3.18: **not tested upstream, no known breakage**

- **Not in CI.** The `tox.ini` envlist tops out at `py314-django5.2-drf3.16` and `django6.0-drf3.17` ([tox.ini](https://github.com/tfranzel/drf-spectacular/blob/master/tox.ini)). The `drfmaster` envs exist, but `helper/github-ci-vars.py` drops every env containing `master` from the matrix ("temp remove the optional targets") ([source](https://github.com/tfranzel/drf-spectacular/blob/master/helper/github-ci-vars.py)). So **DRF 3.18 is not tested in any form.**
- **Dormant.** The last commit is the 0.30.0 version bump on 2026-07-06, and there's been nothing since ([commits](https://github.com/tfranzel/drf-spectacular/commits/master)). There is one maintainer (tfranzel).
- **DRF 3.18 changes that could matter:**
  - It drops Django < 5.2.
  - Errors from list serializers (`many=True`) are now dicts.
  - It replaces `cc_delim_re` ([release notes](https://github.com/encode/django-rest-framework/blob/main/docs/community/release-notes.md)). spectacular doesn't model error bodies by default.
- **Issues:**
  - No issue reports DRF 3.18 breakage. Search "3.18" returns only [#1518](https://github.com/tfranzel/drf-spectacular/issues/1518), a Django 6.1 `cc_delim_re` ImportError, closed and irrelevant on 5.2.
  - Open regression [#1538](https://github.com/tfranzel/drf-spectacular/issues/1538): since 0.30.0, `allow_blank` string fields that also have `format`/`pattern`/`minLength` are emitted as a `oneOf` that rejects `""`. A plain `CharField(max_length=…, allow_blank=True)` for the PATCH body isn't affected.
- DRF's own docs mark built-in OpenAPI generation **deprecated** and recommend drf-spectacular ([schemas.md](https://github.com/encode/django-rest-framework/blob/main/docs/api-guide/schemas.md)). There is no first-party alternative.
- **Cost:** 9 runtime packages (`drf-spectacular, uritemplate, PyYAML, inflection, jsonschema, attrs, referencing, jsonschema-specifications, rpds-py` (Rust)) ([jsonschema](https://pypi.org/pypi/jsonschema/json)).

### 2.2 openapi-typescript on TypeScript 6: **peer conflict, unreleased fix, maintainer bandwidth low**

- **Peer conflict.** 7.13.0 peers `typescript ^5.x`, and it's still the only 7.x release since February.
- **Competing unmerged fixes.** Three open PRs try to fix this:
  - [#2818](https://github.com/openapi-ts/openapi-typescript/pull/2818) widens the peer to `^5 || ^6`. Its only code change is in the *helpers* package (`Readable/Writable` types used by openapi-fetch), not in the generator.
  - [#2867](https://github.com/openapi-ts/openapi-typescript/pull/2867) and [#2872](https://github.com/openapi-ts/openapi-typescript/pull/2872) add TS 7 support and would need a major release.
  - TS 7 breakage is confirmed in [#2841](https://github.com/openapi-ts/openapi-typescript/issues/2841) (`ts.factory` undefined).
- **Likely works on TS 6, but not run here.** TS 6 still has the JS API, so codegen most likely runs with only a peer warning. Silence the warning with `pnpm.peerDependencyRules.allowedVersions: {"openapi-typescript>typescript": "6"}`.
- **Audit issue is stale.** [#2846](https://github.com/openapi-ts/openapi-typescript/issues/2846) (vulnerable `js-yaml` 4.2.0 via `@redocly/openapi-core`, GHSA-52cp-r559-cp3m, high) no longer applies to a fresh lock: `@redocly/openapi-core` 1.34.20+ pins `js-yaml 4.3.2`, and the advisory is fixed in 4.3.0.

### 2.3 djangorestframework-stubs vs the mypy cap

- **Where the cap lives.** It sits only on the `compatible-mypy` extra.
  - 3.18.1: `mypy<2.4` and `django-stubs>=6.1.0`.
  - 3.18.2: `mypy<2.5` and `django-stubs>=6.1.2` ([3.18.2 JSON](https://pypi.org/pypi/djangorestframework-stubs/3.18.2/json)).
- **When 3.18.2 clears.** It was uploaded 2026-11-02T23:46:16Z, so it leaves the 7-day window at **≈2026-11-09 23:46 UTC**. That is a few hours earlier than the "11-10" in the typing note.
- **Recommendation:** start on `mypy>=2.3.1,<2.4` with the extra. Then run `uv lock --upgrade-package djangorestframework-stubs --upgrade-package mypy` to move to 3.18.2 and mypy 2.4.1.
- **Not recommended:** dropping the extra to get mypy 2.4.1 now. It resolves, but upstream doesn't test it.

### 2.4 Can django-stubs 6.x be restricted to Django 5.2? **No.**

- **No version setting.** django-stubs has no config option for the Django version (the plugin options are `django_settings_module`, `strict_settings`, …). The stubs aren't version-gated.
- **6.x modules are present.** `django-stubs/tasks/__init__.pyi`, `middleware/csp.pyi` and `utils/csp.pyi` all exist at tag 6.1.2. The matching modules exist only on Django `stable/6.0.x` (404 on `stable/5.2.x`).
- **No release fits 5.2 on 3.14.** The compatibility table has no release that targets 5.2 *and* Python 3.14 (5.2.9 stops at 3.13). Downgrading to 6.0.9 conflicts with drf-stubs (§ conflicts) ([README table](https://github.com/typeddjango/django-stubs#version-compatibility)).
- **Mitigations:**
  - Ruff `TID251` with `[tool.ruff.lint.flake8-tidy-imports.banned-api]`: ban `django.tasks`, `django.middleware.csp` and `django.utils.csp`, with a message pointing to the `django-lts` skill.
  - Tests run on real 5.2. They catch new methods or kwargs on old classes, but only on covered paths.

### 2.5 Pyrefly

Not relevant: mypy is the gate. For the record, 1.4.0 ships `py3-none` binary wheels and has no Python-version classifiers.

## 3. Unchosen pieces

### 3.1 MariaDB driver for the WP import → **PyMySQL** (only if you read MariaDB directly)

| | mysqlclient 2.3.0 (2026-09-14) | PyMySQL 1.2.3 (2026-09-17) |
|---|---|---|
| Maintainer | Inada Naoki (`PyMySQL` org) | Same person and org. 7.9k★, pushed today |
| Py 3.14 | Classifier ✅. **No Linux wheels**, so it's built from sdist: needs `build-essential pkg-config default-libmysqlclient-dev` in the image ([README](https://github.com/PyMySQL/mysqlclient#linux)) | Pure Python. No classifier, but CI-tested on 3.14 and 3.15 |
| Django backend | "The recommended choice" ([5.2 databases](https://docs.djangoproject.com/en/5.2/ref/databases/#mysql-db-api-drivers)) | Not listed by Django. Needs the `install_as_MySQLdb()` shim to work as a backend |
| Typing | Ships stubs | `types-PyMySQL` 1.2.0.20260923 (typeshed) |

- **Why PyMySQL.** The import only *reads* WP tables. Use a plain DB-API connection inside the management command with constant SQL and parameters, not a second `DATABASES` alias. That avoids a C toolchain in the image and keeps MariaDB out of Django's configuration.
- **Security note.** **1.2.4 (2026-11-09, still in cooldown)** fixes SQL injection for `tuple/list/set` parameters under `NO_BACKSLASH_ESCAPES` ([CHANGELOG](https://github.com/PyMySQL/PyMySQL/blob/main/CHANGELOG.md), GHSA-m75w-33c4-7v8q). On 1.2.3, don't pass sequence parameters. WP's `sql_mode` doesn't set that flag.
- **Zero-dependency alternative:** the WP REST API through stdlib `urllib`. It exposes ACF fields (`show_in_rest` in `acf-fields.php`) and Yoast `yoast_head_json`, but not user emails or arbitrary postmeta.

### 3.2 Databases → **PostgreSQL 18, one container per service**, with `psycopg[binary]>=3.3.6,<3.4`

| | Postgres 18 (`postgres:18-alpine`, 18.6) | SQLite (stdlib) | Reuse MariaDB 11 |
|---|---|---|---|
| Deps | `psycopg[binary]` 3.3.6 (2026-09-18). cp314 wheels for glibc and musl on x86_64/aarch64. Daniele Varrazzo. 3.3.7/3.3.8 are bug fixes only ([news](https://github.com/psycopg/psycopg/blob/master/docs/news.rst)) | None | mysqlclient (compiled, see above) |
| Django 5.2 fit | PG 14+ supported. Conditional and functional unique constraints, `nulls_distinct` (PG 15+) | Partial indexes ✅. Concurrency limits with multiple gunicorn workers (use WAL + `transaction_mode: IMMEDIATE`) | **`condition=` and functional indexes are silently ignored** on MariaDB ([indexes](https://docs.djangoproject.com/en/5.2/ref/models/indexes/#condition)). Couples the new app to the legacy DB server |
| Fit with the challenge ("own container, own DB", "100x data") | Strongest | Weak answer to "100x" and to "would you ship this?" | Weak boundary story |

- psycopg's docs prefer the local `c` build for production ([install](https://github.com/psycopg/psycopg/blob/master/docs/basic/install.rst)). Binary is fine for this take-home; say so if asked.
- Give the main app no credentials for the auth database.

### 3.3 WSGI server → **gunicorn 26.2.0** (2026-08-24), with approval for the missing 3.14 classifier

| | gunicorn 26.2.0 | granian 2.8.7 (2026-10-28) | uvicorn 0.54.0 (2026-09-25) |
|---|---|---|---|
| Kind | Pure-Python WSGI. **Zero required deps** | Rust WSGI/ASGI/RSGI server, cp314 wheels | ASGI only. Status "4 - Beta" |
| Py 3.14 | ❌ classifier and CI stop at 3.13 | ✅ classifiers 3.10–3.15 | ✅ |
| Maintainers | benoitc plus contributors. 10.7k★. Very active (HTTP/1.1 hardening in 26.0) | Mostly one person (gi0baro). 5.8k★ | Kludex (Encode) |
| Fit | Django's documented WSGI path ([5.2 howto](https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/gunicorn/)). Sync views, so the sync worker is fine | Fast, but harder to defend and single-maintainer | Running sync Django under ASGI adds a thread hop for nothing |

- **Oddity:** GitHub has release tags **26.2.1 and 26.2.2** (2026-09-05/06, HTTP/2 and ASGI hardening), but neither is on PyPI (`/pypi/gunicorn/26.2.2/json` → 404). The reason is unverified. It doesn't affect the default sync worker.
- **New need: WhiteNoise.** With `DEBUG=False`, something must serve `/static/`: the compiled SCSS and the React bundle. Use **`whitenoise` 6.12.0** (2026-02-27): classifiers Dj 5.2 and Py 3.14, no required deps, maintained by David Evans. The alternative is an nginx container. No CORS package is needed: the bundle is same-origin, and in development use Vite's `server.proxy` instead of `django-cors-headers`.

### 3.4 Python base image → **`python:3.14-slim-trixie` pinned by digest**, with uv copied from `ghcr.io/astral-sh/uv:0.13.x`

- `python:3.14.10-slim-trixie` was rebuilt 2026-11-08 (Docker Hub). Python 3.14.10 was released 2026-10-25 (python.org), with bugfixes until 2027-10 and security fixes to 2030-10 *(endoflife.date)*.
- Every compiled dependency picked here (cryptography, nh3, psycopg-binary) has glibc wheels, so the runtime image needs no compiler. That's the main reason to avoid mysqlclient.
- Alpine also works: musllinux wheels exist for all of them. But musl brings no benefit here.
- Use a multi-stage build, `uv sync --locked --no-dev`, and a non-root user. Include the shared-lib directory in the build context.
- Docker Hardened Images are an option to mention *(secondary)*.

### 3.5 Sass compiler → **`sass` 1.107.1**

| | `sass` (Dart Sass compiled to JS) | `sass-embedded` |
|---|---|---|
| Deps | 3 (`chokidar`, `immutable`, `source-map-js`), plus optional `@parcel/watcher` | 7, plus **18 optional per-platform native packages** (Dart VM binary) |
| Maintainers | nex3, hcatlin | nex3 only |
| Install scripts | `@parcel/watcher` has an `install` script that pnpm will flag. Leave it unapproved: prebuilt platform packages cover it | None |
| Speed | Slower. Irrelevant for one theme | Faster |

Both work with Vite 8 (optional peers). `sass` is also the CLI for the README's "how to compile" step: `pnpm exec sass frontend/scss/main.scss static/css/main.css`.

### 3.6 Frontend tests → **Vitest 5.0.5 + jsdom 30.1.3 + Testing Library + `axe-core` directly**

- **Vitest:** 5 maintainers, from the Vite team.
- **jsdom over happy-dom 21.0.4:** jsdom has 6 maintainers; happy-dom has a single one.
- **Call `axe-core` directly** with a ~10-line helper: `const r = await axe.run(container); expect(r.violations).toEqual([])`.
  - **Skip `vitest-axe`:** 0.1.0 is from 2022, and only `1.0.0-pre.5` exists after it, from a single maintainer.
  - **Skip `jest-axe` 11.0.0:** it pulls `jest-matcher-utils` and pins `axe-core 4.12.1`.
- `@testing-library/jest-dom` 7.0.1 is optional sugar; skip it.
- jsdom can't check colour contrast because it has no layout *(secondary)*. Do that manually in the browser.

## 4. Challenge fit, weak spots, dependency weight

| Choice | Strongest interviewer objection | One-line defence |
|---|---|---|
| Django 5.2 LTS | "6.1 is out. Why old?" | LTS security support to April 2028. 6.x isn't LTS. Deprecation warnings fail the tests, so the move to 6.2 stays cheap. |
| Python 3.14 | "Bleeding edge; gunicorn doesn't even declare it." | Newest Python that 5.2.8+ supports. Every compiled dependency has 3.14 wheels. The gaps are pure-Python packages, approved and tested. |
| DRF | "Maintainers call it feature-complete. Ninja is modern." | The challenge names DRF authentication and permission classes. It has pagination and filtering conventions, and 3 security fixes in October show it's patched. |
| PyJWT EdDSA, local JWKS | "How do you revoke? What if auth is down?" | Short TTL plus `kid` rotation. Cached JWKS keeps verifying while auth is down, and a cold start fails closed. Revocation is a deliberate trade-off (user's decision). Check `typ` by hand (§1). |
| nh3 | "ammonia 4.1.4 has open advisories." | All three need SVG animation or `style` allowed. The allow-list forbids both, and tests include those payloads. |
| Custom CSP | "Don't roll your own security." | It's a static header with no nonces, about 20 tested lines. django-csp doesn't declare 3.14 and hasn't released in 19 months. It maps onto `SECURE_CSP` in 6.2. |
| mypy strict + stubs | "The stubs describe Django 6.1, so the checker lies about 5.2." | It's the only ORM-aware checker. 6.x leaks are blocked by `TID251` and by tests on 5.2 (§2.4). |
| drf-spectacular → openapi-typescript → Zod | **"Three tools and ~10 packages for one GET and one PATCH."** | Hard to defend. See "Drop" below. |
| React 19 + Vite, client-only | "Why React for a component on an SSR page?" | The challenge requires it. It's an island mounted with `json_script`, with no RSC server surface. |
| TypeScript 6 | "7 is `latest`." | 7.0 ships no compiler API, and typescript-eslint caps at `<6.1`. 6.0 is the compatible line. |
| pytest + pytest-django | "Django has a test runner." | The shared library can't use Django's runner. One runner everywhere, plus fixtures and parametrize. |
| Postgres ×2 | "Two more containers." | The challenge says "own container, own database". MariaDB silently ignores conditional constraints. |
| gunicorn | "No 3.14 classifier." | Django's documented WSGI server, pure Python, no deps. The approval is recorded. granian is the fallback. |

**Drop:**
- **openapi-typescript.** It conflicts with TS 6, has had no release in 9 months, and its fix is split across three unmerged PRs.
- **Make drf-spectacular optional.** It's untested on DRF 3.18, dormant for 4 months, and adds 9 packages including a Rust extension.
- **Replacement:**
  - Use one hand-written Zod schema, with the TS type from `z.infer`.
  - Add a zero-dependency **contract fixture**: a pytest test writes or compares `contracts/brand-list.example.json` from the real serializer, and a Vitest test `safeParse`s that same file. Drift fails CI on both sides.
- **Keep Zod.** Runtime validation at the fetch boundary feeds the graded error state.
- **When the generators come back.** Use drf-spectacular to produce a committed `openapi.json` as a talking point for the mobile-client question, or as "more endpoints" future work.
- **Shared-library scope note.** The DRF adapter in the shared library makes the library's strict mypy run need django-stubs and drf-stubs too. Its tests need a minimal `settings.configure()`. That's allowed ("without either Django project"), but say so.

**Direct dependency counts (recommended set):**

| Project | Runtime | Dev | Notes |
|---|---|---|---|
| Main app | 8: Django, DRF, nh3, shared-lib, psycopg[binary], gunicorn, whitenoise, PyMySQL | 7: pytest, pytest-django, mypy, django-stubs, drf-stubs, ruff, types-PyMySQL | About 16 runtime packages in total. drf-spectacular would add 9 |
| Auth service | 6: Django, DRF, PyJWT[crypto], shared-lib, psycopg[binary], gunicorn (+PyMySQL if `wp_users` is read from MariaDB) | 6 (same, minus types-PyMySQL) | DRF is optional here: login and JWKS are 2 views |
| Shared lib | 1: PyJWT[crypto] (`cryptography` floor), extra `[drf]`: DRF | 3–5: pytest, mypy, ruff (+ django-stubs, drf-stubs for the adapter) | — |
| Frontend | 3: react, react-dom, zod | 12 | Plus openapi-typescript if kept |

## 5. Recommended pins

```toml
# main app pyproject.toml  (requires-python = ">=3.14,<3.15"; [tool.uv] exclude-newer = "7 days")
dependencies = [
  "Django>=5.2.8,<5.3",                 # locks 5.2.18 today; 5.2.19 (security) clears 2026-11-10
  "djangorestframework>=3.18.3,<3.19",
  "nh3>=0.3.7,<0.4",
  "psycopg[binary]>=3.3.6,<3.4",
  "gunicorn>=26.2.0,<27",               # needs approval: no Py3.14 classifier
  "whitenoise>=6.12.0,<7",
  "PyMySQL>=1.2.3,<1.3",                # only for a direct-DB import; raise floor to 1.2.4 once it clears
  "<shared-lib>",                       # [tool.uv.sources] path = "../<shared-lib>", editable
]
[dependency-groups]
dev = ["pytest>=9.2.0,<10", "pytest-django>=4.14.0,<5", "ruff>=0.17.3,<0.18",
       "mypy>=2.3.1,<2.4", "django-stubs[compatible-mypy]>=6.1.2,<6.2",
       "djangorestframework-stubs[compatible-mypy]>=3.18.1,<3.19",   # → 3.18.2 + mypy>=2.4.1,<2.5 after 11-09 23:46 UTC
       "types-PyMySQL>=1.2.0.20260923"]

# auth service: same Django/DRF/psycopg/gunicorn/shared-lib pins, plus
  "PyJWT[crypto]>=2.15.1,<3", "cryptography>=50.0.2",    # signs tokens directly
# dev: as main app minus types-PyMySQL

# shared lib (wide ranges; the services' lockfiles pin)
dependencies = ["PyJWT[crypto]>=2.15.1,<3", "cryptography>=50.0.2"]
[project.optional-dependencies]
drf = ["djangorestframework>=3.18.3,<3.19"]
[dependency-groups]
dev = ["pytest>=9.2.0,<10", "mypy>=2.3.1,<2.4", "ruff>=0.17.3,<0.18"]   # + stubs if the adapter is type-checked
```

```jsonc
// frontend/package.json   (Node 24.15+ or 26; pnpm release-age delay resolves carets to the versions noted)
"engines": { "node": "^24.15.0 || >=26.0.0" },
"dependencies":    { "react": "^19.3.1", "react-dom": "^19.3.1", "zod": "^4.6.7" },
"devDependencies": { "vite": "^8.3.5", "@vitejs/plugin-react": "^6.1.2", "typescript": "~6.0.3",
  "@types/react": "^19.3.0", "@types/react-dom": "^19.3.0", "sass": "^1.107.1",
  "vitest": "^5.0.5", "jsdom": "^30.1.3", "@testing-library/react": "^16.3.3",
  "@testing-library/dom": "^10.4.2", "@testing-library/user-event": "^14.6.8", "axe-core": "^4.14.0" }
// if kept: "openapi-typescript": "7.13.0" + pnpm.peerDependencyRules.allowedVersions {"openapi-typescript>typescript": "6"}
```

Container images: `python:3.14-slim-trixie@sha256:…`, `postgres:18-alpine@sha256:…`, `node:24-slim@sha256:…` (build stage only).

## Not verified
- openapi-typescript 7.13.0 actually generating under TS 6.0.3 (nothing was installed).
- drf-spectacular 0.30.0 against DRF 3.18.3: no upstream CI and no local run. Only the absence of issue reports.
- gunicorn on Python 3.14: no upstream CI. Also why the 26.2.1/26.2.2 tags never reached PyPI.
- drf-stubs 3.18.1 with mypy 2.4.x without the `compatible-mypy` extra.
- pnpm 12's default peer-dependency strictness (whether the TS 6 peer mismatch warns or fails).
- The Vite releases across 6.4/7.3/8.1/8.2/8.3 on 2026-11-09 have no published advisory yet. They look like a coordinated fix; defer to the cooldown research.
- Maintainer identities come from PyPI `author`/`maintainer` fields and npm `maintainers`, not from PyPI's web UI.
