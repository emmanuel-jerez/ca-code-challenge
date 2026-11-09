# Pillar 6: the shared Python library

Research notes, **2026-11-09**. Scope: the installable package that both Django services use. It covers what goes in (module by module), the JWKS client, the verifier, the DRF adapter, packaging, how each service installs and upgrades it, the breaking-change process, and its tests. Signing, the login endpoint and the JWKS endpoint belong to the auth service (Pillar 5) and appear here only where the library touches them. Every section names options with their attack-surface and stability costs, gives a **Recommendation**, and ends with a **Defend it** line. The user owns the design decisions; the open ones are listed near the end.

> **How this was checked.** Context7 answered for PyJWT 2.15.1, uv 0.13.5 and DRF 3.18.3 (no quota problems). Source code came from GitHub at the exact tags; versions and dates came from the PyPI JSON API; advisories came from GitHub's advisory API and OSV. Claims marked **(verified)** were run in throwaway projects in the session scratchpad, never in the repo: uv 0.13.6, PyJWT 2.15.1, cryptography 50.0.2, Django 5.2.18, DRF 3.18.3, mypy 2.3.1, Ruff 0.17.3. Python 3.14 isn't installed on this machine, so the runs used Python 3.12.3. mypy was run with `--python-version 3.14`. None of the tested behavior depends on the interpreter version [37].

> **Corrections to earlier research**
> - `best-practices-2026.md` §8 says to "serve a stale JWKS rather than failing closed for a bounded time". PyJWT's `PyJWKClient` can't do that. Once its cache expires and the fetch fails, every verification fails (verified, §2).
> - `best-practices-2026.md` §9 suggests shipping token-minting test fixtures as a `[testing]` extra. Extras gate *dependencies*, not files. A `testing.py` that signs would ship in every wheel and break the "never signing" rule (ADR 0003, AGENTS.md). Keep minting helpers in the library's own `tests/`.
> - `stack-decisions.md` §2b recommends an `IsEditor` permission, and `typing-and-validation.md` §1 proposes `Claims(roles: frozenset[Role])`. Both predate the accepted rule "authorize by scope claims, not role names" (ADR 0003). The claims carry `scopes`.
> - `stack-decisions.md` §2b's `require` list (`exp, iat, iss, aud, sub`) misses `jti`, which RFC 9068 requires [11]. It also misses `nbf`, which ADR 0003 says to check. PyJWT checks `nbf` only when the claim is present [2].
> - `typing-and-validation.md` §3 says the library "needs only mypy (no Django stubs)". That holds only if the DRF adapter lives elsewhere. If the adapter is in the library, its dev group needs `django-stubs` and `djangorestframework-stubs` (verified, §4).
> - `stack-validation.md` §5's library dev group has no Django pin. DRF 3.18.3 requires `django>=5.2` with no upper bound [36], so the library's own lockfile would resolve Django 6.x. The adapter tests need `Django>=5.2.8,<5.3` in a dev group.

---

## Key findings

1. **`PyJWKClient` has no stale-if-error.** In PyJWT 2.15.1, once `lifespan` (default 300 s) passes and the JWKS endpoint is down, *every* verification fails, and every request retries the fetch (3 calls made 3 fetches, verified) [1].
2. **Its unknown-`kid` cooldown counts only successful fetches.** During an outage, each token with a made-up `kid` triggers a new fetch. The fetch runs under a lock with a 30 s default timeout (5 bad tokens made 5 fetches, verified) [1].
3. **A non-JSON `200` from the JWKS endpoint escapes as a raw `json.JSONDecodeError`**, not a `PyJWTError` (verified). An example is a proxy error page. The 2.15.0 advisory says a deeply nested JWKS response raises a raw `RecursionError` the same way [1][8].
4. **PyJWT's `decode` never checks `typ`** (verified). It checks `exp`, `nbf` and `iat` only when they're present, so the verifier must pass `options={"require": [...]}` [2][3].
5. **The `PyJWT[crypto]>=2.15.1` floor is right.** PyJWT had 21 advisories in 2026, all fixed by 2.15.0 [8]. OSV lists none for 2.15.1 [10], and the 2.15.1 wheel carries trusted-publishing provenance [9]. Caveat: 2.15.1 accepts correctly padded segments again [7], so one token now has two valid spellings. Index revocation by `jti`, never by the raw token string.
6. **The JWKS must never carry the private key component `d`.** `OKPAlgorithm.to_jwk()` emits `d` when handed a private key [6]. `PyJWK` accepts a JWK that contains `d` and builds a private key from it [4][6]. The library's JWKS helpers must accept public keys only, in their types and at runtime.
7. **What `uv.lock` pins depends on the source type (verified):**
   - A **directory** path source records the version and declared dependencies, with **no content hash**.
   - A **wheel** path source records a sha256, and a tampered wheel fails `uv sync --locked`.
   - A **git** tag source is pinned to the commit SHA.
   - For a path source, `uv lock --upgrade-package` does the same as a plain `uv lock`.
8. **A version bump is the forcing function (verified).** Bumping the library's version makes `uv lock --check` fail in each service until it re-locks. A code-only change goes unnoticed. A *non-editable* install also keeps stale code until `tool.uv.cache-keys` includes `src/**/*.py` [18].
9. **`uv_build` needs no build-time downloads** (verified): uv builds the library with its bundled copy of the backend. With `hatchling`, uv fetches 6 packages at build time; they aren't hash-locked, though the cooldown still applies to them (verified). The costs of `uv_build`: it requires a static version (verified), and it needs an upper-bound bump with each uv minor (four bumps between 2025-10 and 2026-10) [13][21].
10. **Dependency confusion (verified).** With the path source, uv never asks PyPI for the library's name. With `--no-sources` (or with pip), it does. So the name must be distinctive and unclaimed. `shared` already exists on PyPI [36].
11. **The DRF adapter tests and type-checks without either Django project (verified).** Tests need only:
    - `settings.configure(INSTALLED_APPS=["rest_framework"], REST_FRAMEWORK={"UNAUTHENTICATED_USER": None})` plus `django.setup()`;
    - no `django.contrib.auth`, no database, no pytest-django.

    mypy strict passes on the adapter with the stubs and no plugin. Put the claims in `request.auth` and narrow them with a `TypeIs` guard.
12. **DRF builds authentication and permission classes with no arguments** (`auth() for auth in ...`) [25]. Configuration can't arrive through the constructor. Use a one-method subclass in each service, or a class factory.

---

## 1. What goes in, module by module

**Requirement.** CHALLENGE.md says the library must hold "the token verification and permission-check code the main app uses to protect its endpoint". It also says: "Only code that both services actually use belongs there; be ready to justify each module." Those two lines pull against each other, because verification is a main-app job. Accepted already: verification, the claims dataclass, the JWKS client, permission checks and a thin DRF adapter. Never signing, models or settings.

| Module | Holds | Main app uses it to… | Auth service uses it to… | Verdict |
|---|---|---|---|---|
| `profile.py` | `ALGORITHM = "EdDSA"`, `TOKEN_TYPE = "at+jwt"`, required claim names, max token size, default leeway | verify against the profile | set `alg`/`typ` headers and claims when signing | **In**: one definition of the token profile |
| `scopes.py` | scope names, e.g. `BRANDS_WRITE = "brands:write"` | guard `PATCH /api/brands/<slug>/` | map roles to scopes (`editor → {BRANDS_WRITE}`) | **In**: a typo becomes an import error, not a silent 403 |
| `claims.py` | `AccessClaims` frozen dataclass, `from_payload()` with `TypeIs` guards, `to_payload()` | parse a verified payload | build the payload it passes to `jwt.encode` (the key and `encode` stay in the auth service) | **In**: the claim schema *is* the contract |
| `errors.py` | the exception hierarchy (§3) | map errors to 401/403/503 | contract tests; its own protected endpoint, if any | **In** |
| `jwks.py` | `public_jwk(key, kid)` and `parse_jwks(raw)`; public keys only | parse the fetched JWKS | publish `/.well-known/jwks.json` | **In**: the publisher and parser can't drift apart (e.g. a missing `use` would reject every key) |
| `keys.py` | `KeyProvider` Protocol, `StaticKeyProvider` | tests | contract tests ("what I mint, the verifier accepts"); its own endpoint | **In** |
| `jwks_client.py` | `CachedJwksKeyProvider`, `Fetcher` Protocol, `UrllibFetcher` | fetch and cache the JWKS | **never**: it doesn't fetch its own JWKS over HTTP | **Main-app only**: see the options |
| `verify.py` | `TokenVerifier` | verify every bearer token | contract tests; its own endpoint, if any | **In**: the challenge's minimum |
| `permissions.py` | `has_scopes()`, `require_scopes()` (pure Python) | authorize the write | its own endpoint, if any | **In**: the challenge's minimum |
| `drf.py` | `BearerAuthentication`, `require_scopes()` permission factory, principal | protect the endpoint | only if it has a token-protected endpoint | **In**: the challenge names it |
| Test helpers that sign | — | — | — | **Out**: signing |

**Kept out, and why:**
- Signing and private-key loading. Only the auth service may mint (ADR 0003). Signing code in the library would put minting on the main app's import path.
- Role names and the role → scope map. That's the auth service's data, and it should change without a library release.
- `token_version` lookups and revocation stores. They need a database or a network call, and only the main app's write path uses them. The library exposes the claim; the check lives in the service.
- Django models and settings.
- HTTP client libraries (`requests`, `httpx`): stdlib `urllib` is enough for one GET.
- Pydantic (AGENTS.md).

**A credible reason the auth service uses the library:**
- **Production:** its minting code builds `AccessClaims` and calls `to_payload()`. It reads `profile` and `scopes`, and its JWKS endpoint calls `public_jwk()`.
- **Tests:** a contract test mints a token and verifies it with `TokenVerifier(StaticKeyProvider(...))`. Issuer and verifier then fail together if they drift.
- **Optional:** a token-protected `GET /api/me/` that echoes the caller's `sub` and scopes, using the same DRF adapter. This also helps the README's "get a token and call the endpoint" walkthrough. Whether to add it is Pillar 5's call.

| Option | Security cost | Stability cost | Effort | Why it might lose |
|---|---|---|---|---|
| **(a) Everything above in the library; the JWKS client flagged main-app-only** | All verification code is in one tested place | Every module change is a library release | Lowest | Doesn't fit "only code both use" for the JWKS client |
| (b) The JWKS client moves into the main app | Same code, tested in the main app | Smaller library | Low | Splits verification across two places; a third consumer would copy it |
| (c) A tiny library: claims, scopes and profile only | Verification lives in the main app | Smallest | Low | Breaks the challenge's stated minimum |

**Recommendation: (a).** Keep the JWKS client in the library in its own module, and say in the README that only the main app uses it. The challenge counts token verification as library content, and the client's tests belong next to the verifier's.

**Defend it:** "Both services share the token *contract*: the profile, the claims schema, the scope names and the JWKS format. The issuer writes it and the verifier reads it, so it lives in one place. Signing, roles and revocation stores stay out, because only one side needs them, and signing must never be on the main app's import path."

---

## 2. JWKS client

**Requirement.** Fetch the auth service's JWKS, cache it, and pick keys by `kid`. Pick up rotated keys. Refetch on an unknown `kid` without letting a flood of bad tokens hammer the auth service. Behave predictably when the auth service is down (CHALLENGE question 7).

### What `PyJWKClient` 2.15.1 actually does

Read from source [1][4]; the "Verified" column means it was run locally.

| Property | Behavior | Verified |
|---|---|---|
| Set cache | `cache_jwk_set=True`, `lifespan=300` s, monotonic clock. Since 2.15.0 it stores a parsed `PyJWKSet` | — |
| Per-`kid` LRU | `cache_keys=False` by default. When on, it wraps `get_signing_key` in `lru_cache` with **no TTL**, so a key removed from the JWKS stays trusted until evicted | — |
| Unknown `kid` | Refetches once, unless within `cooldown_duration=30` s of the last **successful** fetch | ✅ |
| Fetch fails after expiry | The cache survives errors (2.13.0 fix), but `get()` returns nothing once expired. Every call refetches and raises `PyJWKClientConnectionError`. **No stale serving and no backoff** | ✅ (3 calls → 3 fetches) |
| Outage plus unknown `kid` | Every bad token makes a fetch attempt | ✅ (5 → 5) |
| Timeout | 30 s default | — |
| Concurrency | A `threading.RLock` is held **across the network fetch** | — |
| TLS | Optional `ssl_context` | — |
| Schemes and redirects | `http`/`https` only (2.13.0); redirects refused (2.14.0) | — |
| Non-JSON body | Raw `json.JSONDecodeError` escapes | ✅ |
| Key types accepted | Any usable JWK, including `kty: oct` (HMAC) and OKP keys carrying a private `d` | — |
| Test seam | A real socket, or a subclass overriding `fetch_data()`. The override must also update the private `_last_successful_fetch` | — |
| gunicorn | One cache per worker process. With ADR 0008's sync workers the lock is uncontended | — |

The `oct` acceptance is not exploitable while the verifier passes `algorithms=["EdDSA"]`. Since 2.13.0, PyJWT binds the token's `alg` to the key's algorithm when the key is a `PyJWK` [3][7]. The `d` acceptance is a different problem: if the auth service ever published `d` by mistake, the main app would hold a signing key in memory.

### Options

| Option | Security cost | Stability cost | Effort | Why it might lose |
|---|---|---|---|---|
| **A. `PyJWKClient` behind a `KeyProvider` wrapper.** `timeout=2`, `cache_keys=False`; the wrapper catches `PyJWKClientError`, `ValueError` and `RecursionError` | Upstream-maintained. Hardened by 5 client-side fixes in 2026. Keeps gaps 1–3 above and the `d`/`oct` acceptance | Tracks PyJWT's internals for free | ~30 lines | Auth outage beyond `lifespan` = total auth failure. An outage also amplifies fetches. Tests need a socket |
| B. Subclass `PyJWKClient`, overriding `fetch_data()` with an injected fetcher | Same as A, plus testability | **Couples to private attributes.** PyJWT changed these internals in 2.15.0 [7] | ~50 lines | Fragile across PyJWT minors, which cuts against the LTS goal |
| **C. A small custom provider.** stdlib `urllib` behind a `Fetcher` Protocol; PyJWT's `PyJWK` still parses keys and PyJWT still verifies | No new dependency. Stale-if-error and attempt-based rate limits by design. Rejects `oct` and `d` | Owns ~100 lines. Must restate upstream's 2026 protections: fixed URL, http(s) only, no redirects, never clear on error | ~100 lines + tests | More code to defend on the call |

**Recommendation: C**, built to these rules:
1. **Fresh cache, known `kid`:** return the key.
2. **Unknown `kid`:** refetch only if the last *attempt* (success or failure) was at least `min_refetch_interval` ago (30 s). Otherwise raise `UnknownKey` (401). Attempts are rate-limited, not just successes, so an outage can't amplify fetches.
3. **Cache older than `refresh_after` (300 s):** refetch, rate-limited the same way. On failure, serve the stale keys until `max_stale` (3,600 s). Past that, raise `KeySetUnavailable` (503).
4. **Never clear the cache on a failure.** This is the 2.13.0 lesson, GHSA-fhv5-28vv-h8m8 [8].
5. **`UrllibFetcher`:**
   - the URL comes from settings, never from a token header;
   - `http`/`https` only, no redirects;
   - 2 s timeout, at most 64 KiB read;
   - `User-Agent: <dist-name>/<version>` from `importlib.metadata`, so the auth service's logs show which library versions are live (§7).
6. **`parse_jwks()`:** the body must be a JSON object with a `keys` list. Keep only keys where:
   - `kty == "OKP"` and `crv == "Ed25519"`;
   - `use` is `sig` or absent, and `alg` is `EdDSA` or absent;
   - `kid` is a string and `d` is **absent**.

   Build each key with `PyJWK(jwk, algorithm="EdDSA")`. An empty result raises `KeySetUnavailable`. Catch `ValueError` and `RecursionError` from `json.loads`.
7. **One lock around the state and the fetch.** It's uncontended with sync workers, and the 2 s timeout bounds the wait with `gthread` workers.

Choose A instead if owning less code matters more than the outage behavior. The open decision is below.

```python
class Fetcher(Protocol):
    def fetch(self) -> bytes: ...          # raises KeySetUnavailable on any failure

class CachedJwksKeyProvider:               # implements KeyProvider
    def __init__(self, fetcher: Fetcher, *, refresh_after: float = 300.0,
                 max_stale: float = 3600.0, min_refetch_interval: float = 30.0,
                 clock: Callable[[], float] = time.monotonic) -> None: ...
    def get(self, kid: str) -> PyJWK: ...  # UnknownKey | KeySetUnavailable
```

**Defend it:** "I read PyJWKClient's source and tested it. Past its cache lifetime it fails every request when auth is down, and each forged `kid` costs a fetch during an outage. So the client is about 100 lines of stdlib code with an injected fetcher and clock. It serves known keys for up to an hour of outage, refetches at most once every 30 seconds whatever the outcome, and only accepts public Ed25519 keys. Each of PyJWT's 2026 JWKS advisories is a test case."

---

## 3. Verifier

**Requirement.** Verify an EdDSA access token against the cached keys. Check `iss`, `aud`, `exp`, `nbf` and `typ`. Return a typed claims object and raise only the library's own errors (ADR 0003, ADR 0013).

### Steps, in order

1. **Size cap.** Reject tokens over 4 KiB before parsing. Real tokens are a few hundred bytes. PyJWT has no limit of its own.
2. **Header pre-check** with `jwt.get_unverified_header()`, which validates that `kid` is a string [3]. Require `alg == "EdDSA"`, `typ` (lower-cased) in `{"at+jwt", "application/at+jwt"}` [11], and a `kid`. Junk tokens then never reach the key provider, so they can't trigger refetches.
3. **Key lookup:** `keys.get(kid)`, which returns a `PyJWK` bound to EdDSA.
4. **Decode:**
   ```python
   decoded = jwt.decode_complete(
       token, key, algorithms=["EdDSA"],
       audience=self._audience, issuer=self._issuer, leeway=self._leeway,
       options={"require": ["iss", "sub", "aud", "exp", "iat", "jti", "nbf"], "strict_aud": True},
   )
   ```
   - Build `options` as a fresh literal on every call. PyJWT 2.11–2.13 mutated a caller's options dict, which silently disabled claim checks on later calls (CVE-2026-103001, GHSA-gvp8-978c-rx2q) [8]. 2.15.1 copies the dict first [2], but a fresh literal makes a regression harmless.
   - PyJWT validates `exp`, `nbf` and `iat` only when they're present, and `require` treats a `None` value as missing [2].
   - `strict_aud=True` requires `aud` to be one string equal to ours [2]. Use it only if Pillar 5 always mints single-audience tokens.
   - RFC 9068 also requires `client_id` [11]. Add it to `require` only if the issuer emits it (open decision).
5. **Re-check `typ` on the verified header.** It's part of the signed input, so it's now authentic.
6. **Parse** `decoded["payload"]` into `AccessClaims` with `TypeIs` guards.
7. **Map errors** (table below). Catch `jwt.PyJWTError`, not `Exception`. A new PyJWT leak then shows up as a 500 in a fuzz test instead of hiding as a 401.

**Leeway: 30 s.** RFC 9068 allows "some small leeway, usually no more than a few minutes" [11]. PyJWT applies it to `exp`, `nbf` and `iat`; an `iat` in the future raises `ImmatureSignatureError` [2]. Both containers share one host clock under Compose.

**`typ`.** ADR 0003 says `typ == "at+jwt"`. RFC 9068 says the resource server "MUST verify that the 'typ' header value is 'at+jwt' or 'application/at+jwt'" [11]. Accepting both costs one set lookup and matches the RFC. See the decisions list.

### Error hierarchy and mapping

| Library error | Raised for (PyJWT source [2][3][5]) | HTTP |
|---|---|---|
| `AuthzError` | Base class; never raised directly | — |
| `TokenRejected` → `TokenExpired` | `ExpiredSignatureError` | 401 `invalid_token` [12] |
| → `TokenNotYetValid` | `ImmatureSignatureError` (`nbf` or `iat`) | 401 |
| → `WrongAudience` / `WrongIssuer` | `InvalidAudienceError` / `InvalidIssuerError` | 401 |
| → `MissingClaim(claim)` | `MissingRequiredClaimError` | 401 |
| → `WrongTokenType` | the library's own `typ` check | 401 |
| → `BadSignature` | `InvalidSignatureError`, `InvalidAlgorithmError` | 401 |
| → `UnknownKey` | no key for `kid` after any allowed refetch | 401 |
| → `MalformedToken` | `DecodeError`, other `InvalidTokenError`s (`InvalidSubjectError`, `InvalidJTIError` and `InvalidIssuedAtError` aren't exported from `jwt`), the size cap, bad claims | 401 |
| `KeySetUnavailable` | JWKS can't be fetched and no stale keys are left; `InvalidKeyError` (a bad key from our side) | 503 |
| `InsufficientScope(required)` | `require_scopes()` | 403 `insufficient_scope` [12] |

Clients get a generic message. The specific reason goes to logs, never the token itself.

### Claims parsing

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class AccessClaims:
    subject: str                   # sub: the auth service's user id
    scopes: frozenset[str]         # from "scope", space-separated (RFC 9068 §2.2.3 [11])
    token_id: str                  # jti: index revocation on this, never on the raw token
    issued_at: int
    expires_at: int
    token_version: int | None = None   # only if Pillar 5 adopts it (ADR 0003)

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> Self: ...   # MalformedToken
    def to_payload(self, *, issuer: str, audience: str) -> dict[str, object]: ...

def is_str(value: object) -> TypeIs[str]: return isinstance(value, str)
```

Unknown claims and unknown scopes are ignored (a tolerant reader). That keeps additive changes non-breaking (§7).

### PyJWT advisories and the minimum version

From the GitHub advisory API [8] and the changelog [7]:

| Fixed in | 2026 advisories | Relevant to us |
|---|---|---|
| 2.12.0 | 1 (CVE-2026-32597, unknown `crit` accepted) | Yes, any header |
| 2.13.0 | 5: CVE-2026-48526 (JWK as HMAC secret), -48523 (allow-list bypass with `PyJWK`), -48522 (`PyJWKClient` SSRF), -48524 (refetch DoS), -48525 (`b64=false` DoS) | -48523 and -48524 hit a `PyJWK`/JWKS design like ours |
| 2.14.0 | 13, including CVE-2026-102268 (critical PEM-whitespace HS/asymmetric bypass), -102267 (redirects), -101917 (incomplete refetch DoS fix), -102269 (non-canonical signature), -103001 (options mutation) | Mixed-HMAC issues don't apply with `algorithms=["EdDSA"]`; the client and parsing ones do |
| 2.15.0 | 2: CVE-2026-101918 (`RecursionError` DoS before verification), -102275 (inconsistent OKP `x`/`d`) | Yes: an unauthenticated crash, and our key type |

- **Minimum: `PyJWT[crypto]>=2.15.1,<3`** (ADR 0003). 2.15.0 holds the last security fixes. 2.15.1 (2026-09-28) fixes padded-segment decoding [7].
- OSV lists no advisories for PyJWT 2.15.1, cryptography 50.0.2, cffi or pycparser [10].
- The 2.15.1 wheel was published by trusted publishing from `jpadilla/pyjwt`'s `pypi-package.yml` workflow [9].
- The repo was last pushed 2026-11-03. The top contributor is the original author [9].

**Defend it:** "The verifier pins EdDSA and binds the algorithm to each key, so the 2026 algorithm-confusion CVEs don't apply. It requires every claim it relies on, because PyJWT skips `exp` and `nbf` when they're missing. It checks `typ` itself, because PyJWT doesn't. And it turns every PyJWT exception into one typed hierarchy that maps to 401, 403 or 503 in one place."

---

## 4. DRF adapter without forcing Django on the core

**Requirement.** The main app needs a DRF authentication class and a permission class. The library's core must import and test without Django.

### Where the adapter lives

| Option | Security cost | Stability cost | Effort | Why it might lose |
|---|---|---|---|---|
| **Submodule `drf.py` + optional extra `[drf]`** | Django/DRF are installed only where asked for | One version line for core and adapter | Low | Extras gate dependencies, not files: `drf.py` ships everywhere and fails on import without DRF |
| Separate distribution (`…-drf`) | Same | Two versions to keep in step | Higher | Overkill for two consumers |
| Adapter copied into each service | — | Duplication drifts | Low | The challenge asks for it in the library |

**Recommendation: submodule plus extra.** Enforce the boundary two ways:
- **Ruff `TID251`.** Ban `django` and `rest_framework` in the library's `banned-api` table, with a per-file ignore for `drf.py`. Ruff 0.17.3 flags `from django.conf import settings` and `import rest_framework.permissions` under a bare `"django"`/`"rest_framework"` entry (verified). This fits ADR 0009's existing TID251 use.
- **A test** that runs `python -I -c "import <pkg>; import sys; assert 'django' not in sys.modules"` in a subprocess.

### How the adapter gets its configuration

DRF builds authentication and permission classes with no arguments [25].

| Option | Security cost | Stability cost | Effort | Why it might lose |
|---|---|---|---|---|
| (a) The adapter reads a Django setting (`settings.AUTHZ = {...}`) | Config spread over a settings name the library defines | Library coupled to a setting name | Low | The library reads settings, which AGENTS.md rules out |
| **(b) One-method subclass per service:** library `BearerAuthentication.get_verifier()` is abstract; the service overrides it to return a `functools.cache`d verifier built from *its* settings | Explicit; the core never reads settings | Plain inheritance | ~5 lines per service | Small boilerplate |
| (c) Class factory: `make_authentication(verifier) -> type[BaseAuthentication]` | Explicit | Dynamic class | Low | Harder to read in a traceback |
| (d) Class attribute set in `AppConfig.ready()` | Mutable global; `None` until ready | Order-dependent | Low | Tests must reset global state |

**Recommendation: (b) for authentication, a factory for permissions.** For example, `permission_classes = [require_scopes(BRANDS_WRITE)]`. The factory form type-checks cleanly. A `view.required_scopes` attribute would need `getattr` on `APIView`.

### Behavior

- **No `Authorization: Bearer` header:** return `None`. Public endpoints keep working, and RFC 6750 says to send no error code when no credentials were tried [12].
- **Invalid token:** raise `AuthenticationFailed`. `authenticate_header()` returns `Bearer realm="api"`, which makes DRF answer 401 with `WWW-Authenticate` instead of 403 [23].
- **`KeySetUnavailable`:** a small `APIException` subclass with `status_code = 503`. Fail closed, but don't blame the client's token.
- **Missing scope:** the permission returns `False` → DRF answers 403 [23]. Alternatively raise `PermissionDenied`.
- **`request.user`:** a frozen `Principal(subject)` with `is_authenticated = True` and a `pk` property. DRF's `IsAuthenticated` reads `request.user.is_authenticated`, and `UserRateThrottle` reads `request.user.pk` [25].
- **`request.auth`:** the `AccessClaims`. The stubs type `request.auth` as `Token | Any`, and `request.user` as `_User | AnonymousUser` [27]. So permissions read `request.auth` and narrow it with `is_claims(value) -> TypeIs[AccessClaims]`.
- **Main-app settings:** `REST_FRAMEWORK["UNAUTHENTICATED_USER"] = None` lets it run without `django.contrib.auth` [24]. That's a main-app decision.

### Testing and typing without a project

- **Tests (verified).** A conftest with `settings.configure(SECRET_KEY="test", INSTALLED_APPS=["rest_framework"], ROOT_URLCONF=[], REST_FRAMEWORK={"UNAUTHENTICATED_USER": None})` and `django.setup()` was enough. `APIRequestFactory` plus a tiny `APIView` then gave 401 + `WWW-Authenticate` for a missing or bad token and 200 for a good one. That was Django 5.2.18 + DRF 3.18.3, with no `django.contrib.auth`, no database and no pytest-django. DRF's own suite uses the same `pytest_configure` + `settings.configure()` pattern [26]; pytest-django documents it too [29]. pytest-django (4.14.0) isn't needed, because the adapter does no ORM work.
- **Typing (verified).** mypy 2.3.1 `--strict --python-version 3.14` passed on an adapter sketch with `django-stubs` 6.1.2 and `djangorestframework-stubs` 3.18.1, with **no plugin** and so no settings module. The django-stubs plugin needs a `django_settings_module` [28]; the adapter uses no ORM, so leave the plugin off in the library. The `TypeIs` guard narrowed `request.auth` correctly. The stubs' mypy cap follows ADR 0009: mypy 2.3.1 until drf-stubs 3.18.2 clears the cooldown.
- **Django pin.** DRF 3.18.3 requires `django>=5.2` with no upper bound [36]. Put `Django>=5.2.8,<5.3` in the library's adapter dev group so its tests run on the LTS (`django-lts` skill).

**Defend it:** "The core is pure Python plus PyJWT; Ruff bans Django imports there and a test proves it. The DRF adapter is one module behind an extra. Each service hands it a verifier through a one-method subclass, so the library never reads settings. Its tests configure Django in a conftest, with no project and no database."

---

## 5. Packaging

### Build backend

Versions and dates from PyPI [36]; build behavior verified with uv 0.13.6.

| | `uv_build` 0.13.6 (2026-10-27) | `hatchling` 1.33.0 (2026-10-28) | `setuptools` 84.2.1 (2026-10-20) |
|---|---|---|---|
| Build-time downloads | **None.** uv used its bundled backend ("direct build", verified) whenever its version matches the `requires` range [13] | **6 packages:** hatchling, packaging, pathspec, pluggy, tomlkit, trove-classifiers. Resolved at build time, **not in `uv.lock`**; the cooldown applies to them (verified with a 2026-10-01 cutoff → hatchling 1.32.4) | Not measured; more |
| Version policy | uv's: the minor version marks breaking changes. Docs recommend an upper bound [13][14]. Minors 0.9 (2025-10-07), 0.10, 0.11 (2026-03-23), 0.12 (2026-07-28), 0.13 (2026-10-09). The 0.9, 0.10, 0.12 and 0.13 notes say "no breaking changes" to the backend [21] | 1.x | Two majors in 2026 (83.0.0 in July, 84.0.0 in August) |
| Fit | Pure Python only; `src/<name>` default; **static `version` required** (verified: `missing field version`) | Flexible, plugins, dynamic versions | Legacy surface |
| Reproducible | **Yes**: same wheel hash across rebuilds and mtime changes (verified) | Not tested | Not tested |

**Recommendation: `uv_build>=0.13.6,<0.14`**, bumped together with the uv binary in the images (ADR 0008 copies uv 0.13.x in). The extra effort is one line per uv minor. In exchange, building the library downloads nothing at all, so no unlocked build dependencies can reach the image.

### Layout and metadata

- **`src/` layout.** It stops tests from importing the in-repo copy instead of the installed one, and keeps editable installs from exposing non-package files [33]. pytest recommends a src layout and `--import-mode=importlib` for new projects [30]. It's also `uv_build`'s default [13].
- **`py.typed`.** The typing spec requires it for type checkers to read inline types [32]. `uv_build` includes it automatically (verified in the wheel listing).
- **Version source.** A static `version` in `pyproject.toml`, bumped with `uv version --bump minor` [22]. Read it at runtime with `importlib.metadata.version()` for the User-Agent; don't keep a second `__version__` literal.
- **`requires-python = ">=3.14,<3.15"`**, as the `uv-only` skill says. Note that uv ignores upper bounds on `requires-python` when it evaluates *dependencies* [17], so this states the support target; it isn't enforced on consumers.
- **Dependency ranges: wide in the library, exact in each service's `uv.lock`.**
  - `PyJWT[crypto]>=2.15.1,<3`.
  - `cryptography>=50.0.2`, declared directly because the library imports `Ed25519PublicKey`. This sets a security floor for both services; the auth service needs it anyway.
  - Extra `drf = ["djangorestframework>=3.18.3,<4"]`. ADR 0002's tighter `<3.19` stays in the services.
  - The core pulls in 4 runtime packages in total: PyJWT, cryptography, cffi, pycparser (verified lock).

```toml
[project]
name = "brandreviews-authz"             # see "Name" below; the user's call
version = "1.0.0"
requires-python = ">=3.14,<3.15"
dependencies = ["PyJWT[crypto]>=2.15.1,<3", "cryptography>=50.0.2"]

[project.optional-dependencies]
drf = ["djangorestframework>=3.18.3,<4"]

[dependency-groups]
dev = ["pytest>=9.2.0,<10", "mypy>=2.3.1,<2.4", "ruff>=0.17.3,<0.18"]
drf-dev = ["Django>=5.2.8,<5.3", "django-stubs>=6.1.2,<6.2", "djangorestframework-stubs>=3.18.1,<3.19"]

[build-system]
requires = ["uv_build>=0.13.6,<0.14"]
build-backend = "uv_build"

[tool.uv]
exclude-newer = "7 days"
cache-keys = [{ file = "pyproject.toml" }, { file = "src/**/*.py" }]   # see §6
```

### Name and dependency confusion

uv's default `index-strategy = "first-index"` exists to stop dependency confusion across *multiple indexes* [20]. For a path source the question is different: does uv ever ask an index at all?
- **Normal locking:** with the path source, `uv lock -v` never requested `pypi.org/simple/<name>/`. It only fetched PyJWT, cryptography, cffi and pycparser (verified).
- **`uv lock --no-sources`:** uv *did* request `pypi.org/simple/<name>/` (verified). A public project with that name would have been installed.
- **Other tools:** "Sources are only respected by uv" [15]. pip, or a tool reading only `[project]`, goes to PyPI.

So the name must not exist on PyPI, and should be distinctive enough that nobody registers it by chance:
- `shared` **exists** on PyPI (0.0.32, "Data exchange and persistence based on human-readable files") [36].
- `brandreviews-authz`, `reviews-authz`, `ca-authz` and `shared-lib` returned 404 on both the JSON and simple APIs on 2026-11-09. That's a snapshot: anyone can register a free name.
- Don't register anything (out of scope). Never run `--no-sources` or pip against the services.

**Recommendation:** a project-prefixed name such as `brandreviews-authz` (import `brandreviews_authz`), in a directory named `shared-lib/`.

**Defend it:** "It's a pure-Python, src-layout package with `py.typed`, built by uv's bundled backend, so building it downloads nothing. It declares wide dependency ranges, and each service's lockfile pins the exact versions. The name is prefixed and unclaimed on PyPI, and uv never asks PyPI for it because of the path source."

---

## 6. Install by local path, and how upgrades reach each service

### What each install option pins

| Option | What `uv.lock` records (verified) | Independent version per service? | Docker build needs | Security | Why it might lose |
|---|---|---|---|---|---|
| **Directory path, `editable = true` locally** (the `uv-only` skill's form) | `source = { editable = "../shared-lib" }`, the version, declared deps. **No content hash** | No: both use the library at the same commit | The library dir in the build context | No index lookup; content is whatever's on disk at that commit | The pin is the commit, not the lockfile |
| Directory path, non-editable | `source = { directory = … }`; same, no hash | No | Same | Same | **Stale code** in a local venv after a code-only change, until `cache-keys` covers `src/**/*.py` (verified both ways) |
| Wheel path (`../shared-lib/dist/<name>-1.2.0-py3-none-any.whl`) | `source = { path = … }` plus **sha256**. A tampered wheel fails `uv sync --locked` (verified) | **Yes**: each service points at its own wheel | The wheel file | Tamper-evident; reproducible wheels let CI rebuild and compare | Binary artifacts in git; an extra release step; changes the `uv-only` skill's source form |
| Git URL + tag + `subdirectory` | Tag pinned to the **commit SHA** (verified) | Yes | git + network to GitHub (+ credentials if private) at build time | `exclude-newer` doesn't apply to git sources [17] (moot for our own code) | Network and credentials in builds; slow local loop |
| uv workspace | One lockfile for the whole workspace [16] | No; also one resolution for *all* third-party packages | The repo root | — | **Couples upgrades:** bumping Django for one service bumps it for both. Contradicts the skill's "own `uv.lock`" per project |
| Private index | Hashes | Yes | Index credentials | Needs trusted publishing | Infrastructure out of scope |

**How a version bump propagates (verified):**
- Bumping `version` in the library makes `uv lock --check` fail in each service until it runs `uv lock`, so `uv sync --locked` in CI and Docker fails too.
- Plain `uv lock` updates a path source's version (`Updated … v0.2.0 -> v0.3.0`). `uv lock --upgrade-package <name>` does the same thing.
- Adding a dependency to the library also fails `--check`.
- A code-only change passes `--check` silently.

**Recommendation: directory path, editable for local development, non-editable in images.**
- Require a version bump on every library change: a CI check fails if `shared-lib/src` changed and `version` didn't. Each service then re-locks and runs its tests in the same PR.
- Keep `cache-keys` in the library [18], so non-editable installs (and Docker builds that use a uv cache mount) rebuild on code changes.
- If the user wants each service on its own library version, move to wheel path sources. Each service then pins a hashed artifact, at the cost of committing wheels.

**README-ready: "how a new version reaches each service"**
1. Change `shared-lib/`, add a `CHANGELOG.md` entry, run `uv version --bump <part>` there.
2. Run `uv lock` in `main-app/` and `auth-service/`. CI's `uv lock --check` fails until you do.
3. Run each service's tests. Commit the library and both lockfiles together.
4. Deploy each service on its own schedule. A library change must work with the token format the *other* service is running (§7).

### Docker

The uv lock path `../shared-lib` must resolve inside the build stage. The Compose spec's `additional_contexts` adds a named context [34], and `COPY --from=<name>` reads from it [35]. The service's own context then stays minimal. A repo-root context would send the repo-root `.env` to the builder unless `.dockerignore` excludes it.

```yaml
main-app:
  build:
    context: ./main-app
    additional_contexts:
      shared-lib: ./shared-lib
```
```dockerfile
FROM python:3.14-slim-trixie@sha256:<digest> AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.6@sha256:<digest> /uv /bin/uv
COPY --from=shared-lib . /src/shared-lib
WORKDIR /src/main-app
COPY . .
RUN uv sync --locked --no-dev --no-editable     # library installed as a real copy
FROM python:3.14-slim-trixie@sha256:<digest>
# copy /src/main-app/.venv to the same path, add a non-root user, USER it (ADR 0008)
```

- **`--no-editable`.** `uv sync --no-editable` installs a real `<pkg>/` directory where the editable sync installed a `.pth` file (verified). The runtime stage then doesn't need the library source [19].
- **No downloads for the library build.** With `uv_build` and a matching uv binary, building the library inside the image fetches nothing (verified).

**Defend it:** "Both services install the library from its directory, so uv never looks the name up on an index. A version bump breaks each service's `uv lock --check` until it re-locks and re-tests in the same PR. Images install it non-editable from a named build context, so the runtime image has no library source and no repo-root secrets in its context. If we needed each service on a different library version, I'd switch to hashed wheel paths."

---

## 7. Versioning and breaking changes

**SemVer for the library**, starting at **1.0.0** when it first ships. Under 0.x, SemVer gives no compatibility promise, and this library *is* a contract.

| Bump | Examples |
|---|---|
| Patch | A bug fix with no API or claim change |
| Minor (expand) | New optional claim parsed; new function; old API marked deprecated |
| Major (contract) | Deprecated API removed; a claim made required; an old token shape no longer accepted |

**`CHANGELOG.md`** uses Added / Changed / Deprecated / Removed / Fixed / Security, the way PyJWT does [7].

**Deprecations in the expand phase** use stdlib `warnings.deprecated` (Python 3.13+, PEP 702). It warns at runtime, and type checkers flag uses statically [31]. The services' mypy config already enables the `deprecated` error code (`typing-and-validation.md` §3). Give the warning its own category so services can make *only the library's* deprecations fatal, the way the `django-lts` skill does for Django's:

```python
class AuthzDeprecationWarning(DeprecationWarning): ...

@deprecated("Use require_scopes()", category=AuthzDeprecationWarning)
def has_scope(claims: AccessClaims, scope: str) -> bool: ...
# each service: filterwarnings = ["error::brandreviews_authz.AuthzDeprecationWarning"]
```

**The overlap rule for token changes:**
1. Verifiers learn to accept the new shape first.
2. The issuer starts emitting it, dual-writing if old verifiers may still run.
3. Wait one token lifetime plus leeway (≤ 15 min + 30 s), so no old-shape token is still valid.
4. The issuer stops emitting the old shape.
5. Wait again; then a major release removes the old path.

The verifier ignores unknown claims and scopes (§3), so purely additive changes need no coordination.

**Walkthrough A: rename `scope` (space-separated string) to `scp` (JSON array)**
| Step | Library | Deploy | Accepts |
|---|---|---|---|
| 1 | 1.3.0: `from_payload` reads `scp`, falls back to `scope`, counts fallbacks | main app | both |
| 2 | 1.4.0: `to_payload` writes **both** | auth service | old verifiers read `scope`, new read `scp` |
| 3 | — | wait ≥ 15 min 30 s; the fallback counter in the main app drops to zero | — |
| 4 | 1.5.0: `to_payload` writes `scp` only | auth service (only after every verifier runs ≥ 1.3.0) | — |
| 5 | **2.0.0**: `scope` fallback removed | main app, ≥ one token lifetime after step 4 | new only |

**Walkthrough B: make `token_version` required** (the revocation aid in ADR 0003)
1. 1.6.0 adds `token_version: int | None`; tokens are accepted with or without it.
2. The auth service emits `tv`.
3. After one token lifetime, 2.0.0 makes it required, and the main app deploys it.

**Walkthrough C: signing-key rotation** (an operations procedure, no library release)
1. The auth service publishes the new key next to the old one.
2. It waits longer than `refresh_after` + `min_refetch_interval`, so every verifier has the new key without needing an unknown-`kid` refetch.
3. It signs with the new key.
4. After one token lifetime, it removes the old key.

The same overlap covers an algorithm change. During the overlap, `algorithms=["EdDSA", "ES256"]` is safe because each `PyJWK` binds its own algorithm [3].

**The monorepo caveat.** With directory path sources, both services build against the library at the *same commit*. Version skew happens only through deploy timing, so CI should test it:
- Keep golden tokens from the previous library version in `tests/fixtures/`, so the verifier test also checks "old issuer → new verifier".
- The JWKS `User-Agent` names the library version (§2), so the auth service's logs show which verifier versions are still live before a contract release.

**Defend it:** "A breaking change ships in three releases. Verifiers accept old and new; then the issuer switches, dual-writing if needed; after one token lifetime the old path is removed. No moment needs both services deployed together. Deprecated APIs warn with a library-specific warning that each service's tests turn into errors, and the JWKS User-Agent tells me which versions are still running."

---

## 8. Tests without Django

**Layout.** `tests/` sits next to `src/` and never ships. Signing lives only here.
- **Keys and minting.** A `conftest.py` fixture makes a fresh `Ed25519PrivateKey.generate()` per test. A `mint(**overrides)` helper calls `jwt.encode` with that key and `headers={"typ": "at+jwt", "kid": ...}`. Signing in tests is fine; signing in `src/` isn't.
- **Key sets.** Build test JWKS with `OKPAlgorithm.to_jwk(public_key, as_dict=True)` [6].
- **Fakes.** `FakeFetcher` returns queued bytes or raises; `FakeClock` is a callable that tests advance. Both are injected through the Protocols, so the cache tests never touch the network.
- **Fetcher tests.** Two or three loopback tests for `UrllibFetcher` itself: a redirect refused, an oversize body refused, a timeout. They use stdlib `http.server` on `127.0.0.1` in a thread.

**Time control without a dependency.**
- **Cache tests** use the injected clock.
- **`exp`/`nbf` tests** mint tokens relative to `int(time.time())`, with margins ≥ 60 s beyond the 30 s leeway. PyJWT reads `datetime.now(tz=timezone.utc)` internally [2], so there's no clock to inject.
- **freezegun** is a poor fit: last release 1.5.5 on 2025-08-09, classifiers stop at 3.13 [36].
- **time-machine** 3.6.0 (2026-10-25) supports 3.14 [36], but it's a C extension nobody here needs.

**Hypothesis or not.** Hypothesis 6.170.14 (2026-10-30) is cooldown-safe; it releases several times a week and has one runtime dependency, `sortedcontainers` [36]. It earns its place on exactly one property: "for any string, `verify()` returns `AccessClaims` or raises `TokenRejected`, never anything else". PyJWT leaked raw `TypeError` and `RecursionError` from untrusted input several times in 2026, fixed in 2.14.0 and 2.15.0 [7][8]. It would be dev-only and never reach an image. A parametrized table of nasty inputs is the zero-dependency fallback. Open decision.

**Must-have cases**, each tied to an RFC or a 2026 advisory:
- Valid token → claims. Expired. `nbf` in the future. `iat` in the future.
- Leeway: `exp` 20 s ago passes, 90 s ago fails.
- Wrong `aud`; `aud` as a list when `strict_aud` is on. Wrong `iss`. Each required claim missing.
- `alg: none`. `alg: HS256` signed with the public key bytes (CVE-2026-48526 class). `typ: JWT`; `typ` missing; `application/at+jwt` accepted.
- `!!!!` appended to the signature (CVE-2026-102269). A deeply nested payload (CVE-2026-101918). Oversize token.
- Unknown `kid`: exactly one refetch, then none within 30 s, **including after a failed fetch**. Outage: known `kid` served stale until `max_stale`, then `KeySetUnavailable`.
- JWKS containing `oct`, Ed448, or `d` → that key ignored. JWKS as HTML or non-object → `KeySetUnavailable`.
- Scopes: missing → empty set; not a string → `MalformedToken`; unknown scopes ignored.
- Golden payload fixture: `to_payload()` output equals the committed JSON, and `from_payload()` reads it back.
- Adapter (with `pytest.importorskip("rest_framework")`): no header → anonymous; bad token → 401 + `WWW-Authenticate`; missing scope → 403; keys unavailable → 503.
- Core imports without Django (subprocess test).

**CI commands** (all through uv, per the skill):
```sh
uv run pytest                                            # core; DRF absent, adapter tests skip
uv run --extra drf --group drf-dev pytest                # everything, Django 5.2
uv run --extra drf --group drf-dev mypy --strict src tests
uv run ruff check                                        # ANN, S, TC, TID251 (bans Django in core)
```

**Defend it:** "The core tests are plain pytest, with a fresh Ed25519 key per test and a fake fetcher and clock. No network, no Django, no time-freezing library. Every 2026 PyJWT advisory that touches our design is a test. The adapter tests configure Django in a conftest and are skipped when DRF isn't installed, which also proves the core doesn't need it."

---

## Proposed package layout

```text
shared-lib/
├── pyproject.toml            # uv_build, static version, wide ranges, [drf] extra, cache-keys
├── CHANGELOG.md
├── README.md                 # what's in, who uses what, how to run the tests
├── src/brandreviews_authz/
│   ├── __init__.py           # re-exports the core API; never imports drf      (both)
│   ├── py.typed              # PEP 561 marker                                  (both)
│   ├── profile.py            # ALGORITHM, TOKEN_TYPE, REQUIRED_CLAIMS, limits  (both)
│   ├── scopes.py             # scope name constants                            (both)
│   ├── claims.py             # AccessClaims, from_payload/to_payload, guards   (both)
│   ├── errors.py             # AuthzError hierarchy, AuthzDeprecationWarning   (both)
│   ├── jwks.py               # public_jwk() (publish), parse_jwks() (consume)  (both)
│   ├── keys.py               # KeyProvider Protocol, StaticKeyProvider         (both: auth for contract tests)
│   ├── jwks_client.py        # Fetcher, UrllibFetcher, CachedJwksKeyProvider   (main app only)
│   ├── verify.py             # TokenVerifier                                   (main app; auth contract tests)
│   ├── permissions.py        # has_scopes(), require_scopes() (pure Python)    (main app; auth if /me)
│   └── drf.py                # BearerAuthentication, Principal, require_scopes (main app; auth if /me)
└── tests/
    ├── conftest.py           # Ed25519 key per test, mint() helper (signing lives only here)
    ├── fakes.py              # FakeFetcher, FakeClock
    ├── fixtures/             # golden payload + tokens from previous versions
    ├── test_claims.py  test_jwks.py  test_jwks_client.py  test_verify.py
    ├── test_core_imports_without_django.py
    └── drf/conftest.py + test_drf.py   # settings.configure(); importorskip("rest_framework")
```

## Public API sketch (signatures only)

```python
# profile.py
ALGORITHM: Final = "EdDSA"
TOKEN_TYPE: Final = "at+jwt"
REQUIRED_CLAIMS: Final[tuple[str, ...]]
MAX_TOKEN_BYTES: Final = 4096

# claims.py
@dataclass(frozen=True, slots=True, kw_only=True)
class AccessClaims:
    subject: str; scopes: frozenset[str]; token_id: str
    issued_at: int; expires_at: int; token_version: int | None = None
    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> Self: ...
    def to_payload(self, *, issuer: str, audience: str) -> dict[str, object]: ...
def is_claims(value: object) -> TypeIs[AccessClaims]: ...

# jwks.py
def public_jwk(key: Ed25519PublicKey, *, kid: str) -> dict[str, str]: ...   # rejects private keys
def parse_jwks(raw: bytes) -> Mapping[str, PyJWK]: ...                      # KeySetUnavailable

# keys.py / jwks_client.py
class KeyProvider(Protocol):
    def get(self, kid: str) -> PyJWK: ...
class StaticKeyProvider:
    def __init__(self, keys: Mapping[str, Ed25519PublicKey]) -> None: ...
class Fetcher(Protocol):
    def fetch(self) -> bytes: ...
class UrllibFetcher:
    def __init__(self, url: str, *, timeout: float = 2.0, max_bytes: int = 65_536,
                 ssl_context: ssl.SSLContext | None = None) -> None: ...
class CachedJwksKeyProvider:
    def __init__(self, fetcher: Fetcher, *, refresh_after: float = 300.0, max_stale: float = 3600.0,
                 min_refetch_interval: float = 30.0, clock: Callable[[], float] = time.monotonic) -> None: ...

# verify.py
class TokenVerifier:
    def __init__(self, keys: KeyProvider, *, issuer: str, audience: str, leeway: float = 30.0) -> None: ...
    def verify(self, token: str) -> AccessClaims: ...   # TokenRejected | KeySetUnavailable

# permissions.py
def has_scopes(claims: AccessClaims, *required: str) -> bool: ...
def require_scopes(claims: AccessClaims, *required: str) -> None: ...   # InsufficientScope

# drf.py  (needs the [drf] extra)
@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    is_authenticated: bool = True
    @property
    def pk(self) -> str: ...
class BearerAuthentication(BaseAuthentication):
    def get_verifier(self) -> TokenVerifier: ...          # abstract; each service overrides
    def authenticate(self, request: Request) -> tuple[Principal, AccessClaims] | None: ...
    def authenticate_header(self, request: Request) -> str: ...
def require_scopes(*required: str) -> type[BasePermission]: ...
class KeysUnavailable(APIException): ...                   # status_code = 503
```

---

## Open decisions for the user

| # | Question | Options | Recommendation |
|---|---|---|---|
| 1 | JWKS client: own it or use PyJWT's? | A. `PyJWKClient` + wrapper (~30 lines) · C. custom stdlib provider (~100 lines) | **C**: the outage and amplification behavior was verified, not guessed |
| 2 | Auth service down past the refresh interval: fail closed or serve stale keys? | Fail closed after `refresh_after` · stale up to a bound | **Stale up to 60 min, rate-limited retries.** Revocation by key removal still lands within 5 min while auth is up |
| 3 | Does the auth service use the verifier in production? | Contract tests only · plus `GET /api/me/` with the DRF adapter | **Contract tests at least.** `/me` if Pillar 5 agrees |
| 4 | Where does the JWKS client live? | Library (main-app-only module) · main app | **Library**, flagged in the README |
| 5 | How do services install the library? | Directory path · hashed wheel path · git tag · workspace | **Directory path** (editable locally, `--no-editable` in images) + a CI-enforced version bump |
| 6 | Package name | `brandreviews-authz` · `reviews-authz` · other prefixed name | **`brandreviews-authz`** (free on PyPI on 2026-11-09) |
| 7 | Build backend | `uv_build` · `hatchling` | **`uv_build`**: no build-time downloads |
| 8 | `typ` check | Exact `at+jwt` (ADR wording) · `at+jwt` or `application/at+jwt` (RFC 9068) | **Both RFC values**, lower-cased |
| 9 | Required claims and `aud` form | Add `client_id` (RFC 9068)? `strict_aud`? | Require `iss sub aud exp iat jti nbf`. `client_id` and `strict_aud` only if Pillar 5 emits single-audience tokens with `client_id` |
| 10 | Hypothesis | Dev-only, one fuzz property · parametrized table only | **Dev-only**, one property on `verify()` |
| 11 | DRF range in the `[drf]` extra | `<4` (library style) · `<3.19` (matches ADR 0002) | **`<4`**; the services keep `<3.19` |

## Conflicts with accepted decisions

**None found.** Notes that touch accepted records:
- **ADR 0003, `typ`.** The ADR's `typ == "at+jwt"` is stricter than RFC 9068, which also allows `application/at+jwt` [11]. It's harmless with our own issuer; decision 8 above.
- **ADR 0003's consequence** "keeps verifying … until its cached JWKS expires" is exactly `PyJWKClient`'s behavior (verified). If decision 2 picks stale-if-error, record it in a new ADR that links back, per ADR 0000.
- **ADR 0002 pins `djangorestframework>=3.18.3,<3.19`** for the services. A wider library range doesn't change that; each service's lockfile still resolves inside its own pin.
- **The `uv-only` skill** prescribes `{ path = …, editable = true }` and "own `uv.lock`" per project. That rules out a workspace. Choosing wheel path sources (decision 5) would mean editing the skill.

## Not verified

- Behavior on Python 3.14 itself: everything ran on 3.12.3, with mypy targeting 3.14. Hypothesis wasn't run.
- The 0.11 uv changelog's statement about the build backend (the 0.9, 0.10, 0.12 and 0.13 notes were read).
- Docker specifics:
  - How BuildKit applies `.dockerignore` to a named additional context.
  - Whether a Docker uv cache mount reuses a stale library wheel without `cache-keys` (only the local equivalent was tested).
- The `RecursionError` from a deeply nested JWKS response in `PyJWKClient.fetch_data`: taken from the 2.15.0 advisory text and the 2.15.1 source, not run.
- The advisory database leaves the patched version blank for GHSA-gvp8-978c-rx2q. The fix was confirmed in the 2.15.1 source (the options dict is copied) and in a changelog commit dated 2026-10-12. Its exact first release wasn't confirmed.
- Whether uv checks PEP 740 attestations on install. Not checked; assume it doesn't.
- PyPI name availability is a snapshot from 2026-11-09. A 404 also can't tell a free name from a prohibited one.
- Maintainer identities come from GitHub contributor counts and PyPI provenance metadata, not PyPI's web UI.

## Sources

PyJWT
1. PyJWT 2.15.1 `jwt/jwks_client.py`: https://github.com/jpadilla/pyjwt/blob/2.15.1/jwt/jwks_client.py
2. PyJWT 2.15.1 `jwt/api_jwt.py` (options, `require`, claim checks, `strict_aud`, `datetime.now`): https://github.com/jpadilla/pyjwt/blob/2.15.1/jwt/api_jwt.py
3. PyJWT 2.15.1 `jwt/api_jws.py` (header validation, alg binding to `PyJWK`, no `typ` check): https://github.com/jpadilla/pyjwt/blob/2.15.1/jwt/api_jws.py
4. PyJWT 2.15.1 `jwt/api_jwk.py` and `jwt/jwk_set_cache.py`: https://github.com/jpadilla/pyjwt/blob/2.15.1/jwt/api_jwk.py · https://github.com/jpadilla/pyjwt/blob/2.15.1/jwt/jwk_set_cache.py
5. PyJWT 2.15.1 `jwt/exceptions.py` and `jwt/__init__.py`: https://github.com/jpadilla/pyjwt/blob/2.15.1/jwt/exceptions.py
6. PyJWT 2.15.1 `jwt/algorithms.py` (`OKPAlgorithm.to_jwk`/`from_jwk`): https://github.com/jpadilla/pyjwt/blob/2.15.1/jwt/algorithms.py
7. PyJWT CHANGELOG at 2.15.1 (also via Context7 `/jpadilla/pyjwt/2.15.1`): https://github.com/jpadilla/pyjwt/blob/2.15.1/CHANGELOG.rst
8. PyJWT security advisories, GitHub API, fetched 2026-11-09 (23 total, 21 from 2026): https://github.com/jpadilla/pyjwt/security/advisories
9. PyPI JSON, PyJWT (release dates, 2.15.1 = 2026-09-28), PyPI integrity/provenance API for `pyjwt-2.15.1-py3-none-any.whl`, and GitHub repo/contributors/commits API, all 2026-11-09: https://pypi.org/pypi/PyJWT/json
10. OSV queries for PyJWT 2.15.1, cryptography 50.0.2, djangorestframework 3.18.3, cffi 2.1.1, pycparser 3.12 (2026-11-09): https://api.osv.dev/v1/query

Standards
11. RFC 9068, JWT Profile for OAuth 2.0 Access Tokens (§2.1 `typ`, §2.2 required claims, §4 validation): https://www.rfc-editor.org/rfc/rfc9068
12. RFC 6750, Bearer Token Usage (§3.1 `invalid_token` → 401, `insufficient_scope` → 403): https://www.rfc-editor.org/rfc/rfc6750

uv (docs at tag 0.13.6 unless noted; Context7 `/astral-sh/uv/0.13.5`)
13. The uv build backend: https://github.com/astral-sh/uv/blob/0.13.6/docs/concepts/build-backend.md
14. Versioning policy: https://github.com/astral-sh/uv/blob/0.13.6/docs/reference/policies/versioning.md
15. Managing dependencies (path, git, editable, build dependencies, "sources are only respected by uv"): https://github.com/astral-sh/uv/blob/0.13.6/docs/concepts/projects/dependencies.md
16. Workspaces (single lockfile; when not to use): https://github.com/astral-sh/uv/blob/0.13.6/docs/concepts/projects/workspaces.md
17. Resolution (`requires-python` upper bounds ignored; `exclude-newer` registry-only): https://github.com/astral-sh/uv/blob/0.13.6/docs/concepts/resolution.md
18. Cache, dynamic metadata and `cache-keys`: https://github.com/astral-sh/uv/blob/0.13.6/docs/concepts/cache.md
19. Using uv in Docker (`--no-editable`, intermediate layers): https://github.com/astral-sh/uv/blob/0.13.6/docs/guides/integration/docker.md
20. Settings reference (`cache-keys` globs, `index-strategy` default and dependency-confusion rationale), docs site 2026-11-09: https://docs.astral.sh/uv/reference/settings/
21. uv changelogs: 0.13.0 (2026-10-09), 0.12.0 (2026-07-28), 0.11.0 (2026-03-23), 0.10.0, 0.9.0 (2025-10-07): https://github.com/astral-sh/uv/blob/0.13.6/CHANGELOG.md · https://github.com/astral-sh/uv/tree/0.13.6/changelogs
22. Building and publishing a package (`uv version --bump`): https://github.com/astral-sh/uv/blob/0.13.6/docs/guides/package.md

Django REST framework and typing
23. DRF 3.18.3 authentication and permissions guides (Context7 `/encode/django-rest-framework/3.18.3`): https://github.com/encode/django-rest-framework/blob/3.18.3/docs/api-guide/authentication.md · https://github.com/encode/django-rest-framework/blob/3.18.3/docs/api-guide/permissions.md
24. DRF 3.18.3 settings (`UNAUTHENTICATED_USER`): https://github.com/encode/django-rest-framework/blob/3.18.3/docs/api-guide/settings.md
25. DRF 3.18.3 source: `views.py` (`get_authenticators`/`get_permissions`), `permissions.py`, `throttling.py`: https://github.com/encode/django-rest-framework/tree/3.18.3/rest_framework
26. DRF 3.18.3 `tests/conftest.py` and `pyproject.toml` (test setup with `settings.configure`): https://github.com/encode/django-rest-framework/blob/3.18.3/tests/conftest.py
27. djangorestframework-stubs 3.18.1 `authentication.pyi`, `permissions.pyi`, `request.pyi`: https://github.com/typeddjango/djangorestframework-stubs/tree/3.18.1/rest_framework-stubs
28. django-stubs README (plugin needs `django_settings_module`), 2026-11-09: https://github.com/typeddjango/django-stubs#readme
29. pytest-django, configuring Django (`settings.configure()`): https://github.com/pytest-dev/pytest-django/blob/main/docs/configuring_django.rst
30. pytest good integration practices (src layout, `importlib` import mode), stable docs for 9.2: https://docs.pytest.org/en/stable/explanation/goodpractices.html

Python and packaging
31. Python 3.14 `warnings.deprecated` (added 3.13, PEP 702) and `typing.TypeIs` (added 3.13): https://docs.python.org/3.14/library/warnings.html · https://docs.python.org/3.14/library/typing.html
32. Typing spec, distributing type information (`py.typed`): https://typing.python.org/en/latest/spec/distributing.html
33. Packaging guide, src layout vs flat layout: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/

Docker
34. Compose file build reference (`additional_contexts`): https://docs.docker.com/reference/compose-file/build/
35. Dockerfile reference (`COPY --from` with named contexts, `--chown`): https://docs.docker.com/reference/dockerfile/

Package metadata
36. PyPI JSON API, 2026-11-09: hatchling 1.33.0, uv-build 0.13.6/0.13.7, setuptools 84.2.1, pytest 9.2.0, pytest-django 4.14.0, hypothesis 6.170.14/15, time-machine 3.6.0, freezegun 1.5.5, mypy 2.3.1/2.4.1, django-stubs 6.1.2, djangorestframework-stubs 3.18.1/3.18.2, cryptography 50.0.2, Django 5.2.19, djangorestframework 3.18.3 (`requires_dist: django>=5.2`), `shared` 0.0.32; name checks via `https://pypi.org/pypi/<name>/json` and `https://pypi.org/simple/<name>/`.

Local experiments
37. Session scratchpad, 2026-11-09 (not in the repo): uv 0.13.6, CPython 3.12.3, PyJWT 2.15.1, cryptography 50.0.2, Django 5.2.18, DRF 3.18.3, mypy 2.3.1, Ruff 0.17.3. Tested:
    - lockfile entries for directory, wheel and git sources;
    - `--check` after code, version and dependency changes;
    - `--upgrade-package`, `cache-keys`, `--no-editable`;
    - build-dependency fetching for `uv_build` vs `hatchling`, with and without a cutoff;
    - wheel reproducibility, and index lookups with and without `--no-sources`;
    - `PyJWKClient` outage, cooldown and error behavior, plus the `typ` and `require` behavior of `decode`;
    - DRF adapter without a project; mypy strict on the adapter; Ruff TID251 scope.
