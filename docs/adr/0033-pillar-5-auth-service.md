# 0033. Pillar 5: the auth service

- Status: Accepted
- Date: 2026-11-09

## Context
ADRs 0016 (token format, lifetime, revocation, outages), 0020 (reviewer
identity) and 0024 (imported passwords, scrypt) had already settled most of
Pillar 5. The research (`docs/research/pillar-5-auth-service.md`, "Open
decisions") left the rest open. Facts that shaped them:

- `wp_users` has 9 rows: 1 `administrator` and 8 `subscriber`s, who wrote
  every review. No login contains `@`, and every email is present and unique.
- The live WordPress adds `session_tokens` rows to `wp_usermeta` whenever
  someone logs into wp-admin. A MariaDB column grant can't hide rows.
- The protected `PATCH` needs the token verifier. AGENTS.md puts the verifier
  in the Pillar 6 shared library, which doesn't exist yet.
- Compose mounts a file secret as it is and ignores `uid`, `gid` and `mode`.
  A `0600` key owned by the host user can't be read by the container's user
  (uid 10001): gunicorn stopped at boot with "Permission denied" when tried.

The user chose items 1–8 on this date, taking the recommendation each time.
Items 9–18 are implementation defaults the agent took while building, flagged
for review in the Pillar 5 pull request.

## Options considered
1. **What this pull request covers.**
   - Auth service, a first verifier-only library and the `PATCH`, all at once.
     Rejected: one large diff spanning three projects.
   - The verifier inside the main app for now, moved later. Rejected: code
     written to be moved.
   - The auth service only. Chosen. The `PATCH` and the library come together
     in Pillar 6, since one can't exist without the other.
2. **Where roles and scopes live.**
   - Groups plus `auth.Permission`. Rejected: scopes become
     `app_label.codename`, need a placeholder model, and appear only after
     `post_migrate`.
   - Own `Role` and `Scope` models. Rejected: `Role` duplicates `Group`.
   - Groups as roles plus a small `Scope` model. Chosen.
3. **Brute-force protection.**
   - django-axes 9.0.0. Rejected: an app, a backend and a middleware, in a
     major release that cleared the cooldown on 2026-11-06. Lockout can deny
     real users.
   - Nothing beyond scrypt. Rejected: leaves the one unauthenticated write
     open to guessing.
   - DRF throttles per address and per account on a shared cache. Chosen.
4. **The Django admin.** On an internal port was rejected: it brings sessions,
   cookies, CSRF, static files and a second password login the throttles
   don't cover. None, with management commands, was chosen.
5. **Failed login response.** RFC 6749's `400 invalid_grant` was rejected: it
   dresses the endpoint as the OAuth password grant, which RFC 9700 forbids.
   `401 {"error": "invalid_credentials"}` for every cause was chosen.
6. **Login identifier.** Username only was rejected: WordPress users may know
   only their email. Username or email, case-insensitive, was chosen.
7. **`external_id` version.** UUIDv7 was rejected: it reveals when each
   account was created, and index locality doesn't matter here. UUIDv4 was
   chosen (RFC 9562 says v4 for security uses).
8. **Signing key delivery.** Generating it at startup was rejected: every
   restart would invalidate all tokens, and each worker would sign with its
   own key. A Compose file secret was chosen.
9. **What the import's MariaDB user can read.** Column grants on `wp_users`
   and `wp_usermeta` were rejected: `meta_value` would expose session tokens.
   A view of ID, login, email and the `wp_capabilities` value, with `SELECT`
   on that view only, was chosen.
10. **Making the key readable by uid 10001.** `chmod 0444` was rejected: any
    user on the host could read it. Host `openssl` plus `sudo chown` was
    rejected: the challenge promises "Docker, nothing else". Chosen:
    `keygen.py` runs in the auth image as root with no network, creates the
    file with `O_EXCL`, mode `0400` and owner 10001. `make up` creates it if
    missing and never overwrites it.
11. **Failing fast on a bad key.** A check in `AppConfig.ready()` was
    rejected: it would also stop management commands, and the import
    container has no key. `config/wsgi.py` loads the key, so only gunicorn
    refuses to boot. `/healthz` checks the key and the database.
12. **What a re-import changes.** Overwriting everything was rejected: after
    cutover, this service owns accounts (ADR 0024). Chosen: create missing
    users, follow a login or email changed in WordPress, and never touch a
    password, role or `is_active`.
13. **A user with no role.** Refusing the login was rejected: it mixes
    authentication with authorization. The login succeeds with `scope: ""`,
    which grants nothing.
14. **`WWW-Authenticate` on the 401.** HTTP says a 401 must carry it.
    Inventing a scheme for body credentials was rejected. The header is
    omitted, a known deviation.
15. **Malformed bodies.** DRF's default 400 field map, as in the main app
    (ADR 0027). The throttles still count them.
16. **Throttle rates.** 20 per minute per address and 5 per minute per
    account, both overridable by environment. The account key is a SHA-256 of
    the trimmed, case-folded username, so the cache never stores what people
    type. Counts live in a `DatabaseCache` table made by `createcachetable`.
17. **The clickjacking middleware.** Added: JSON can't be usefully framed,
    but the header costs nothing and clears a `check --deploy` warning.
18. **Reading the user map in the main app.** Deferred to the Pillar 6 pull
    request, with the other main-app changes. `make auth-map` writes
    `secrets/user-map.json` now.

## Decision
- **Project:** `auth-service/`, apps `accounts` and `wp_import`. Installed:
  `contenttypes`, `auth`, DRF and those two apps. No admin, sessions,
  messages, staticfiles, templates or whitenoise. Middleware: security,
  common, clickjacking.
- **User:** `AbstractUser` with `external_id` (UUIDv4, the token's `sub`) and
  a unique, nullable `wp_user_id`. Case-insensitive unique constraints on
  username and on non-empty email. Usernames can't contain `@`.
- **Roles:** Groups `reader` and `editor`. `Scope` rows `brands:read` and
  `brands:write` link to Groups and are seeded by a data migration. A token's
  scope is the sorted union of its user's Groups' scopes.
- **Endpoints:**
  - `POST /api/token/`: `{"username", "password"}` in. Out:
    `{"access_token", "token_type": "Bearer", "expires_in": 600, "scope"}`
    with `Cache-Control: no-store`. Every failure is
    `401 {"error": "invalid_credentials"}`.
  - `GET /.well-known/jwks.json`: one Ed25519 public key with `kid` (RFC 7638
    thumbprint), `use: sig` and `alg: EdDSA`, served as
    `application/jwk-set+json` with `max-age=300`.
  - `GET /healthz`: 200 when the database answers and the key loads, else 503.
- **Commands:** `import_wp_users [--dry-run]`, `grant_role`, `revoke_role`,
  `export_user_map`. Passwords are set with Django's `changepassword`.
- **Compose:** `auth-db` (its own Postgres), `auth-service` on port 8001, and
  the one-off `auth-import`, the only auth container with WordPress
  credentials and the only one without the key. The main app doesn't
  `depends_on` the auth service.
- **Key rotation runbook (today):** stop the auth service, delete
  `secrets/jwt_ed25519.pem`, `make auth-key`, start it again. Old tokens fail
  once the main app's cached JWKS expires (at most 5 minutes, ADR 0016), or
  sooner, when a token with the new `kid` makes it refetch. Graceful
  rotation, with the next key published before it signs (research §8), needs
  the JWKS to serve two keys. That isn't built.

## Consequences
- The auth service runs no HTML, form parsing, cookies or admin code.
- Brute-force protection is rate limiting plus scrypt, not lockout. One
  person's logins can be slowed for a minute by someone guessing at them.
- Rotating the key logs everyone out within the main app's JWKS cache.
- Pillar 5's protected endpoint isn't in this pull request. CHALLENGE.md's
  "call the protected endpoint" step arrives with Pillar 6.
- Tests use Django's MD5 hasher for speed. Production uses scrypt, as checked
  by hand against the running container.

## Revisit when
- Keys must rotate without logging people out (publish two keys).
- More than one proxy or a load balancer sits in front (`DJANGO_NUM_PROXIES`).
- Guessing shows up in the logs despite the throttles (django-axes or lockout).
- Roles need an audit trail beyond shell history (a log table, or the admin).

## Sources
`docs/research/pillar-5-auth-service.md` §2, §3, §5, §6, §8, §11 and "Open
decisions"; ADRs 0016, 0020, 0024, 0027;
[RFC 9700](https://www.rfc-editor.org/rfc/rfc9700) §2.4;
[RFC 9562](https://www.rfc-editor.org/rfc/rfc9562);
[Compose secrets](https://docs.docker.com/reference/compose-file/secrets/).
