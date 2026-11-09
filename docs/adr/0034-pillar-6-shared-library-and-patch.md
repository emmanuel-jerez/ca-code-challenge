# 0034. Pillar 6: the shared library, its use in both services, and the `PATCH`

- Status: Accepted
- Date: 2026-11-09

## Context
ADRs 0016 (token checks, `PyJWKClient`, fail closed, 503) and 0025 (name,
`uv_build`, path install, version bump) had already settled most of the
library. ADR 0033 deferred the protected `PATCH` to this pillar, because
it needs the verifier. ADR 0027 left `PATCH` concurrency open. The research
(`docs/research/pillar-6-shared-library.md`, "Open decisions") left the rest open.
Facts that shaped them:

- The auth service already signed tokens and built its JWK by hand
  (`accounts/tokens.py`). The main app had no verifier.
- CHALLENGE.md says only code both services use belongs in the library.
  Verification is a main-app job, so the auth service needs a real use
  of the library, not just a test.
- `Brand.short_description` is a 300-character column. The import writes it
  only when it creates a brand, then editors own it (ADR 0026). The main app
  has no `GET /api/brands/<slug>/`.
- PyJWT 2.15.1's `PyJWKClient` raises the same bare `PyJWKClientError` for an
  unknown `kid` and for a JWKS that isn't a JSON object (read from source).
- gunicorn runs 2 sync workers (ADR 0008), each with its own JWKS cache.

The user chose items 1–4 on this date, taking the recommendation each time.
Items 5–18 are implementation defaults the agent took while building, flagged
for review in the Pillar 6 pull request.

## Options considered
1. **What this pull request covers.**
   - The library only. Rejected: the README's "call the protected endpoint"
     step would still be missing.
   - The library, the `PATCH` and the main-app import reading
     `secrets/user-map.json`. Rejected: the user map is ADR 0020's concern,
     not this one, and one pull request would span three concerns.
   - The library, both services adopting it, and the `PATCH`. Chosen. The user
     map gets its own pull request.
2. **How the auth service uses the library.**
   - Contract tests only. Rejected: it's hard to argue the library is
     "actually used" by both services.
   - The minting path plus a token-protected `GET /api/me/`. Rejected: more
     surface for a walkthrough the `PATCH` already gives.
   - The minting path plus a contract test. Chosen. In production the auth
     service builds `AccessClaims`, signs `to_payload()` with the profile's
     `alg` and `typ`, and publishes `public_jwk()`. A test verifies what it
     mints with the library's `TokenVerifier`.
3. **`PATCH` concurrency.**
   - Optional `If-Match`. Rejected: clients have nowhere to get the first
     ETag except a previous `PATCH`.
   - Required `If-Match` (428, 412). Rejected: needs a new detail endpoint and
     an extra step in the curl walkthrough, for a single 300-character field.
   - Last write wins, logged. Chosen. Each write logs the slug, `sub` and
     `jti`.
4. **The `PATCH` body and reply.**
   - The full card in the reply. Rejected: the listing's prefetch queries on
     every write.
   - A lenient body that ignores unknown fields and allows empty strings.
     Rejected: a client that thinks it renamed a brand would hear 200.
   - A strict body and a minimal reply. Chosen. The body is
     `{"short_description": str}`: plain text, trimmed, 1–300 characters, and
     any other field is a 400. The reply is `200 {"slug", "short_description"}`.
5. **Modules.** A separate `permissions.py` was rejected: one function didn't
   earn a module. Chosen: `profile`, `scopes`, `claims` (with
   `has_scopes()`), `errors`, `jwks`, `verify` and `drf`. Each is used by
   both services, except `JwksClientKeyProvider` (main app only), which sits
   next to `public_jwk()` so the publisher and the parser share one file.
6. **Errors.** The research's nine `TokenRejected` subclasses were rejected:
   they all map to 401, and only the logs differ. Chosen: `TokenRejected`
   with a reason message, `KeySetUnavailable` (503) and
   `InsufficientScope` (403).
7. **What the verifier checks before looking up a key.** It rejects a token
   over 4 KiB or one that isn't a compact JWS with no padding. It also rejects
   a `typ` other than `at+jwt` or `application/at+jwt` (case-insensitive), an
   `alg` other than `EdDSA`, and a `kid` that isn't a 43-character thumbprint.
   Junk then can't trigger a JWKS refetch, and each token has exactly one
   accepted spelling. After the signature check it re-checks `typ` and
   requires `client_id`, `scope` and a UUID `sub`. Every claim in ADR 0016 is
   required, with `strict_aud`.
8. **Telling 503 from 401 with `PyJWKClient`.** Matching on PyJWT's error
   messages was rejected. The wrapper loads the key set first, so a failure
   there is 503, and a missing `kid` afterwards is 401. A key that isn't an
   Ed25519 public key (HMAC, Ed448, or one carrying `d`) is 503: the auth
   service published something wrong. The fetch sends
   `User-Agent: brandreviews-authz/<version>`.
9. **Fuzzing.** Hypothesis was rejected as a new dev dependency. Chosen: a
   parametrized table of malformed tokens, with one case per 2026 PyJWT
   advisory that touches this design.
10. **Dev dependencies.** A separate `drf-dev` group was rejected. Chosen: one
    `dev` group with Django and DRF at the versions the services lock. The core's
    independence is checked twice: Ruff `TID251` bans Django and DRF outside
    `drf.py`, and a subprocess test imports the core and asserts neither
    loaded.
11. **The DRF adapter.**
    - `get_verifier()` raises `NotImplementedError` rather than using
      `@abstractmethod`, which DRF's non-ABC base class wouldn't enforce.
    - `request.user` is a `Principal(subject)`.
    - The 401 challenge is `Bearer realm="api"`, without RFC 6750's
      `error="invalid_token"`, because DRF asks for the header without
      saying why authentication failed.
    - The 403 carries no `WWW-Authenticate`, because DRF adds it only to 401s.
    - Calling `require_scopes()` with no scopes raises `ValueError`.
12. **Auth service tests.** The RFC 8037 thumbprint test moved to the library,
    with the code. A new test checks that the seeded `Scope` names equal
    `scopes.ALL`, because a misspelled seed would mean a silent 403 for every
    editor.
13. **Main-app wiring.** The bearer class is the default authentication class.
    The listing keeps `authentication_classes([])`, so a junk token never
    breaks it. The verifier is built on first use and cached per process.
    Settings defaults match Compose, and Compose passes `JWT_ISSUER` and
    `JWT_AUDIENCE` to both services from the same variables.
14. **`PATCH` details.**
    - Only published brands can be edited: a draft is a 404, like its page.
    - Credentials are checked before the lookup, so an anonymous caller can't
      probe slugs.
    - A number is refused, not turned into a string.
    - A missing claims object fails closed with 403, not an `assert` that
      `python -O` would strip.
15. **Docker.** A repo-root build context was rejected: it would send `.env`
    to the builder. Each image gets a `shared-lib` named context and installs
    the library with `--no-editable`, so the runtime image has no library
    source. `shared-lib/.dockerignore` leaves out tests and caches.
16. **The version-bump check.** `scripts/check-shared-lib-version.sh` fails
    when `shared-lib/src` changed since the merge base and the version didn't.
    `make check-shared` runs it, plus `uv lock --check` in both services.
17. **First version.** 0.x was rejected: under SemVer it promises nothing, and
    this library is a contract. Chosen: 1.0.0.
18. **DRF range.** The `[drf]` extra allows `<4`. The services keep their own
    `<3.19` pin (ADR 0015), and each lockfile resolves inside it.

## Decision
- **Library:** `shared-lib/`, `brandreviews-authz` 1.0.0, with the modules
  in item 5. It depends on `PyJWT[crypto]` and `cryptography`, and on DRF
  only through the `[drf]` extra. It holds no signing code, no role-to-scope
  map, no models, and it reads no settings.
- **Auth service:** mints through `AccessClaims.to_payload()` and the profile
  constants, and publishes `public_jwk()`. Signing and key loading stay in
  `accounts/tokens.py`.
- **Main app:** `PATCH /api/brands/<slug>/`, guarded by
  `require_scopes(scopes.BRANDS_WRITE)`. It answers 401 with no usable token,
  403 without the scope, 503 when keys can't be fetched, 404 for an unknown
  or unpublished brand, and 400 for a bad body.
- **Install:** a uv path source in both services (editable locally,
  `--no-editable` in images), as ADR 0025 says.

## Consequences
- **The JWKS cache is per gunicorn worker.** During an auth outage, a worker
  that has verified a token in the last 5 minutes keeps accepting; a worker
  that hasn't since it started answers 503 at once. Seen live: the first
  `PATCH` after the auth service stopped got a 503, and twelve requests after
  warming both workers all passed.
- **Lost updates are possible.** Two editors saving at once: the second write
  wins, and the log shows both.
- **Known RFC 6750 deviations:** no `error=` parameter on the 401 challenge,
  and no challenge on the 403.
- **A library change is a release.** Bump the version, re-lock both
  services, and test both in the same change.
- **The user map is still not read** by the main-app import (ADR 0020). It
  comes in its own pull request.

## Revisit when
- More fields become editable, or more editors work at once (add `If-Match`
  and a detail endpoint).
- A second client needs RFC 6750's exact challenges (a custom DRF exception
  handler).
- More workers or protected endpoints make outage behavior matter (share
  the JWKS cache, or ADR 0016's option C).
- The services need different library versions at once (ADR 0025's
  hashed-wheel option).

## Sources
`docs/research/pillar-6-shared-library.md` §1–8 and "Open decisions";
ADRs 0015, 0016, 0020, 0025, 0026, 0027, 0033; PyJWT 2.15.1
`jwt/jwks_client.py` and `jwt/api_jwk.py` (read from the locked install);
[RFC 6750](https://www.rfc-editor.org/rfc/rfc6750) §3;
[RFC 9068](https://www.rfc-editor.org/rfc/rfc9068) §2, §4;
[RFC 8037](https://www.rfc-editor.org/rfc/rfc8037) Appendix A.
