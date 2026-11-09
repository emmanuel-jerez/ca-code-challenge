# 0016. EdDSA JWTs verified locally: lifetime, revocation and outages

- Status: Accepted
- Date: 2026-11-09
- Supersedes: [0003](0003-eddsa-jwt-verified-locally.md)

## Context
ADR 0003 chose asymmetric JWTs (Ed25519, `EdDSA`) issued by the auth service and
verified locally by the main app against a cached JWKS. The Pillar 5 and Pillar 6
research (`docs/research/pillar-5-auth-service.md`,
`docs/research/pillar-6-shared-library.md`) found four facts 0003 got wrong or left
vague. Each was checked against the RFC text and PyJWT 2.15.1's source on this date.

- **`EdDSA` is deprecated as an identifier.** RFC 9864 (October 2025) deprecates
  polymorphic JOSE identifiers such as `EdDSA` in favor of fully specified ones
  (`Ed25519`). PyJWT 2.15.1, the latest release, only knows `EdDSA`.
- **0003's `typ == "at+jwt"` is stricter than RFC 9068.** RFC 9068 §4 says verifiers
  accept `at+jwt` or `application/at+jwt`. RFC 7515 makes the media type
  case-insensitive.
- **We follow RFC 9068's profile but don't conform to it fully.** RFC 9068 §2.1 requires
  RS256 support. We accept only EdDSA.
- **"Keeps verifying until its cached JWKS expires" is 300 seconds.** That is
  `PyJWKClient`'s default `lifespan`. It doesn't serve stale keys after that, so with the
  auth service down every verification fails. PyJWT also skips `exp` and `nbf` when they
  are absent unless told to require them.

The research also left two answers to CHALLENGE question 7 (revocation, and what
happens when the auth service is down) that didn't fit together:
- **Pillar 5:** check token status online on the one protected write (`PATCH`) and
  fail closed.
- **Pillar 6:** a custom JWKS client that serves stale keys for up to 60 minutes.

The `PATCH` is the main app's only protected endpoint. If it always calls the auth
service, a stale-key cache never helps it. One coherent answer was needed, and the
simplest one that holds together was chosen.

## Options considered
- **A. Short lifetime only, local verification, fail closed when keys can't be
  fetched.** No call to the auth service per request, no stale cache, no status
  endpoint. Chosen.
- **B. Online status check on every `PATCH`, failing closed** (Pillar 5). Revocation and
  role changes take effect at once on writes. Rejected: it adds an auth endpoint, a
  runtime dependency on every write, and more code to test. CHALLENGE.md asks how
  revocation works; it doesn't require instant revocation.
- **C. A custom ~100-line JWKS client serving stale keys for up to 60 minutes**
  (Pillar 6). Rejected: it's security code we would own. It also keeps trusting keys the
  auth service may have removed, and buys little: no new tokens can be minted during an
  outage, so at most one token lifetime of editor writes is saved.
- **D. A `jti` denylist, or refresh tokens with rotation.** Rejected: more state and
  token types than "login plus roles" needs.
- **Per request:** opaque tokens with introspection on every request, and HS256 shared
  secrets. Both were rejected in 0003 for reasons that still hold.

## Decision
- **Libraries:** `PyJWT[crypto]>=2.15.1,<3` and `cryptography>=50.0.2`, unchanged. Never
  python-jose or simplejwt (reasons in 0003).
- **Algorithm:** Ed25519 keys only, under the identifier `EdDSA`. RFC 9864 allows a
  deprecated identifier where an implementation requires it, and PyJWT does. The
  verifier passes `algorithms=["EdDSA"]` and uses only OKP/Ed25519 *public* keys from
  the JWKS. Move to `Ed25519` by expand → migrate → contract once PyJWT supports it.
- **Header:** the auth service mints `typ: at+jwt`. The verifier accepts `at+jwt` or
  `application/at+jwt`, case-insensitively, and checks it with `decode_complete`,
  because PyJWT doesn't check `typ`.
- **Lifetime:** 10 minutes (`exp = iat + 600`), with at most 30 s of leeway.
- **Claims:** the verifier checks `iss`, `aud`, `exp` and `nbf`, and passes them in
  `options={"require": [...]}` so a token missing any of them fails. Authorization
  reads scope claims, not role names.
- **Verification is local only.** The main app never calls the auth service per
  request.
- **Key fetching:** the shared library wraps `PyJWKClient` with `lifespan=300`,
  `cache_keys=False`, `cooldown_duration=30` and `timeout=3`. It maps PyJWT and JSON
  errors to the library's own error types, and rejects any key that isn't an Ed25519
  public key. If no key can be fetched, the response is **503, not 401**, so clients
  don't discard a valid token.
- **Revocation and role changes** take effect within one token lifetime (≤ 10 minutes):
  - a deactivated user gets no new token;
  - a changed role appears in the next token's scopes;
  - to revoke every token at once, rotate the signing key and drop the old one from the
    JWKS, and the main app stops trusting it within the 5-minute cache.
- **When the auth service is down:**
  - public pages and `GET /api/brands/` don't involve it;
  - the `PATCH` keeps working while the cached keys are under 5 minutes old, then
    returns 503 until the auth service is back;
  - editors can't log in during the outage anyway.

## Consequences
- This replaces 0003's "per-user token version checked on the protected write". There
  is no token-version claim and no status endpoint.
- A 10-minute revocation window is accepted. Shortening the lifetime is the lever if it
  ever needs to shrink.
- **Known gap:** during an outage, `PyJWKClient` attempts a fetch for each token with an
  unknown `kid`, because it rate-limits only after successful fetches. The 3 s timeout
  and the single protected endpoint bound the cost.
- The profile is RFC 9068-style, not conformant. Adding RS256 would widen the algorithm
  list for no gain.

## Revisit when
- Instant revocation becomes a requirement (option B).
- More protected endpoints or editors make outage behavior matter (option C).
- PyJWT supports RFC 9864 identifiers.
- `draft-ietf-oauth-rfc8725bis` is published.
- A new PyJWT advisory lands.

## Sources
- [RFC 9864](https://www.rfc-editor.org/rfc/rfc9864) (October 2025); [RFC 9068](https://www.rfc-editor.org/rfc/rfc9068) §2.1, §4; [RFC 7515](https://www.rfc-editor.org/rfc/rfc7515) §4.1.9.
- PyJWT 2.15.1 source: [`jwks_client.py`](https://github.com/jpadilla/pyjwt/blob/2.15.1/jwt/jwks_client.py) (defaults), [`algorithms.py`](https://github.com/jpadilla/pyjwt/blob/2.15.1/jwt/algorithms.py) (identifiers).
- `docs/research/pillar-5-auth-service.md` §7–10 and "What the shared library must accept";
  `docs/research/pillar-6-shared-library.md` §2–3.
