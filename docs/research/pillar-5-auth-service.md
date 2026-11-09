# Pillar 5: the auth service

Researched 2026-11-09. Targets Django 5.2 LTS on Python 3.14, under the 7-day dependency cooldown (ADR 0012).

Scope: the separate Django project that owns users, passwords and roles, and mints the access token. It covers the user model, the import of `wp_users`, password hashing, roles and scopes, the login endpoint, token minting, the JWKS endpoint, revocation, behaviour when the service is down, and the container and settings. The shared library (Pillar 6) is covered elsewhere. This note only says what that library must accept. Accepted decisions (ADR 0003: EdDSA JWT, ≤ 15 min, `typ: at+jwt`, JWKS, local verification, scope-based authorization, PyJWT) are not reopened. Evidence that bears on them is under "Conflicts with accepted decisions".

> Confidence notes. Facts come from primary sources: RFCs and IETF drafts, Django, PyJWT, WordPress and pyca source at a pinned tag, official docs, the PyPI JSON API, and the GitHub Advisory Database. Items marked *(tested)* were run on 2026-11-09 in a throwaway Python 3.14.10 environment outside the repo, with uv `--exclude-newer 2026-11-02` [51]. Timings come from one aarch64 machine. Treat them as ratios, not absolutes. Context7 answered the Django 5.2 and DRF 3.18.3 doc questions. Everything else came from source files and RFC texts fetched directly.

---

## Key findings

1. **The WordPress data is simpler than the existing notes assume.** There are 9 users. All 9 hashes are WordPress 6.8+ bcrypt (`$wp$2y$10$`); there is no phpass `$P$` hash. One user has the `administrator` role and 8 have `subscriber`. The 8 subscribers wrote all 60 reviews [2]. A WordPress hash verifier needs no phpass code. Its HMAC key is the literal string `wp-sha384`, so it needs no WordPress secret either [21].
2. **`EdDSA` is now a deprecated algorithm name.** RFC 9864 (October 2025) marks the polymorphic `EdDSA` JOSE identifier "Deprecated" in favour of `Ed25519` [43]. The JWT best-practice revision (draft -10, approved and in the RFC Editor queue) says new deployments SHOULD prefer `Ed25519` [45]. PyJWT 2.15.1 rejects `algorithm="Ed25519"` with `NotImplementedError` *(tested)*; support is an open issue and pull request [31]. So keep `EdDSA` for now, pin the key curve to Ed25519 in the verifier, and plan an expand → contract switch.
3. **"RFC 9068" needs care.** RFC 9068 says conforming servers MUST support RS256, and verifiers MUST accept `typ` values of both `at+jwt` and `application/at+jwt` [33]. RFC 7515 says media types are case-insensitive [42]. An EdDSA-only, exact-match setup is an RFC 9068-*style* profile, not a conformant one. Say so on the call.
4. **PyJWT only checks the claims you ask for.** It checks `exp`, `nbf` and `iat` only when they are present. `issuer=None` skips the issuer check entirely. If you omit `algorithm`, `encode` signs with HS256 *(tested)* [29]. The verifier must pass `options={"require": [...]}`, `issuer`, `audience` and `strict_aud=True`. The issuer must always pass `algorithm="EdDSA"`.
5. **PyJWT's JWKS client never serves a stale key set.** Once the cache's `lifespan` (default 300 s) runs out, a failed fetch raises `PyJWKClientConnectionError`. The client also holds a lock during the fetch, and the default timeout is 30 s [29]. With these defaults, "keeps verifying while auth is down" lasts about 5 minutes. Any longer tolerance must be built into the shared library.
6. **Strong password hashing needs no new dependency.** Django 5.2's PBKDF2 uses 1,000,000 iterations, above OWASP's 600,000 [3][25]. Django's built-in scrypt hasher (N=2^14, r=8, p=5) matches one of OWASP's listed scrypt configurations and is memory-hard [3][25]. Argon2id, OWASP's first choice, adds four packages (argon2-cffi, argon2-cffi-bindings, cffi, pycparser) *(tested)*.
7. **A legacy WordPress hasher leaks timing.** `ModelBackend` runs the default hasher for unknown usernames [4]. But Django's own comment says it does not hide timing when a stored hash uses a different hasher [3]. Measured: a WP bcrypt cost-10 check took 41 ms and PBKDF2 took 72 ms *(tested)*. The February 2026 Django timing CVE (CVE-2025-13473) affected only the mod_wsgi auth handler, not `ModelBackend` [16].
8. **DRF throttling is weak by default.** DRF says its throttling "should not be considered a security measure or protection against brute forcing" [48]. Django's default cache is per process, so each gunicorn worker counts separately [10]. With `NUM_PROXIES` unset, DRF trusts a client-supplied `X-Forwarded-For` verbatim, so an attacker can rotate it to dodge per-IP limits [48]. Set `NUM_PROXIES = 0` and use a shared cache.
9. **The OAuth password grant is banned.** RFC 9700 (January 2025) says the resource owner password credentials grant "MUST NOT be used" [37]. Borrow RFC 6749's response field names (`access_token`, `token_type`, `expires_in`), but don't present the endpoint as an OAuth `grant_type=password`.
10. **An API-only service can drop a lot.** It doesn't need the admin, sessions, messages, the CSRF middleware, staticfiles or whitenoise. In 2026, three admin CVEs affected 5.2, plus a model-formset CVE that admin inlines rely on. Session and cache CVEs only matter if those features are on [15].
11. **Compose file secrets ignore `uid`, `gid` and `mode`.** A file-based secret is a bind mount, and those attributes are "silently ignored" [50]. The key file's host permissions must already suit the container's non-root UID.
12. **`uuid.uuid7()` exists and works, but use v4 for `sub`.** Python 3.14 added `uuid.uuid7()` [19], and Django's migration writer serializes `default=uuid.uuid7` *(tested)*. RFC 9562 says UUIDv4 SHOULD be used when a UUID serves "any security operation" [20], and v7 exposes the account's creation time. `sub` is an authorization identity.

---

## 1. What the data and requirements look like

| Fact | Value | Source |
|---|---|---|
| WordPress version | 6.9 (`wordpress:6.9-php8.3-apache`) | `docker-compose.yml` |
| `wp_users` rows | 9 (IDs 1–9). All emails present and unique. Logins unique even ignoring case; none contains `@`. `user_status` = 0 and no activation keys. | [2] |
| Hash formats | 9 × `$wp$2y$10$…` (63 chars: `$wp` + a 60-char bcrypt string, cost 10). 0 × phpass `$P$`, 0 × MD5, 0 × other | [2] |
| Roles (`wp_capabilities`) | 1 × `administrator` (`wp_user_level` 10). 8 × `subscriber` (level 0) | [2] |
| Who wrote reviews | The 8 subscribers wrote all 60 reviews (5–10 each). The administrator wrote 1 post and 2 pages | [2] |
| Out of scope | Registration, password reset, MFA, a login UI | [1] |

The administrator's WordPress password is the trivial demo value published in CHALLENGE.md's setup section [1]. That matters for option (b) in §3.

**Defend it:** "I checked the dump first. All nine hashes are WordPress 6.8 bcrypt, with no phpass. There's one admin and eight subscribers, who are the reviewers. So the migration problem is smaller than a generic WP migration."

---

## 2. User model

### Options

| Option | Security cost | Stability cost | Effort | Why it might lose |
|---|---|---|---|---|
| **`AbstractUser` subclass** (username, email, names, `is_active`, `is_staff`, groups and permissions) | None beyond Django | The most-used path. Works with `createsuperuser`, `changepassword` and `ModelBackend` unchanged | Lowest | Carries fields you may not use (`first_name`, `is_staff`) |
| `AbstractBaseUser` + `PermissionsMixin` | None | You write and own a custom manager (`create_user`, `create_superuser`) | Medium | More hand-written code for no gain here |
| Default `auth.User` | None | Django warns that changing `AUTH_USER_MODEL` later "can't be done automatically" [8][12] | Lowest now, high later | Can't add `external_id` cleanly |

Django 5.2's docs show the starting-project pattern as `class User(AbstractUser): pass`, set before the first migration [8]. Inherit from the abstract class, not a concrete parent. CVE-2026-113733 (password hash shown to view-only admins) applied when `AUTH_USER_MODEL` inherited `password` through multi-table inheritance. It was fixed only in 6.0 and 6.1; 5.2.19 doesn't list it [17][18].

### Fields to add

- **`external_id`**: `UUIDField(default=uuid.uuid4, unique=True, editable=False)`. This is the token's `sub` and the only user reference the main app stores. Keep the `BigAutoField` primary key internal (`DEFAULT_AUTO_FIELD` explicit, per the django-lts skill) and never expose it.
- **`wp_user_id`**: `PositiveBigIntegerField(null=True, unique=True)`. The re-import upsert key. It's null for users created later.
- **Case-insensitive uniqueness:** `UniqueConstraint(Lower("username"), …)` and `UniqueConstraint(Lower("email"), condition=~Q(email=""), …)`. Functional and conditional constraints are supported in 5.2 [13], and Postgres enforces them (ADR 0006). This mirrors WordPress, whose `utf8mb4_unicode_520_ci` collation already makes logins case-insensitive [2].
- **If you adopt the revocation check in §9:** `tokens_valid_after = DateTimeField(null=True)`.

### UUID version

| | Exists on 3.14 + Django 5.2? | Leaks | Fit |
|---|---|---|---|
| **`uuid.uuid4`** | Yes | Nothing | ✅ RFC 9562: "If UUIDs are required for use with any security operation … UUIDv4 SHOULD be utilized" [20] |
| `uuid.uuid7` | Yes: "Added in version 3.14", takes no arguments [19]. `MigrationWriter.serialize(uuid.uuid7)` → `uuid.uuid7` *(tested)* | Creation time (48-bit ms timestamp) and creation order [20] | ⚠️ Index locality doesn't matter at 9 users, and the primary key stays a bigint |
| `uuid.uuid5(ns, wp_id)` | Yes | Anyone who knows the namespace can map public WP user IDs to external IDs | ⚠️ Only useful for the cross-service mapping (§3, open decision 4) |

### Login by username or email

WordPress 6.9 accepts both: `wp_authenticate_username_password` and `wp_authenticate_email_password` are both hooked to `authenticate` [22]. To keep parity, write a small `ModelBackend` subclass:
- If the identifier contains `@`, look up `email__iexact`; otherwise look up `username__iexact`. Then forbid `@` in usernames, so the two can never collide.
- On `DoesNotExist` or `MultipleObjectsReturned`, call `User().set_password(password)` before returning `None`. That keeps the timing equaliser Django's own backend uses [4].
- Keep `user_can_authenticate()`, so inactive users fail after the hash check [4].

**Recommendation:** subclass `AbstractUser`. Add `external_id` (UUIDv4), `wp_user_id` and the two functional unique constraints. Allow login by username or email through one small backend.

**Defend it:** "The main app only ever sees a random UUID. Integer IDs and usernames stay inside the auth service. I used v4, not v7, because RFC 9562 says v4 for anything security-related, and v7 would leak when each account was created."

---

## 3. Migrating `wp_users` and their passwords

### How WordPress 6.9 hashes and checks

From `wp-includes/pluggable.php` at the 6.9 tag [21]:
- **Hash:** `'$wp' . password_hash(base64_encode(hash_hmac('sha384', trim($password), 'wp-sha384', true)), PASSWORD_BCRYPT)`.
- **Check:** if the hash starts with `$wp`, run `password_verify(base64_encode(hash_hmac('sha384', $password, 'wp-sha384', true)), substr($hash, 3))`. Note there is **no `trim()`** on check. Passwords over 4096 characters are rejected. `$P$` hashes go to phpass, and hashes of 32 chars or fewer go to MD5.
- The make.wordpress.org announcement (2025-02-17) confirms bcrypt with SHA-384 pre-hashing, "to avoid the 72 byte length limit". It says phpass hashes are rehashed on the next login, and application passwords use BLAKE2b with a `$generic$` prefix [23]. The dump has no `$generic$` values.

The pre-hash is 64 base64 characters, under bcrypt's 72-byte limit. pyca/bcrypt 5.0.0 raises `ValueError` above 72 bytes [24], so this never triggers.

### Options

| | (a) Import with unusable passwords; set chosen ones with `changepassword` | (b) Verify-only WordPress hasher; upgrade on first login | (c) Random one-time passwords, printed once |
|---|---|---|---|
| How | `set_unusable_password()` for every import. For demo accounts, run the built-in `manage.py changepassword <user>`, which prompts and applies validators | A `BasePasswordHasher` subclass with `algorithm = "wp_bcrypt"`. Store `wp_bcrypt$` + the original string. `verify()` recomputes the HMAC pre-hash and calls `bcrypt.checkpw` on `hash[3:]`. Django's `check_password` setter re-hashes with the default hasher on success [3] | `secrets.token_urlsafe()`, then `set_password()`, then print once |
| New dependency | None | **`bcrypt` 5.0.0** (pyca, 2025-09-25, cp314 wheels, no GHSA advisories ever) [24][27][28] | None |
| Security cost | None. The auth DB never holds WordPress hashes, and the import never needs to read `user_pass` | Keeps cost-10 bcrypt hashes alive until each user logs in. Migrates weak passwords as they are (including the admin's published demo password [1]), because validators don't run at login. Leaks timing (41 ms vs 72 ms) that marks un-migrated accounts *(tested)* | Secrets land in terminal scrollback and CI logs. Re-running the import must not regenerate them |
| Stability cost | None | About 25 lines of crypto-adjacent code to test and later delete. bcrypt 5.0 already changed long-password behaviour once [24] | Low |
| Users keep their passwords? | No | Yes | No |
| Effort | Lowest | Medium | Low |

Detail for (b): `identify_hasher()` takes the text before the first `$` as the algorithm name. A raw `$wp$2y$…` value raises "Unknown password hashing algorithm ''" *(tested)* [3]. So the import must store `wp_bcrypt$$wp$2y$…`, which is 73 characters, under the 128-character field limit [3]. With that prefix the round trip works: correct password → `True`, the setter fires, and the password is re-stored as `pbkdf2_sha256$1000000$…`; a wrong password → `False` *(tested)*.

**phpass:** none in the data. A hand-written phpass verifier means maintaining iterated MD5 code for zero users. If a `$P$` value ever shows up, treat it as (a).

### Import mechanics (any option)

- **Source:** query MariaDB with PyMySQL, as ADR 0007 already does for the main app. The REST API can't provide hashes or roles without authentication.
- **Least privilege:** give the auth import its own read-only MariaDB user with `SELECT` on `wp_users` and `wp_usermeta` only. Leave `user_pass` out of the column grant unless you choose (b). The main app's import user then never sees `user_pass` at all.
- **Re-runs:** upsert on `wp_user_id`. After cutover the auth service is the source of truth, so a re-run should fill gaps, not overwrite. Never reset a password a user has already changed or upgraded. Never overwrite roles changed in the auth service. Put any destructive sync behind an explicit flag.
- **Roles from `wp_capabilities`:** the value is a PHP-serialized array (`a:1:{s:N:"role";b:1;}`). Parse it with a strict regex that also checks each declared length `N`. Don't add a PHP-unserialize package for one key. Read the meta key from the table prefix (`WORDPRESS_TABLE_PREFIX`), not a hard-coded `wp_`.

### Role mapping

| WP role | Count | New role | Note |
|---|---|---|---|
| `administrator` | 1 | `editor` | Not `is_superuser`. If you keep the admin, create a superuser separately with `createsuperuser` |
| `subscriber` | 8 | `reader` | These are the reviewers |
| anything else | 0 | none, plus a warning | Fail safe. The existing note's "author → reader" row has no data behind it |

**Recommendation:** (a). Import every account with an unusable password and set passwords for the demo accounts with `changepassword`. Keep (b) as the documented upgrade path if real users must keep their passwords. Because only `$wp$2y$` is present, (b) would need no phpass code. Its costs are the `bcrypt` dependency, the timing signal, weak migrated passwords, and a removal date.

**Defend it:** "The challenge allows resets, and resetting means no WordPress hashes reach the new database. It also means no legacy crypto code and no `bcrypt` dependency, and the admin's demo password isn't carried over. If users had to keep their passwords, I'd add a 25-line verify-only hasher. The data shows it only needs bcrypt, not phpass, and Django re-hashes on first login."

---

## 4. Password hashing (for new passwords)

| | Django 5.2 defaults | OWASP minimum | New deps | Measured verify *(tested)* | Notes |
|---|---|---|---|---|---|
| **PBKDF2-SHA256** (Django's default) | 1,000,000 iterations [3] | 600,000 ("if FIPS-140 compliance is required") [25] | None | 72 ms | Django raises the count every feature release, and `must_update` re-hashes on login. Not memory-hard |
| **scrypt** (`ScryptPasswordHasher`) | N=2^14, r=8, p=5, `maxmem=0` [3] | N=2^17, r=8, p=1, *or the equivalent* N=2^14, r=8, p=5 (16 MiB) [25] | None (stdlib `hashlib.scrypt`, needs OpenSSL 1.1+) [7] | 96 ms | Memory-hard. OWASP's second choice. Memory = `work_factor × 2 × block_size × 64` = 16 MiB, so raising N needs a higher `maxmem` [7] |
| **Argon2id** (`Argon2PasswordHasher`) | t=2, m=102,400 KiB (100 MiB), p=8 [3] | m=19 MiB, t=2, p=1 [25] | 4: argon2-cffi 25.1.0 (2025-06-03), argon2-cffi-bindings 26.1.0 (2026-08-20, cp314 wheels), cffi, pycparser. No GHSA advisories [27][28] | 14 ms (8 threads) | OWASP's first choice. 100 MiB per concurrent login is a memory-exhaustion lever on an unauthenticated endpoint |
| bcrypt (`BCryptSHA256PasswordHasher`) | 12 rounds | cost ≥ 10, "legacy systems" [25] | `bcrypt` | — | OWASP lists it for legacy systems only |

**Recommendation:** put `ScryptPasswordHasher` first and `PBKDF2PasswordHasher` second in `PASSWORD_HASHERS`. That gives a memory-hard algorithm, OWASP's second choice, with no new dependency. Hashes made before the switch (for example by an early `createsuperuser`) still verify and upgrade. Fallback: keep Django's PBKDF2 default, the most-travelled path. Argon2 doesn't earn four packages at 9 users.

**Defend it:** "OWASP ranks Argon2id, then scrypt. Django ships scrypt using only the standard library, and its defaults match an OWASP configuration. So I get memory-hardness without a native dependency in the service that holds the passwords."

---

## 5. Roles and scopes

### What the token needs

- RFC 8693 §4.2 defines `scope` as one JSON string of space-separated values [34], with RFC 6749's syntax: case-sensitive tokens of `%x21 / %x23-5B / %x5D-7E`. So `:` is allowed; space, `"` and `\` are not [35].
- RFC 9068 §2.2.3: every scope "MUST have meaning for the resources indicated in the `aud` claim" [33].
- RFC 9068 §2.2.3.1 offers SCIM `roles`, `groups` and `entitlements` claims for non-delegated authorization [33]. Leave them out. Putting role names in the token invites the main app to check them, which AGENTS.md forbids.

### Role store options

| Option | Security cost | Stability cost | Effort | Why it might lose |
|---|---|---|---|---|
| Groups + `auth.Permission` as scopes | None | Built in. But every Permission needs a content type, so scopes must hang off a placeholder model. Default permissions are created by `post_migrate` at the *end* of `migrate`, so a data migration on a fresh DB must create them itself [9][14] | Medium | Scope strings become `app_label.codename`, which is awkward |
| **Groups as roles + a small `Scope` model** (unique `name` with a validator for `resource:action`, M2M to `Group`) | None | `user.groups` is built in. Your one model holds the exact token strings | Low | One extra model |
| Own `Role` + `Scope` + `User.roles` | None | Duplicates `Group`, whose tables exist anyway | Medium | Two concepts for one thing |

**Seeding:** a `RunPython` data migration using historical models (`apps.get_model`). It creates groups `reader` and `editor`, scopes `brands:read` and `brands:write`, and links `reader → brands:read`, `editor → brands:read brands:write`. Give it a reverse function. Nothing then depends on `post_migrate` timing.

**Naming:** `resource:action`, lowercase, plural resource, no wildcards: `brands:read`, `brands:write`. `brands:read` guards nothing today, because `GET /api/brands/` is public. It gives `reader` a meaningful token and a place to grow. Saying so beats inventing a use.

**Mapping into the token:** one query, `Scope.objects.filter(groups__user=user).values_list("name", flat=True).distinct()`, sorted and joined with spaces.

**Recommendation:** Groups as roles plus a small `Scope` model, seeded by a data migration.

**Defend it:** "Roles live only in the auth service. The token carries scopes, and the main app checks `brands:write`. If editors are later split into two roles, only the auth service's data changes, not the main app's code."

---

## 6. Login endpoint

### Shape

- **Request:** `POST /api/token/` with JSON `{"username": "...", "password": "..."}`. `username` also accepts an email address. Cap `password` at 4096 characters to mirror WordPress [21]. OWASP asks for at least 64 [26].
- **Success, 200:** `{"access_token": "...", "token_type": "Bearer", "expires_in": 600, "scope": "brands:read brands:write"}`, with `Cache-Control: no-store`. RFC 6749 §5.1 requires `no-store` on any response containing tokens [35].
- **Failure:** one status and one body for every cause: unknown user, wrong password, inactive user, unusable password. OWASP: respond "in a generic manner", for example "Invalid user ID or password", with equal processing time [26]. Use 401 with `{"error": "invalid_credentials"}`, or RFC 6749 §5.2's `400 invalid_grant`. Pick one and keep it identical for every cause.
- **Don't** accept `grant_type=password` or call this OAuth. RFC 9700 §2.4: "The resource owner password credentials grant … MUST NOT be used", because it exposes credentials to the client [37]. Here the only client is our own curl or CLI, and the challenge scopes out a login UI [1]. That's the line to defend.

### Timing and enumeration

- `ModelBackend.authenticate` calls `UserModel().set_password(password)` when the user doesn't exist, "to reduce the timing difference" [4].
- `verify_password` runs a fake hash for unusable passwords [3]. So option (a)'s imported users fail in about the same time as unknown users: 68 ms vs 72 ms *(tested)*.
- Django does *not* equalise timing when the stored hash uses another hasher. Its comment reads "we don't protect against enumeration if it does" [3]. That's the cost of option (b).
- WordPress already exposes authors publicly. For callers without `list_users`, WP 6.9's REST `/users` route returns every user with published posts in a REST-visible post type, including their `slug` (`user_nicename`, usually derived from the login) [52]. The reviewers are exactly those users, so enumeration matters less for this dataset than in general.

### Throttling

| | Security | Stability | New deps | Notes |
|---|---|---|---|---|
| **DRF `ScopedRateThrottle`** (per IP) plus a small `SimpleRateThrottle` subclass keyed on the normalised username | Per-username limits stop distributed guessing on one account, which OWASP prefers over per-IP limits [26]. They also let an attacker slow a victim's login, a soft lockout. DRF itself says throttling isn't a brute-force control [48] | Part of DRF (ADR 0002) | None | **Needs a shared cache**: the default `LocMemCache` is per process [10]. Use Django's `DatabaseCache` on the service's own Postgres. Run `createcachetable` in the entrypoint; it isn't a migration [10]. **Set `NUM_PROXIES = 0`**: with the default `None`, DRF trusts a client-sent `X-Forwarded-For` as-is [48] |
| django-axes 9.0.0 | Per-user and per-IP lockout with a database audit trail | Moved from Jazzband to Django Commons and now uses trusted publishing (good). But 9.0.0 is a major release from 2026-10-30 that cleared the cooldown only on 2026-11-06. It has 167 releases in total, and its changelog lists an 8.3.2 that isn't on PyPI [49][27]. No GHSA advisories [28] | 1 app (with migrations), plus a backend and a middleware | Needs `request=` passed to `authenticate()`. Lockout can deny service to real users [26] |

### Logging

- Log outcomes, not inputs. On success, log `external_id`, IP and `jti`. On failure, log IP and a hash of the normalised username; people sometimes type passwords into the username box.
- Never log the request body, the `Authorization` header, or the token.
- Django's `user_login_failed` signal masks credential keys matching `api|token|key|secret|password|signature` [5].
- Error reports mask `request.META` and settings keys matching `API|AUTH|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE`, which covers `HTTP_AUTHORIZATION` [6].
- Add `@sensitive_variables("password")` on the view so the value is masked in tracebacks.

**Recommendation:** a DRF view at `POST /api/token/` with RFC 6749-style field names, a generic failure response, per-IP and per-username throttles on `DatabaseCache`, and `NUM_PROXIES = 0`. No django-axes.

**Defend it:** "It's a first-party credential exchange, not the banned OAuth password grant. Every failure looks the same and takes about the same time. The rate limits use a shared cache and ignore spoofed `X-Forwarded-For`, because DRF's defaults get both wrong."

---

## 7. Token minting

### Versions and advisories

- **PyJWT 2.15.1** (2026-09-28) is the latest release. Its classifiers cover 3.10–3.15 [27].
- The GitHub Advisory Database lists 20 PyJWT advisories published in 2026 [28]:
  - CVE-2026-32597 (unknown `crit` headers accepted), fixed in 2.12.0.
  - Five fixed in 2.13.0: CVE-2026-48522, -48523, -48524, -48525 and -48526 (the HMAC/JWK confusion).
  - Twelve fixed in 2.14.0, including the critical CVE-2026-102268 (PEM whitespace bypass), CVE-2026-102267 (redirects) and CVE-2026-103001 (options-dict mutation).
  - Two fixed in 2.15.0: CVE-2026-101918 and -102275 (inconsistent OKP x/d).
- OSV returns no vulnerabilities for 2.15.1 [28]. This corrects nothing in ADR 0003; it confirms its floor.
- **CVE-2026-102269**, "non-canonical signature segments enable raw-token revocation bypass" (fixed in 2.14.0) [28], is a design lesson: any denylist must key on `jti`, never on the raw token string.
- **cryptography 50.0.2** (2026-09-30) has cp314 and abi3 wheels [27]. Its 2026 advisories cover PKCS#7, X.509 path building, SECT curves and the bundled OpenSSL. None touches Ed25519 signing [28].

### Keys

- **Generate** outside the image: `openssl genpkey -algorithm ed25519 -out secrets/jwt_ed25519.pem` under `umask 077`. This produces a PKCS#8 `BEGIN PRIVATE KEY` PEM that `load_pem_private_key` loads as `Ed25519PrivateKey` *(tested)* [32]. `Ed25519PrivateKey.generate()` plus `private_bytes(PEM, PKCS8, NoEncryption())` is the pure-Python equivalent [32].
- **Load** once at startup from the path in `JWT_SIGNING_KEY_FILE` (for example `/run/secrets/jwt_signing_key`). Narrow the result with an `isinstance(key, Ed25519PrivateKey)` guard and fail fast otherwise. Never log it, never bake it into the image, never commit it.
- **gitignore:** this repo's `.gitignore` has no `secrets/` entry today. Add one before generating keys.
- **Compose:** a file-based secret is a read-only bind mount at `/run/secrets/<name>`, and `uid`, `gid` and `mode` are "silently ignored" for file sources [50]. Make the host file readable by the container's UID (for example `chown 10001` with mode `0400`). Don't loosen it to `0444`. Avoid passing the key through an environment variable: env values show up in `docker inspect` and the process environment.

### `kid`

Use the RFC 7638 thumbprint [41]. For OKP keys, hash exactly `crv`, `kty` and `x`, in that order [40]: `base64url(SHA-256('{"crv":"Ed25519","kty":"OKP","x":"…"}'))`, without padding. That's stdlib `json` (sorted keys, no spaces), `hashlib` and `base64`; PyJWT has no thumbprint helper. RFC 8037 Appendix A.3 provides a test vector, `kPrK_qmxVWaYVA9wwBF6Iuo3vVzz7TxHCTwXBygrS4k`, which this recipe reproduces *(tested)* [40]. Make it a unit test. A thumbprint `kid` is always 43 characters of `[A-Za-z0-9_-]`, which gives the verifier a cheap format check (rfc8725bis §3.10 says to validate `kid`) [45].

### Claims

| Claim | Value | Why |
|---|---|---|
| `iss` | `JWT_ISSUER` (e.g. `http://auth:8000` in compose; an https URL in production) | RFC 9068 REQUIRED. The verifier needs an exact match [33] |
| `aud` | `"brands-api"`, a single string | RFC 9068 REQUIRED. RFC 9068 §5: use a distinct `aud` per resource [33]. One string allows `strict_aud=True` [29] |
| `sub` | `str(user.external_id)` | RFC 9068 REQUIRED [33] |
| `client_id` | A fixed configured value, e.g. `"brands-cli"` | RFC 9068 REQUIRED (RFC 8693 §4.3) [33][34]. There's no client registry, so a constant is honest |
| `iat`, `nbf` | Now (integer seconds) | `iat` is RFC 9068 REQUIRED. PyJWT rejects a future `iat` or `nbf` beyond the leeway [29] |
| `exp` | `iat + 600` | ≤ 15 min (ADR 0003) |
| `jti` | `secrets.token_urlsafe(16)` or `uuid4()` | RFC 9068 REQUIRED. Also the denylist key, if one is ever needed |
| `scope` | e.g. `"brands:read brands:write"` | RFC 8693 §4.2 format [34] |
| *(none)* | No email, username, display name or roles | RFC 9068 §6: claims are readable by the client. Send the minimum [33] |

Header: `{"alg": "EdDSA", "typ": "at+jwt", "kid": "<thumbprint>"}`. PyJWT starts from `{"typ": "JWT", "alg": …}` and then `header.update(headers)`, so passing `headers={"typ": "at+jwt", "kid": kid}` overrides `typ` [29]. Always pass `algorithm="EdDSA"` explicitly: when `algorithm` is omitted, PyJWT defaults to HS256, and `algorithm=None` means `none` [29] *(tested)*.

```python
jwt.encode(claims, private_key, algorithm="EdDSA", headers={"typ": "at+jwt", "kid": kid})
```

### Algorithm identifier

| | Status | PyJWT 2.15.1 | Verdict |
|---|---|---|---|
| **`EdDSA`** | "Deprecated" by RFC 9864: SHOULD be replaced in new deployments "unless there exist documented operational or regulatory requirements that prevent migration" [43] | Supported. A JWK with `crv: Ed25519` maps to `EdDSA` [29] | ✅ Use now. The documented requirement is library support |
| `Ed25519` | Preferred by RFC 9864 and rfc8725bis-10 §3.2 [43][45] | `NotImplementedError` *(tested)*. Issue #1190 and PR #1199 are open [31] | Switch when PyJWT ships it |
| Register a custom `Ed25519` via `jwt.register_algorithm` [29] | — | Possible | ❌ Hand-wired crypto plumbing in both services to win a naming argument |

**Recommendation:** EdDSA (Ed25519 keys only), the claims above, a 600 s lifetime, and a thumbprint `kid`. Record the RFC 9864 deviation and its trigger: a PyJWT release with `Ed25519`. Then migrate expand → contract: first the verifier accepts both names, then the issuer switches, then `EdDSA` is dropped.

**Defend it:** "Only the auth service holds the private key; it comes from a mounted secret, never the image. The token carries the RFC 9068 claim set and nothing personal. We still use the `EdDSA` name, which RFC 9864 deprecated, because PyJWT doesn't support `Ed25519` yet. Moving to it is a textbook expand-migrate-contract change for the shared library."

---

## 8. JWKS endpoint

- **Format:** RFC 7517 §5, a JSON object with a `keys` array. Unknown members MUST be ignored [39]. Each key: `{"kty": "OKP", "crv": "Ed25519", "x": "…", "kid": "…", "use": "sig", "alg": "EdDSA"}`. Never include `d` [40].
- **Why include `alg`:** rfc8725bis-10 §3.1 says "each key MUST be used with exactly one algorithm" and that the library must check `alg` against the key [45].
- **Media type:** `application/jwk-set+json` (registered by RFC 7517) [39]. PyJWT parses the body as JSON whatever the content type [29].
- **Path:** `/.well-known/jwks.json` is a convention, not an IANA-registered URI. The registry has `oauth-authorization-server` (RFC 8414) and `openid-configuration`, but no `jwks` entry [47]. Either serve the convention and configure the URL in the main app, or also publish RFC 8414 metadata with `issuer` and `jwks_uri`, which RFC 9068 §4 recommends [33]. For one consumer, the configured URL is enough.
- **Caching:** `Cache-Control: public, max-age=300`, matching PyJWKClient's default `lifespan` of 300 s [29]. PyJWKClient uses `urllib` with no HTTP cache, so the header matters only if a proxy or CDN sits in between.

### Rotation

OIDC Core §10.1.1 describes the standard process [46]. The signer adds new keys to the set, switches by changing `kid`, and the set "SHOULD retain recently decommissioned signing keys". Verifiers refetch on an unknown `kid`. Concretely:
1. Publish the next key without signing with it. Wait at least the longest verifier cache (300 s), plus PyJWKClient's `cooldown_duration` (30 s), so no verifier has to refetch mid-traffic [29].
2. Start signing with the next key.
3. Keep the old key published for at least the token lifetime plus leeway (600 + 30 s), then remove it.

That means one key in steady state and two (at most three) during rotation. **Emergency rotation** (key compromise): remove the key at once. Exposure then lasts until each verifier's cache expires, at most `lifespan`. That bound is the security argument for a short `lifespan`.

**Recommendation:** serve `/.well-known/jwks.json` with `max-age=300`, `alg` and `use` on each key, and the three-step rotation, documented as a runbook rather than automated.

**Defend it:** "Verifiers cache the key set for five minutes and refetch on an unknown `kid`. So I publish the next key before signing with it and keep the old one for a token lifetime. A compromised key stops being trusted within one cache period."

---

## 9. Revocation and role changes before expiry

CHALLENGE question 7 asks this directly [1]. ADR 0003 already accepts "short TTL, plus a per-user token version checked on the protected write". The options below are ways to implement that, and alternatives.

| Option | Lag | Cost to the main app | Auth service down | Notes |
|---|---|---|---|---|
| Short TTL only (10 min) | ≤ 10 min | None | No effect until the JWKS cache expires | The baseline. Fine for reads |
| `jti` denylist, polled by the main app | Poll interval | Background fetch and cache | List goes stale; you must choose fail open or fail closed | Key on `jti`, never the raw token (CVE-2026-102269) [28]. Revokes one token, not a user |
| **Per-user cutoff** (`tokens_valid_after`) checked online, **only on the protected write** | 0 on writes | One call to the auth service per PATCH | **PATCH fails closed (503)**. Reads are public and unaffected | Bump the cutoff on role change, deactivation or "log out everywhere". Needs no new claim: reject if `iat ≤ cutoff` |
| RFC 7662 introspection on writes | 0 | One call per PATCH plus a **service credential**: RFC 7662 says the endpoint "MUST also require some form of authorization" against token scanning [38] | Fails closed | Returns current `active` and `scope`, so roles are fresh too |
| Refresh tokens with rotation | ≤ access TTL (5 min) | None | Refresh fails; access tokens expire within minutes | New token type, a table, and reuse detection. Public clients need rotation or sender-constraining (RFC 9700 §2.2.2) [37]. More than "login plus roles" needs [1] |

### How the online write check could work

The main app forwards the caller's own bearer token to an auth endpoint, for example `GET /api/token/status`, which works like OIDC UserInfo. The auth service verifies it and checks `is_active` and `iat > tokens_valid_after`. It returns `{"active": true, "scope": "<current scopes>"}`.

Because the token authenticates itself and the endpoint only reports on that token, scanning gains nothing. So no service secret is needed, unlike RFC 7662. The current `scope` makes role changes take effect on the next write. The main app then needs no `token_version` claim and no extra secret.

**Recommendation:** default: a 10-minute TTL, and every request still verified locally. On the one protected write, add the online status check and fail closed with 503 if the auth service doesn't answer. Fallback, if you want zero coupling: a 5-minute TTL and accept the lag.

**Defend it:** "Every request is verified locally, so reads never touch the auth service. The one write that matters makes one extra call. That call sees revocations and role changes instantly and fails closed if auth is down. Editors are rare, so that's the right place to pay."

---

## 10. When the auth service is down

| Situation | With PyJWKClient defaults [29] | Recommended behaviour |
|---|---|---|
| Public pages and `GET /api/brands/` | Unaffected (no token) | Same |
| PATCH, JWKS cached (< 300 s old) | Verifies locally | Verifies locally. Then the §9 write check fails closed: **503 with `Retry-After`** |
| PATCH, JWKS cache expired | Fetch fails → `PyJWKClientConnectionError` → the request fails | **503, not 401**. A 401 `invalid_token` tells clients to discard a token that is actually fine [36] |
| Unknown `kid` | One forced refetch, then a 30 s cooldown (refetch storms were CVE-2026-48524 and -101917) [28][29] | Same. Reject with 401 if still unknown |
| Cold start of the main app | No cache, so the first PATCH triggers a fetch | Don't make the main app `depends_on` the auth service. It should boot and serve reads without it |

- **Timeout:** PyJWKClient holds a lock during the fetch, with a 30 s default timeout [29]. Set `timeout` to 2–3 s, or one slow fetch stalls every PATCH thread.
- **Stale keys:** PyJWKClient has no stale-if-error mode [29]. If you adopt the §9 write check, writes fail closed during an outage anyway, so stale keys gain nothing. Keep the default (no stale use). Without the §9 check, a bounded stale-if-error window (≤ 1 h) in the shared library is the availability option. It costs exposure if a removed key was compromised.

**Defend it:** "Reads never depend on auth. Writes verify locally with a five-minute key cache, then check status online. If auth is down they return 503, not 401, so clients retry instead of throwing their token away."

---

## 11. Service, container and settings

### Apps and middleware

| Piece | Needed? | Why |
|---|---|---|
| `django.contrib.auth`, `contenttypes` | Yes | User model, `Group`, hashers. `contenttypes` is required by `auth` |
| `rest_framework` | Yes (recommended) | Same pin as the main app (ADR 0002), serializers and throttles. Plain views would also work for two endpoints, but you'd hand-write the throttling |
| `django.contrib.admin`, `sessions`, `messages`, `staticfiles` | **No** | The admin brings sessions, CSRF, static files and an extra password login that DRF throttles don't cover. 2026 CVEs affecting 5.2's admin: CVE-2026-4277, -4292, -15920 and -87975 (formsets). Sessions: CVE-2026-35192 [15]. Manage roles with management commands (`grant_role`, `revoke_role`, `revoke_tokens`) instead. These also make a good live demo of "change a role before expiry" |
| Middleware | `SecurityMiddleware`, `CommonMiddleware` | No session or auth middleware: login is the only unauthenticated write, and no cookie is ever set. Without cookies there's no ambient credential, so CSRF doesn't apply. `check --deploy` will raise security.W003; explain it rather than silence it [11] |
| whitenoise | **No** | Only needed for admin or browsable-API static files. See the ADR 0008 note below |

### DRF settings (auth service)

- `DEFAULT_RENDERER_CLASSES`: `JSONRenderer` only (no browsable API, so no static files).
- `DEFAULT_PARSER_CLASSES`: `JSONParser` only. Dropping `FormParser` and `MultiPartParser` removes the 2026 multipart DoS class (CVE-2026-33033, CVE-2026-108147) from this service [15][18].
- `DEFAULT_AUTHENTICATION_CLASSES`: `[]`.
- `DEFAULT_PERMISSION_CLASSES`: deny by default. Set `AllowAny` explicitly on login and JWKS.
- `NUM_PROXIES = 0`.
- DRF ≥ 3.18.2 fixes three High advisories from 2026-10-22 that hit any unauthenticated JSON endpoint: JSONParser codec selection, `Accept`-header CPU burn, and the authtoken `TokenProxy` [28]. ADR 0002's floor of 3.18.3 covers them.

### Django settings

- `DEBUG` from the environment, default `False`. `ALLOWED_HOSTS` explicit, for example `auth` (the compose service name the main app uses) and `localhost`.
- `SECRET_KEY` from a secret file. It's still required even though JWTs don't use it.
- `DATA_UPLOAD_MAX_MEMORY_SIZE` small, for example 16 KiB, since a login body is tiny.
- `SECURE_CONTENT_TYPE_NOSNIFF` is already on by default.
- In production behind TLS: `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, and `SECURE_PROXY_SSL_HEADER`. Set the last one only "if you control the proxy and it strips the header" [12].
- Run `check --deploy` with production-like values and explain each remaining warning (the django-lts skill).

### Container and database

- Own `postgres:18-alpine` pinned by digest. The main app gets no credentials for it (ADR 0006).
- `python:3.14-slim-trixie` pinned by digest, gunicorn sync workers, a non-root `USER`, no Docker socket (ADR 0008).
- Secrets via compose `secrets:`: the signing key, `SECRET_KEY` and the DB password.
- A `/healthz` check that confirms the DB connection and that the key loaded, for compose `healthcheck`.

### Django 5.2 security releases in 2026

There were nine 2026 security release dates (Feb 3 → Nov 3) [15].
- Relevant to this service: CVE-2025-13473 (Feb, mod_wsgi only, so not us) [16]. The header-parsing DoS CVE-2026-84429 (Oct) and the multipart and ASGI DoS CVEs; the multipart ones are avoided by the JSON-only parser and sync WSGI [15].
- 5.2.19 (2026-11-03) carries five CVEs, four of them GIS. The non-GIS ones are the `Vary`-header cache issue (CVE-2026-113593) and the multipart memory issue (CVE-2026-108147). Neither applies to a JSON-only service with no cache middleware [18].
- 5.2.19 clears the cooldown on 2026-11-10 (ADR 0012).

**Recommendation:** an API-only service with `auth`, `contenttypes` and DRF on JSON only, two middleware, no admin, no sessions, no whitenoise, and role management by command.

**Defend it:** "The auth service is the most valuable target, so it gets the least code. No admin, no sessions, no cookies, no form parsing. Roles change through management commands, which leave an audit trail in the shell history and logs."

---

## 12. Sample decoded token (illustrative values)

```json
{
  "alg": "EdDSA",
  "typ": "at+jwt",
  "kid": "kPrK_qmxVWaYVA9wwBF6Iuo3vVzz7TxHCTwXBygrS4k"
}
```
```json
{
  "iss": "http://auth:8000",
  "aud": "brands-api",
  "sub": "5f0c6b9e-2d4a-4c1e-9a57-3b8e2f1d7c40",
  "client_id": "brands-cli",
  "scope": "brands:read brands:write",
  "iat": 1794218400,
  "nbf": 1794218400,
  "exp": 1794219000,
  "jti": "q3Jm0vXk2l9cZp7RtY4s1A"
}
```
(`iat` = 2026-11-09T10:00:00Z, `exp` = `iat` + 600.)

## 13. Sample JWKS document

The public key is RFC 8037's Appendix A.2 example, so the `kid` can be checked against RFC 8037 A.3 [40].

```json
{
  "keys": [
    {
      "kty": "OKP",
      "crv": "Ed25519",
      "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo",
      "kid": "kPrK_qmxVWaYVA9wwBF6Iuo3vVzz7TxHCTwXBygrS4k",
      "use": "sig",
      "alg": "EdDSA"
    }
  ]
}
```
Served with `Content-Type: application/jwk-set+json` and `Cache-Control: public, max-age=300`.

---

## What the shared library must accept

For the Pillar 6 counterpart. Each line is a check the verifier performs. Reject on any failure.

**Before parsing**
1. `Authorization: Bearer <token>`, where the token matches `^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$` and is at most 4 KiB. rfc8725bis-10 §3.14 requires rejecting anything else [45]. PyJWT 2.15.1 now *tolerates* trailing `=` padding [30], so this check is the library's job.

**Header**
2. `alg` must be in the allow-list `["EdDSA"]`, passed as `algorithms=`. Never read it from the header. Later, during the expand phase: `["EdDSA", "Ed25519"]`.
3. `typ`: case-insensitive match on `at+jwt` or `application/at+jwt` (RFC 9068 §4, RFC 7515 §4.1.9) [33][42]. ADR 0003 says `== "at+jwt"`; see Conflicts. PyJWT doesn't check `typ`, so use `decode_complete`.
4. `kid`: present, 43 characters of `[A-Za-z0-9_-]`. Look it up in the cached JWKS only. Ignore `jku`, `x5u`, `jwk` and `x5c`; never fetch them (rfc8725bis §3.10) [45]. Unknown `crit` values are rejected by PyJWT ≥ 2.12 [28].

**Keys accepted from the JWKS**
5. Only `kty == "OKP"`, `crv == "Ed25519"`, `use` absent or `"sig"`, `alg` absent or `"EdDSA"`, with a `kid`. This closes the polymorphic-`EdDSA` gap: the name alone also covers Ed448 [43].

**Claims** (all REQUIRED: `options={"require": ["iss", "aud", "sub", "exp", "iat", "nbf", "jti"]}`, then check `client_id` and `scope` yourself, since PyJWT's `require` only checks presence) [29]
6. `iss`: exact match against configuration (pass `issuer=`; `None` skips the check) [29].
7. `aud`: pass `audience="brands-api"` with `strict_aud=True` (the token carries one string) [29].
8. `exp` > now − leeway; `nbf` and `iat` ≤ now + leeway; leeway ≤ 30 s. Optionally reject when `exp − iat > 900`, to catch a misconfigured issuer.
9. `sub`: a string that parses as a UUID. This is the main app's only user key.
10. `jti`: a non-empty string. `client_id`: a non-empty string.
11. `scope`: a string. Split on single spaces. Each item matches RFC 6749's scope-token syntax [35]. Authorize by membership, for example `"brands:write" in scopes`.

**Errors** (RFC 6750 §3.1, RFC 9068 §4) [36][33]
12. Bad or expired token: 401 with `WWW-Authenticate: Bearer error="invalid_token"`. Missing scope: 403 with `error="insufficient_scope"`. JWKS unreachable: 503, not 401.

**JWKS client**
13. `PyJWKClient(uri, lifespan=300, timeout=3, cooldown_duration=30)`, using https outside compose. Redirects are refused since 2.14 [29][30].
14. An injectable hook (a Protocol) for the §9 online status check on protected writes, so the core stays framework-free and testable with plain pytest.

**Test vectors:** the RFC 8037 thumbprint (A.3); `alg: none`; HS256 signed with the public key; an Ed448 key under `EdDSA`; `typ: JWT`; `typ: application/at+jwt` (must pass); a missing `exp`; a wrong `aud`; a list `aud` under strict mode; an unknown `kid`; padded segments.

---

## Open decisions for the user

1. **How do imported users get passwords?** (a) Unusable passwords plus `changepassword` for demo users. (b) A verify-only `$wp$` bcrypt hasher with upgrade on login (+`bcrypt`). (c) Random one-time passwords printed once. **Recommend (a)**; (b) is the documented upgrade path.
2. **Which hasher stores new passwords?** PBKDF2 (default), scrypt (built-in) or Argon2id (+4 packages). **Recommend scrypt first, PBKDF2 second.**
3. **Which UUID version is `external_id`?** v4, v7 or v5-from-WP-ID. **Recommend v4.**
4. **How does the main app learn each reviewer's `external_id`?** Options:
   - The auth service writes a `wp_user_id → external_id` map (no emails, no hashes) with a management command, and the main app's import reads it.
   - Both imports derive `uuid5(namespace, wp_id)` independently. No coordination, but derivable from public WP IDs.
   - An internal lookup API. Needs service auth.

   **Recommend the export file** (offline, no runtime coupling). This decision crosses into Pillar 1.
5. **Where do roles and scopes live?** Groups + Permissions, Groups + a `Scope` model, or own models. **Recommend Groups + `Scope`.**
6. **How do revocation and role changes take effect before expiry?** TTL only, `jti` denylist, per-user cutoff with an online check on the write, RFC 7662 introspection, or refresh tokens. **Recommend the online status check on PATCH, failing closed**, as the implementation of ADR 0003's "per-user token version".
7. **Token lifetime?** 5, 10 or 15 minutes. **Recommend 10 minutes, 30 s leeway.**
8. **Should the main app use stale JWKS keys when the fetch fails?** None (the PyJWKClient default) or a bounded window. **Recommend none if decision 6 is adopted**; otherwise ≤ 1 h.
9. **Admin in the auth service?** None, or the admin on an internal-only port. **Recommend none**; use management commands.
10. **Brute-force protection?** DRF throttles (per IP + per username) on `DatabaseCache`, or django-axes. **Recommend DRF throttles.**
11. **Which login response shape and status?** RFC 6749-style fields with 401, or `400 invalid_grant`. **Recommend RFC 6749 field names, 401, and a generic body.**

---

## Conflicts with accepted decisions

None of these reverses an ADR. They are wording or precision issues worth a superseding note or a "Revisit when" line.

1. **ADR 0003: `algorithms=["EdDSA"]`.** RFC 9864 (October 2025) marks `EdDSA` Deprecated, and rfc8725bis-10 (approved, RFC Editor queue as of 2026-11-06) says new deployments SHOULD prefer `Ed25519` [43][45]. PyJWT 2.15.1 can't do `Ed25519` *(tested)* [31], so staying on `EdDSA` falls under RFC 9864's documented-requirement exception. Suggested "Revisit when": PyJWT releases RFC 9864 support (PR #1199).
2. **ADR 0003: "checks `typ == "at+jwt"`".** RFC 9068 §4 says verifiers MUST accept `at+jwt` *or* `application/at+jwt` [33], and RFC 7515 makes the comparison case-insensitive [42]. An exact match works with our own issuer but would reject a conformant one.
3. **ADR 0003 cites RFC 9068.** RFC 9068 §2.1 requires RS256 support from conforming servers [33]. EdDSA-only is a deliberate RFC 9068-*style* profile. Adding RS256 would widen the algorithm list for no gain, but the ADR shouldn't imply full conformance.
4. **ADR 0003 consequence: "keeps verifying … until its cached JWKS expires".** Accurate, but with PyJWKClient's defaults that's 300 s, and there's no stale fallback [29]. Worth quantifying in the ADR.
5. **ADR 0008: "both services … need something to serve static files".** True for the main app. The auth service needs none if it drops the admin and the browsable API (§11), so whitenoise is optional there.

## Corrections to `best-practices-2026.md` §8 and `stack-decisions.md` §2b

- "Django patched a timing enumeration bug in Feb 2026": CVE-2025-13473 affected only `django.contrib.auth.handlers.modwsgi.check_password()` [16]. It doesn't affect gunicorn, DRF or `ModelBackend`.
- "Argon2 hasher" for login hardening: Django's PBKDF2 already exceeds OWASP, and built-in scrypt is memory-hard with no dependency (§4).
- "Serve a stale JWKS … for a bounded time": PyJWKClient can't. It's custom code, and unnecessary if writes check status online (§10).
- WP hasher "(phpass `$P$…`, or … `$wp$2y$…`)": the data has only `$wp$2y$`. The stored value also needs an algorithm prefix, because `identify_hasher` splits on the first `$` (§3).
- "Map WP roles: … subscriber/author → reader": the data has only `administrator` and `subscriber`.
- `options={"require": ["exp","iat","iss","aud","sub"]}`: add `nbf` and `jti`, check `client_id` and `scope`, and pass `strict_aud=True` (§ "What the shared library must accept").
- "Being revised as `draft-ietf-oauth-rfc8725bis`": now at -10 (2026-08-21) and in the RFC Editor queue. It adds the `Ed25519` preference, one algorithm per key, `typ` prefix rules and a JWT character-set check [45].

## Not verified

- PyPI maintainer identities for `bcrypt` (pyca) and `argon2-cffi` (hynek) come from the repo URLs in PyPI JSON, not from PyPI's bot-gated project pages.
- Why django-axes's changelog lists 8.3.2 (2026-08-30) when no 8.3.2 exists on PyPI.
- Whether 5.2 is affected by CVE-2026-113733. The advisory lists 5.2 as a supported version but gives no 5.2 fix, and the 5.2.19 notes don't mention it [17][18]. It needs multi-table inheritance of `password`, which §2 avoids anyway.
- Timings (PBKDF2 72 ms, scrypt 96 ms, Argon2 14 ms, WP bcrypt 41 ms, unusable-password path 68 ms) come from one aarch64 machine under OrbStack. Ratios matter more than absolutes.
- The WP admin's demo password was deliberately not tested against its hash.
- When PyJWT will merge and release RFC 9864 support (PR #1199 has been open since 2026-08-19).
- django-announce itself (a Google Group) wasn't read. The 2026 release list comes from Django's security archive and weblog [15][16][17].
- Context7 was used for Django 5.2 and DRF 3.18.3 docs. RFCs, PyJWT, WordPress and pyca facts come from source fetched directly, because Context7 doesn't index those at the needed tags.

---

## Sources

1. `CHALLENGE.md` (Pillar 5; "Decisions you will defend live" Q7; setup credentials). Local, 2026-11-09.
2. `db/dump.sql`: counts and format prefixes extracted by a local script that printed no hashes, emails or names. Local, 2026-11-09.
3. Django 5.2.18 `contrib/auth/hashers.py`: <https://github.com/django/django/blob/5.2.18/django/contrib/auth/hashers.py>
4. Django 5.2.18 `contrib/auth/backends.py`: <https://github.com/django/django/blob/5.2.18/django/contrib/auth/backends.py>
5. Django 5.2.18 `contrib/auth/__init__.py` (`_clean_credentials`): <https://github.com/django/django/blob/5.2.18/django/contrib/auth/__init__.py>
6. Django 5.2.18 `views/debug.py` (`SafeExceptionReporterFilter`): <https://github.com/django/django/blob/5.2.18/django/views/debug.py>
7. Django 5.2 docs, Password management: <https://docs.djangoproject.com/en/5.2/topics/auth/passwords/>
8. Django 5.2 docs, Customizing authentication: <https://docs.djangoproject.com/en/5.2/topics/auth/customizing/>
9. Django 5.2 docs, Using the authentication system (default permissions): <https://docs.djangoproject.com/en/5.2/topics/auth/default/>
10. Django 5.2 docs, Cache framework: <https://docs.djangoproject.com/en/5.2/topics/cache/>
11. Django 5.2 docs, System check framework (security checks): <https://docs.djangoproject.com/en/5.2/ref/checks/>
12. Django 5.2 docs, Settings (`AUTH_USER_MODEL`, `SECURE_*`, `CACHES`): <https://docs.djangoproject.com/en/5.2/ref/settings/>
13. Django 5.2 docs, Constraints reference: <https://docs.djangoproject.com/en/5.2/ref/models/constraints/>
14. Django 5.2 docs, Signals (`post_migrate`): <https://docs.djangoproject.com/en/5.2/ref/signals/>
15. Django security issues archive (2026 entries), read 2026-11-09: <https://docs.djangoproject.com/en/dev/releases/security/>
16. Django weblog, security releases 2026-02-03: <https://www.djangoproject.com/weblog/2026/feb/03/security-releases/>
17. Django weblog, security releases 2026-11-03: <https://www.djangoproject.com/weblog/2026/nov/03/security-releases/>
18. Django 5.2.19 release notes (2026-11-03): <https://docs.djangoproject.com/en/5.2/releases/5.2.19/>
19. Python 3.14 `uuid` docs: <https://docs.python.org/3.14/library/uuid.html>
20. RFC 9562, UUIDs (May 2024), §8: <https://www.rfc-editor.org/rfc/rfc9562>
21. WordPress 6.9 `wp-includes/pluggable.php` (`wp_hash_password`, `wp_check_password`): <https://github.com/WordPress/WordPress/blob/6.9/wp-includes/pluggable.php>
22. WordPress 6.9 `wp-includes/default-filters.php`: <https://github.com/WordPress/WordPress/blob/6.9/wp-includes/default-filters.php>
23. make.wordpress.org, "WordPress 6.8 will use bcrypt for password hashing" (2025-02-17): <https://make.wordpress.org/core/2025/02/17/wordpress-6-8-will-use-bcrypt-for-password-hashing/>
24. pyca/bcrypt 5.0.0 README/changelog and `src/_bcrypt/src/lib.rs`: <https://github.com/pyca/bcrypt/tree/5.0.0>
25. OWASP Password Storage Cheat Sheet (no date shown; read 2026-11-09): <https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html>
26. OWASP Authentication Cheat Sheet (read 2026-11-09): <https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html>
27. PyPI JSON API, read 2026-11-09: `https://pypi.org/pypi/<name>/json` for PyJWT, cryptography, bcrypt, argon2-cffi, argon2-cffi-bindings, django-axes, djangorestframework, passlib.
28. GitHub Advisory Database API (`/advisories?ecosystem=pip&affects=<pkg>`) for pyjwt, cryptography, djangorestframework, bcrypt, argon2-cffi, argon2-cffi-bindings and django-axes; OSV query for `pyjwt==2.15.1`. Read 2026-11-09: <https://github.com/advisories>, <https://osv.dev>
29. PyJWT 2.15.1 source (`api_jws.py`, `api_jwt.py`, `api_jwk.py`, `jwks_client.py`, `jwk_set_cache.py`, `__init__.py`): <https://github.com/jpadilla/pyjwt/tree/2.15.1/jwt>
30. PyJWT CHANGELOG at 2.15.1: <https://github.com/jpadilla/pyjwt/blob/2.15.1/CHANGELOG.rst>
31. PyJWT issue #1190 (2026-07-13) and PR #1199 (2026-08-19), RFC 9864 support, both open: <https://github.com/jpadilla/pyjwt/issues/1190>, <https://github.com/jpadilla/pyjwt/pull/1199>
32. cryptography 50.0.2 docs, Ed25519 and key serialization: <https://github.com/pyca/cryptography/blob/50.0.2/docs/hazmat/primitives/asymmetric/ed25519.rst>, <https://github.com/pyca/cryptography/blob/50.0.2/docs/hazmat/primitives/asymmetric/serialization.rst>
33. RFC 9068, JWT Profile for OAuth 2.0 Access Tokens (October 2021): <https://www.rfc-editor.org/rfc/rfc9068>
34. RFC 8693, OAuth 2.0 Token Exchange (January 2020), §4.2–4.3: <https://www.rfc-editor.org/rfc/rfc8693>
35. RFC 6749, OAuth 2.0 (October 2012), §3.3, §5.1, §5.2: <https://www.rfc-editor.org/rfc/rfc6749>
36. RFC 6750, Bearer Token Usage (October 2012), §3.1: <https://www.rfc-editor.org/rfc/rfc6750>
37. RFC 9700 / BCP 240, OAuth 2.0 Security Best Current Practice (January 2025): <https://www.rfc-editor.org/rfc/rfc9700>
38. RFC 7662, Token Introspection (October 2015): <https://www.rfc-editor.org/rfc/rfc7662>
39. RFC 7517, JSON Web Key (May 2015): <https://www.rfc-editor.org/rfc/rfc7517>
40. RFC 8037, CFRG curves in JOSE (January 2017), §2, Appendix A: <https://www.rfc-editor.org/rfc/rfc8037>
41. RFC 7638, JWK Thumbprint (September 2015): <https://www.rfc-editor.org/rfc/rfc7638>
42. RFC 7515, JWS (May 2015), §4.1.9: <https://www.rfc-editor.org/rfc/rfc7515>
43. RFC 9864, Fully-Specified Algorithms for JOSE and COSE (October 2025): <https://www.rfc-editor.org/rfc/rfc9864>
44. RFC 8725 / BCP 225, JWT Best Current Practices (February 2020): <https://www.rfc-editor.org/rfc/rfc8725>
45. draft-ietf-oauth-rfc8725bis-10 (2026-08-21; datatracker IESG state "RFC Ed Queue", updated 2026-11-06): <https://datatracker.ietf.org/doc/draft-ietf-oauth-rfc8725bis/>
46. OpenID Connect Core 1.0 (errata set 2), §10.1.1: <https://openid.net/specs/openid-connect-core-1_0.html>
47. IANA Well-Known URIs registry (CSV), read 2026-11-09: <https://www.iana.org/assignments/well-known-uris/>
48. DRF 3.18.3 throttling guide and `rest_framework/throttling.py`: <https://github.com/encode/django-rest-framework/blob/3.18.3/docs/api-guide/throttling.md>, <https://github.com/encode/django-rest-framework/blob/3.18.3/rest_framework/throttling.py>
49. django-axes `CHANGES.rst` and installation docs (Django Commons): <https://github.com/django-commons/django-axes>
50. Docker Compose file reference, services → secrets: <https://docs.docker.com/reference/compose-file/services/#secrets>
51. Local verification, 2026-11-09: throwaway scripts in the session scratchpad run with `uv run --no-project --python 3.14 --exclude-newer 2026-11-02` against Django 5.2.18, PyJWT 2.15.1, cryptography 50.0.2, bcrypt 5.0.0 and argon2-cffi 25.1.0. They covered `uuid.uuid7`, migration serialization, EdDSA encode/decode with `typ`, `require` behaviour, the HS256 default, `Ed25519` rejection, the prefixed WP hash round trip with upgrade, the RFC 8037 thumbprint, OpenSSL key loading and hasher timings. Nothing was installed into the repo.
52. WordPress 6.9 `wp-includes/rest-api/endpoints/class-wp-rest-users-controller.php` (`has_published_posts` for callers without `list_users`): <https://github.com/WordPress/WordPress/blob/6.9/wp-includes/rest-api/endpoints/class-wp-rest-users-controller.php>
