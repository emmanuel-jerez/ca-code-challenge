# 0003. EdDSA JWTs, issued by the auth service and verified locally

- Status: Superseded by [0016](0016-token-lifetime-revocation-and-outages.md)
- Date: 2026-11-09

## Context
The auth service owns users, passwords and roles. The main app must protect one write
endpoint without storing credentials. CHALLENGE.md asks whether the main app verifies
tokens locally or calls the auth service on every request, and how revocation and role
changes work. PyJWT had a run of 2026 CVEs: algorithm confusion (CVE-2026-48526) and an
allow-list bypass (CVE-2026-48523) fixed in 2.13, and 14 more advisories (one critical
key-confusion bypass) fixed in 2.14.0/2.15.0.

## Options considered
- **Opaque tokens + introspection on every request.** Instant revocation. Rejected:
  the auth service becomes a single point of failure and adds latency to every call.
- **HS256 shared secret.** Simplest. Rejected: every verifier could also mint tokens.
- **Asymmetric JWT verified locally against a cached JWKS.** Chosen.
- Libraries: **PyJWT** chosen. **djangorestframework-simplejwt** rejected (built for
  one service that issues and verifies; no Python 3.14 declared). **python-jose**
  rejected (released 3.4/3.5 in 2025 after a long gap; weak security record; FastAPI
  dropped it). joserfc/authlib not needed.

## Decision
- `PyJWT[crypto]>=2.15.1,<3`, `cryptography>=50.0.2`.
- Ed25519 (`EdDSA`) signatures; header `typ: at+jwt` (RFC 9068); lifetime ≤ 15 minutes.
- The auth service alone holds the private key and publishes a JWKS.
- The main app (via the shared library) decodes with `algorithms=["EdDSA"]` only and
  checks `iss`, `aud`, `exp`, `nbf`. PyJWT does not check `typ` on decode, so the
  library uses `decode_complete` and checks `typ == "at+jwt"` itself.
- Authorization reads scope claims, not role names.

## Consequences
- The main app keeps verifying while the auth service is down, until its cached JWKS
  expires; new logins fail.
- Revocation and role changes lag up to the token lifetime. Mitigation: short TTL,
  plus a per-user token version checked on the protected write.

## Revisit when
Instant revocation becomes a requirement, a new PyJWT advisory lands, or another
client needs a different token profile.

## Sources
`docs/research/stack-decisions.md` §2b; `docs/research/stack-validation.md` §1;
`docs/research/best-practices-2026.md` §8.
