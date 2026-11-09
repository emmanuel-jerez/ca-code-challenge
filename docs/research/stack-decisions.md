# Stack decisions: CSP, API framework and tokens, HTML sanitizer

Researched 2026-11-09 for Django 5.2 LTS on Python 3.14 with uv `exclude-newer = "7 days"`.
Anything released after **2026-11-02** is still inside the cooldown and can't be pinned yet.
Version, date and classifier data comes from the PyPI JSON API (`https://pypi.org/pypi/<name>/json`).
Advisory data comes from each repo's GitHub Security Advisories API. Anything backed only by a
secondary source is marked *(secondary)*.

> **Corrections to `best-practices-2026.md`:**
> - PyJWT ≥ 2.13 is no longer enough. Sixteen more advisories were fixed in 2.14.0 and 2.15.0, so the floor is now **2.15.1**.
> - python-jose has released since 2021: 3.4.0 (2025-02-18) and 3.5.0 (2025-05-28).
> - bleach was *announced* deprecated in 2023, but its last release, 6.4.0, came out on 2026-06-05 with a "no longer maintained" notice.
> - The notes' "Django 6.0 CSP" advice doesn't apply to this project, which stays on 5.2.

> **Side finding:** Django **5.2.19** (2026-11-03) fixes 1 moderate and 4 low-severity CVEs, but the cooldown keeps it out until 2026-11-10.
> The resolver will pick **5.2.18** until then. Either wait one day or add a dated `exclude-newer-package` exception
> ([5.2.19 notes](https://docs.djangoproject.com/en/5.2/releases/5.2.19/)).

---

## 1. Content Security Policy on Django 5.2

**Django 5.2 has no built-in CSP.**
- The 5.2 settings reference has no `SECURE_CSP*` entries, and `docs.djangoproject.com/en/5.2/ref/csp/` returns 404.
- The 6.0 docs have [`ref/csp/`](https://docs.djangoproject.com/en/6.0/ref/csp/), and the 6.0 release notes list "Content Security Policy support" as a new feature ([6.0 notes](https://docs.djangoproject.com/en/6.0/releases/6.0/)).
- `django/middleware/security.py` on `stable/5.2.x` has no CSP code ([source](https://github.com/django/django/blob/stable/5.2.x/django/middleware/security.py)).
- This matches the `django-lts` skill.

| Option | Version / date | Py 3.14 / Dj 5.2 | Maintenance | Pros | Cons |
|---|---|---|---|---|---|
| **(a) `django-csp`** | **4.0**, 2025-04-02 (no release since) | Dj 5.2 classifier ✅. **No Py 3.14 classifier.** tox only tests 3.9–3.13 ([tox.ini](https://github.com/mozilla/django-csp/blob/main/tox.ini)). Pure-Python wheel. | `mozilla/django-csp`. PyPI maintainer is the "Mozilla MEAO team". Low activity: last commit 2026-10-29, Django 6.0 CI added 2025-11 ([commits](https://github.com/mozilla/django-csp/commits/main)). | Lazy per-request nonce (`request.csp_nonce`, `csp.constants.NONCE`). Report-only policy. Per-view decorators. `EXCLUDE_URL_PREFIXES`. | Py 3.14 support isn't declared, which fails the skill's vetting rule as written. No release in 19 months. One more dependency. |
| **(b) Custom middleware** | n/a (~20–30 lines) | ✅ (your code) | You own it | No dependency. The policy dict lives in settings and the header is tested with the Django test client. Easy to swap for 6.2's `SECURE_CSP` at the next LTS. | You write the nonce generation yourself, if you need nonces. No per-view decorators. |
| **(c) Reverse proxy header** | n/a | n/a | Ops config | Covers static and media responses too. No app code. | The challenge ships no proxy for Django. A static header can't carry a per-request nonce. The policy lives outside the repo's tests. |

`django-csp` 4.0 notes:
- **Breaking config change.** The `CSP_*` settings are replaced by `CONTENT_SECURITY_POLICY = {"DIRECTIVES": {...}}` and `CONTENT_SECURITY_POLICY_REPORT_ONLY`. `manage.py check` drafts the migration ([CHANGES.md](https://github.com/mozilla/django-csp/blob/main/CHANGES.md)).
- **Nonce behaviour.** The nonce is emitted only if `NONCE` is in `script-src`/`style-src` and the template reads `request.csp_nonce` ([nonce docs](https://github.com/mozilla/django-csp/blob/main/docs/nonce.rst)).

**Recommendation: (b) a small custom middleware, with no new dependency.**
- **No inline scripts needed.** The React `<BrandList />` ships as a built bundle from `{% static %}`, so `script-src 'self'` covers it. Initial props go through Django's `{{ data|json_script:"brand-list-props" }}`, which is a `type="application/json"` block that browsers don't execute.
- **Suggested policy:** `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'`.
- **Rollout:** ship it as `Content-Security-Policy-Report-Only` first.
- **When to use `django-csp` instead:** if nonces become necessary (an inline script you can't avoid), switch to `django-csp>=4.0,<5`. First get approval for the missing Py 3.14 classifier and run its test suite on 3.14. It's pure Python, so the risk is low but unverified.
- **Reverse proxy:** treat (c) as defence in depth in deployment, not the primary control.

## 2. API framework and token library

### 2a. DRF vs Django Ninja

| | **Django REST framework** | **Django Ninja** |
|---|---|---|
| Latest | 3.18.3, 2026-10-06 ✅ cooldown | 1.8.0, 2026-11-08 ❌ (inside cooldown). **1.7.3**, 2026-10-29 ✅ |
| Py 3.14 / Dj 5.2 | Py 3.14 added in 3.17.0. Classifiers cover Dj 5.2/6.0/6.1 and Py 3.10–3.15. **3.18 dropped Dj < 5.2** ([release notes](https://www.django-rest-framework.org/community/release-notes/)) | Classifiers cover Dj 5.2 and Py 3.10–3.15 ([PyPI](https://pypi.org/project/django-ninja/)) |
| Maintenance | **Official position: "feature-complete".** The project focuses on tracking Django versions and generally doesn't accept new features ([contributing.md](https://github.com/encode/django-rest-framework/blob/main/docs/community/contributing.md)). It is still actively patched: 8 releases in 2026, including 3 security GHSAs fixed in 3.18.2 | Active feature development: 1.7.x and 1.8 in Sep–Nov 2026. Hotfixes are backported to the 1.6/1.7 lines. Mainly one maintainer (vitalik), a bus-factor risk |
| Pluggable auth | `BaseAuthentication.authenticate(request) -> (user, auth)` plus `BasePermission.has_permission()`, configured per view or globally ([auth](https://www.django-rest-framework.org/api-guide/authentication/#custom-authentication), [perms](https://www.django-rest-framework.org/api-guide/permissions/#custom-permissions)). Both are plain classes, so they fit a shared library | `HttpBearer.authenticate(request, token)` for authentication. **No permission classes**: the docs say to check `request.auth` in the view or write a decorator ([auth guide](https://github.com/vitalik/django-ninja/blob/v1.7.3/docs/docs/guides/authentication.md)) |
| Recent security | 3.18.2: `Accept` header DoS, charset handling, TokenProxy deletion | **1.7.2/1.6.4: `auth=` on `add_router()` wasn't applied to nested routers** ([release](https://github.com/vitalik/django-ninja/releases/tag/v1.7.2)). Don't go below 1.7.3 |
| Pros | `CHALLENGE.md` names "a DRF authentication class and permission class" outright. Built-in pagination and filter conventions. Reviewers know it | Pydantic schemas, OpenAPI out of the box, async, less code |
| Cons | Heavier serializers. No new features upstream | You build the permission layer. Smaller ecosystem |

### 2b. JWT library (EdDSA, local JWKS verification)

| | Version / date | Py 3.14 | EdDSA | JWKS fetch + cache | 2026 security | Fit |
|---|---|---|---|---|---|---|
| **PyJWT** | **2.15.1**, 2026-09-28 ✅ | Classifiers cover 3.10–3.15. Pure-Python wheel | Ed25519 and Ed448 via the `[crypto]` extra (`cryptography>=3.4.0`) ([algorithms](https://github.com/jpadilla/pyjwt/blob/2.15.1/docs/algorithms.rst)) | `PyJWKClient(uri, cache_jwk_set=True, lifespan=300, timeout=30, cooldown_duration=30)` ([source](https://github.com/jpadilla/pyjwt/blob/2.15.1/jwt/jwks_client.py)) | 23 GHSAs. Fixed at 2.13.0, 2.14.0 and 2.15.0 (below). **None open against 2.15.1** | ✅ Best fit |
| joserfc (authlib org) | 1.8.0, 2026-11-03 ❌. **1.7.7**, 2026-10-19 ✅ | Classifiers cover 3.11–3.15 | ✅ (OKPKey) | ❌ No HTTP client: you fetch and cache the JWKS yourself | ~8 GHSAs in Sep–Nov 2026. The latest (OctKey accepts DER RSA public keys as HMAC secrets) is fixed in 1.7.7 ([advisories](https://github.com/authlib/joserfc/security/advisories)) | OK, but you'd write more code. Single maintainer (lepture) |
| Authlib | 1.9.5, 2026-11-05 ❌. 1.9.1 ✅ | ✅ | ✅ (via joserfc) | OAuth client machinery | — | Too heavy just to verify tokens |
| djangorestframework-simplejwt | 5.5.1, 2025-07-21 | ❌ No Py 3.14 classifier (stops at 3.13) | Allowed if `cryptography` is installed | `JWK_URL` through PyJWT's `PyJWKClient` ([backends.py](https://github.com/jazzband/djangorestframework-simplejwt/blob/master/rest_framework_simplejwt/backends.py)) | — | ⚠️ Built to be issuer and verifier in **one** project. `JWTStatelessUserAuthentication`/`TokenUser` can verify without a DB lookup ([docs](https://github.com/jazzband/djangorestframework-simplejwt/blob/master/docs/stateless_user_authentication.rst)), but it is a Django/DRF app, so it can't sit in a shared library tested without Django. No release in 15 months |
| python-jose | 3.5.0, 2025-05-28 | ❌ Classifiers stop at 3.13 | — | — | — | ❌ Revived briefly in 2025, no activity since. Still avoid |

PyJWT advisories ([list](https://github.com/jpadilla/pyjwt/security/advisories)):
- **CVE-2026-48526** (high): public-key JWK accepted as an HMAC secret, which allows HS256 forgery. Fixed in **2.13.0** ([NVD](https://nvd.nist.gov/vuln/detail/CVE-2026-48526)).
- **CVE-2026-48523**: algorithm allow-list bypass with `PyJWK`/`PyJWKClient` keys. Fixed in **2.13.0**.
- Also fixed in 2.13.0: CVE-2026-48522 (`PyJWKClient` SSRF via `file://` and similar schemes) and CVE-2026-48524 (JWKS refetch DoS).
- **2.14.0** fixed 12 more, including:
  - CVE-2026-102268 (critical): whitespace-mutated PEM skips the HS/asymmetric guard.
  - CVE-2026-102267: `PyJWKClient` followed redirects.
  - CVE-2026-101917: incomplete fix for the `kid` refetch DoS.
- **2.15.0** fixed CVE-2026-101918 (RecursionError DoS) and CVE-2026-102275 (inconsistent OKP x/d) ([CHANGELOG](https://github.com/jpadilla/pyjwt/blob/master/CHANGELOG.rst)).
- **What this means for us.** Most of these need a mixed HMAC/asymmetric allow-list. Passing `algorithms=["EdDSA"]` only, and never accepting HS*, sidesteps that whole class of bug.

**`cryptography`:**
- Latest is **50.0.2** (2026-09-30). Its `cp311-abi3` wheels install on 3.14, and the classifiers cover 3.10–3.15.
- Use ≥ 50.0.0: CVE-2026-69247 (PKCS#7 Bleichenbacher oracle) is fixed in 50.0.0, and the bundled-OpenSSL CVE-2026-34180 in 48.0.1 ([advisories](https://github.com/pyca/cryptography/security/advisories)).
- Neither affects JWT verification, but there's no reason to sit below them.

**Recommendation: DRF + PyJWT[crypto].**
- **Auth service** (issuer): signs EdDSA (Ed25519) tokens with `jwt.encode` and serves a `/.well-known/jwks.json`.
- **Shared library core** (pure Python): depends only on `PyJWT[crypto]`. It wraps `PyJWKClient` and `jwt.decode`, and pins `algorithms=["EdDSA"]`, `audience`, `issuer` and `options={"require": ["exp","iat","iss","aud","sub"]}`.
- **Shared library DRF adapter:** an authentication class that returns a non-DB principal, plus an `IsEditor` permission class. Ship it under an optional `[drf]` extra.
- **Fallback algorithm:** ES256 if Ed25519 is ever unavailable.
- **Pins** (all outside the cooldown):
  - `djangorestframework>=3.18.3,<3.19`
  - `PyJWT[crypto]>=2.15.1,<3`
  - `cryptography>=50.0.2` (transitive; set the floor explicitly)

## 3. HTML sanitizer for WordPress `post_content`

| | Version / date | Py 3.14 wheels | Maintainers | Allow-list API | Security history | Status |
|---|---|---|---|---|---|---|
| **nh3** (Rust ammonia bindings) | **0.3.7**, 2026-08-23 ✅ | ✅ `cp38-abi3` wheels for all major platforms plus `cp314t` free-threaded wheels. No classifiers on PyPI | messense (PyO3/maturin maintainer). 405★. Frequent releases. ([repo](https://github.com/messense/nh3)) | Allow-list only: `nh3.clean(html, tags=, attributes=, url_schemes=, link_rel=, …)` or a reusable `nh3.Cleaner(...)`. Defaults exposed as `nh3.ALLOWED_TAGS` etc. ([stubs](https://github.com/messense/nh3/blob/v0.3.7/nh3.pyi)) | See the ammonia note below | ✅ Recommended by the lxml-html-clean README itself |
| bleach | 6.4.0, 2026-06-05 | Pure-Python wheel. Py 3.14 classifier | Mozilla (willkg) | Allow-list | Fixed GHSA-8rfp-98v4-mmr6 (invisible-char `javascript:` bypass) in 6.4.0 | ❌ **"No longer maintained. There will be no future releases including for security issues."** Classifier is `7 - Inactive` ([README](https://github.com/mozilla/bleach/blob/main/README.rst), [issue #698](https://github.com/mozilla/bleach/issues/698)) |
| lxml-html-clean | 0.4.6, 2026-10-26 | Pure Python, needs lxml 6.1.3 (cp314 wheels ✅) | Fedora Python / Red Hat (Lumír Balhar) | **Block-list** `Cleaner` | 5 GHSAs, 4 of them in 2026 (`<base>` injection, `xlink:href` `javascript:`, CSS `@import` bypass, ReDoS) ([advisories](https://github.com/fedora-python/lxml_html_clean/security/advisories)) | ❌ Its own README says it is "**not** considered appropriate for security sensitive environments", see nh3 ([README](https://github.com/fedora-python/lxml_html_clean)) |
| justhtml | 3.16.0, 2026-10-26 | Pure Python, zero deps. **No classifiers** | Emil Stenström, single maintainer. First release 2025-11-30 | Policy-based allow-list. Includes a bleach migration guide ([README](https://github.com/EmilStenstrom/justhtml)) | Not reviewed in depth | ⚠️ Credible and active, but under 1 year old and on its 3rd major version. Too young for a security boundary |

**ammonia caveat:**
- nh3 0.3.7's `Cargo.lock` pins **ammonia 4.1.4** ([lock](https://github.com/messense/nh3/blob/v0.3.7/Cargo.lock)). Three October 2026 ammonia advisories cover that version, all medium ([advisories](https://github.com/rust-ammonia/ammonia/security-advisories)):
  - GHSA-f2pc-rwv3-69mv: SVG `animateMotion`/`animateTransform`/`animateColor` XSS.
  - GHSA-69v2-w9vg-4g83: CSS `url()` quote injection.
  - GHSA-x43w-36pp-96g3: case-sensitive `URL(` filter.
- **All three need opt-in features.** One needs SVG animation tags allowed; the other two need `style` plus `filter_style_properties`.
- **ammonia 4.1.4's default tag set has no SVG or MathML tags, and `style` is off by default** ([lib.rs](https://github.com/rust-ammonia/ammonia/blob/v4.1.4/src/lib.rs)).
- The bump to ammonia 4.2.4 is merged on nh3 `main` (PR #149, 2026-10-27) but **not released yet**.
- The earlier mXSS advisories (CVE-2026-63430, CVE-2026-102342) are fixed in 4.1.3/4.1.4, which 0.3.7 already includes.

**Recommendation: nh3, pinned `nh3>=0.3.7,<0.4`.**
- **Explicit allow-list, narrower than the defaults:** `p, br, strong, em, b, i, ul, ol, li, blockquote, a, h2–h4`. Allow `href` on `a` only. Set `url_schemes={"http","https","mailto"}` and keep `link_rel="noopener noreferrer nofollow"`.
- **Never allow:** `style`, `svg`, `math` or `animate*`. That keeps 0.3.7 clear of the open ammonia advisories. Upgrade as soon as an nh3 release with ammonia ≥ 4.2.4 clears the cooldown.
- **Where to sanitize:** at import time, storing the cleaned HTML. Optionally re-clean at render time through a template filter, so `|safe` only ever sees nh3 output.
- **Test it:** add tests with XSS payloads (`<script>`, `onerror=`, `javascript:` hrefs, an SVG `animateMotion` vector).

---

### Not verified
- PyPI maintainer usernames: the PyPI project pages are bot-gated. Maintainers above come from the PyPI JSON `author`/`maintainer` fields and the GitHub repo owner.
- Whether `django-csp` 4.0's test suite passes on Python 3.14: there is no CI evidence either way.
- justhtml's security track record.
- Whether a newer nh3 release is imminent.
