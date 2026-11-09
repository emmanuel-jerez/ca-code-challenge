# 0006. One Postgres database per Django service

- Status: Accepted
- Date: 2026-11-09

## Context
CHALLENGE.md requires the auth service to have its own container and database. The
existing stack has a MariaDB for WordPress. The import must be re-runnable without
duplicates, which relies on unique constraints.

## Options considered
- **Reuse the WordPress MariaDB.** Rejected: blurs migration source and target, and
  Django silently ignores conditional (`condition=`) and functional unique constraints
  on MariaDB.
- **SQLite per service.** Simplest. Rejected: weak answer to "100x data" and to
  concurrent gunicorn workers.
- **Postgres 18, one container per service, psycopg 3.** Chosen.

## Decision
`postgres:18-alpine` pinned by digest, one per service; `psycopg[binary]>=3.3.6,<3.4`.
The main app gets no credentials for the auth database.

## Consequences
Two more containers in docker-compose. psycopg's docs prefer the local C build for
production; the binary wheel is a deliberate shortcut for a take-home.

## Revisit when
Deployment targets change, or the binary wheel lags a Postgres release.

## Sources
`docs/research/stack-validation.md` §3.2.
