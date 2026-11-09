# 0024. Imported users get no usable password; new passwords use scrypt

- Status: Accepted
- Date: 2026-11-09

## Context
CHALLENGE.md Pillar 5: the `wp_users` accounts must exist in the auth service after
migration, and "passwords may be reset; you decide how". The data
(`docs/research/pillar-5-auth-service.md` §1, §3; recounted from the dump on this date):
- **Users:** 9. All have WordPress 6.8+ bcrypt hashes (`$wp$2y$`), and there are no
  older phpass (`$P$`) hashes.
- **Roles:** 1 `administrator` and 8 `subscriber`.
- **The admin's password** is published in CHALLENGE.md (`admin` / `admin`).

| Hasher | Settings | Compared with OWASP | Dependencies |
|---|---|---|---|
| PBKDF2 (Django 5.2 default) | 1,000,000 iterations | Above OWASP's 600,000 | None |
| scrypt (`ScryptPasswordHasher`) | N=2^14, r=8, p=5 | Matches an OWASP setting | None (stdlib) |
| Argon2id | — | OWASP's first choice | 4 packages |

## Options considered
**Imported passwords:**
- **A verify-only WordPress hasher that upgrades on first login.** Users keep their
  passwords. Rejected:
  - it adds `bcrypt` and about 25 lines of crypto code to own and later delete;
  - it keeps WordPress hashes in the auth database;
  - it carries over the published admin password;
  - its timing marks accounts that haven't migrated yet.
- **Random one-time passwords, printed once.** Rejected: the secrets land in terminal
  scrollback and logs, and re-runs must not regenerate them.
- **Unusable passwords; demo accounts set by hand.** Chosen.

**Hasher for new passwords:**
- **Argon2id.** Rejected: 4 packages, and Django's default of 100 MiB per login is a
  memory lever on an unauthenticated endpoint.
- **PBKDF2.** Kept as the fallback: not memory-hard.
- **scrypt first.** Chosen: memory-hard, no new dependency.

## Decision
- **Import:** every imported account gets `set_unusable_password()`.
  - Demo accounts get passwords with `manage.py changepassword`, which runs the
    password validators.
  - The import never reads `wp_users.user_pass`. Its MariaDB user has no grant on that
    column.
  - Re-runs upsert on `wp_user_id`. They never reset a password or overwrite a role
    already changed in the auth service.
- **Role mapping:** `administrator` → `editor` (not superuser), `subscriber` → `reader`.
  Any other role gets no role and a warning.
- **Hashers:** `PASSWORD_HASHERS` lists `ScryptPasswordHasher` first and
  `PBKDF2PasswordHasher` second, so hashes made before the switch still verify and
  upgrade on login.

## Consequences
- No WordPress password hash ever reaches the auth database.
- Real users would have to reset their passwords. The verify-only hasher is the
  documented upgrade path if they must keep them. It would need no phpass code, because
  only `$wp$2y$` hashes exist.

## Revisit when
Real users must keep their WordPress passwords, or OWASP's guidance or Django's
defaults move past these settings.

## Sources
`docs/research/pillar-5-auth-service.md` §3–4; [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
