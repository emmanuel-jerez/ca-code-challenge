#!/bin/bash
# Creates the read-only MariaDB user the auth service's user import connects as.
#
# It can read one view and nothing else: each user's ID, login, email and
# wp_capabilities value. Not user_pass, and not the rest of wp_usermeta, which
# holds session tokens once anyone logs into wp-admin (ADR 0024). A column
# grant on wp_usermeta couldn't hide those rows; a view can.
# MAX_USER_CONNECTIONS 1 stops two imports from reading at once.
#
# Runs once, on the db container's first start (docker-entrypoint-initdb.d).
# For an existing volume, run `make wp-import-user`. Safe to re-run.
set -euo pipefail

: "${WP_AUTH_IMPORT_DB_USER:?WP_AUTH_IMPORT_DB_USER must be set}"
: "${WP_AUTH_IMPORT_DB_PASSWORD:?WP_AUTH_IMPORT_DB_PASSWORD must be set}"
root_password="${MARIADB_ROOT_PASSWORD:-${MYSQL_ROOT_PASSWORD:?root password must be set}}"
database="${MARIADB_DATABASE:-${MYSQL_DATABASE:?database name must be set}}"

# Identifiers can't be bound as parameters, so restrict them to safe characters.
for name in "$WP_AUTH_IMPORT_DB_USER" "$database"; do
  [[ "$name" =~ ^[A-Za-z0-9_]+$ ]] || { echo "unsafe identifier: $name" >&2; exit 1; }
done
# Escape the password for a single-quoted SQL string literal.
password_sql="${WP_AUTH_IMPORT_DB_PASSWORD//\\/\\\\}"
password_sql="${password_sql//\'/\\\'}"

# SQL SECURITY DEFINER: the view reads the base tables with its creator's
# rights, so the import user needs a grant on the view only.
mariadb --protocol=socket -uroot --password="$root_password" <<SQL
CREATE OR REPLACE SQL SECURITY DEFINER VIEW \`${database}\`.auth_import_users AS
  SELECT u.ID, u.user_login, u.user_email, m.meta_value AS capabilities
  FROM \`${database}\`.wp_users u
  LEFT JOIN \`${database}\`.wp_usermeta m
    ON m.user_id = u.ID AND m.meta_key = 'wp_capabilities';
CREATE USER IF NOT EXISTS '${WP_AUTH_IMPORT_DB_USER}'@'%';
ALTER USER '${WP_AUTH_IMPORT_DB_USER}'@'%'
  IDENTIFIED BY '${password_sql}'
  WITH MAX_USER_CONNECTIONS 1;
GRANT SELECT ON \`${database}\`.auth_import_users TO '${WP_AUTH_IMPORT_DB_USER}'@'%';
SQL
echo "Read-only auth import user '${WP_AUTH_IMPORT_DB_USER}' is ready."
