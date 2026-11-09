# 0007. Read WordPress from MariaDB with PyMySQL

- Status: Accepted
- Date: 2026-11-09

## Context
The import must bring brands, reviews, industries, users and postmeta (including Yoast
SEO keys) into the new models, and be re-runnable. Sources available: the MariaDB
database, the WP REST API, and `db/dump.sql`.

## Options considered
- **WP REST API.** A stable public contract. Rejected: `/users` hides fields without
  auth, Yoast meta may be missing, and it's slow at 100x the data.
- **Parse `dump.sql`.** No running WP needed. Rejected: fragile SQL parsing.
- **Query MariaDB directly**, chosen. Drivers:
  - **mysqlclient.** Fast C driver. Rejected: no Linux wheels, so the image would need
    a compiler and MySQL headers.
  - **PyMySQL.** Pure Python. Chosen.

## Decision
A `manage.py` command connects with a read-only DB user through PyMySQL
(`PyMySQL>=1.2.3,<1.3`), uses parameterized fixed queries only, and upserts on each
row's WordPress ID.

## Consequences
- Coupled to WordPress's internal schema; acceptable for a one-way migration.
- PyMySQL 1.2.4 (a SQL-injection fix) was released on 2026-11-09 and is still inside
  the cooldown. Our queries are fixed and parameterized against a read-only user, so we
  wait (ADR 0012).

## Revisit when
PyMySQL 1.2.4 clears the cooldown (raise the floor), or the import moves off the
legacy database.

## Sources
`docs/research/stack-validation.md` §3.1; `docs/research/best-practices-2026.md` §4.
