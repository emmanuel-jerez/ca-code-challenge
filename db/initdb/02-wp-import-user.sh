#!/bin/bash
# Creates the read-only MariaDB user the Django importer connects as.
#
# It can read the five content tables and only the ID and display_name columns
# of wp_users, so a compromised importer can't read password hashes or emails.
# MAX_USER_CONNECTIONS 1 stops two imports from reading at once.
#
# Runs once, on the db container's first start (docker-entrypoint-initdb.d).
# For an existing volume, run `make wp-import-user`. Safe to re-run.
set -euo pipefail

: "${WP_IMPORT_DB_USER:?WP_IMPORT_DB_USER must be set}"
: "${WP_IMPORT_DB_PASSWORD:?WP_IMPORT_DB_PASSWORD must be set}"
root_password="${MARIADB_ROOT_PASSWORD:-${MYSQL_ROOT_PASSWORD:?root password must be set}}"
database="${MARIADB_DATABASE:-${MYSQL_DATABASE:?database name must be set}}"

# Identifiers can't be bound as parameters, so restrict them to safe characters.
for name in "$WP_IMPORT_DB_USER" "$database"; do
  [[ "$name" =~ ^[A-Za-z0-9_]+$ ]] || { echo "unsafe identifier: $name" >&2; exit 1; }
done
# Escape the password for a single-quoted SQL string literal.
password_sql="${WP_IMPORT_DB_PASSWORD//\\/\\\\}"
password_sql="${password_sql//\'/\\\'}"

mariadb --protocol=socket -uroot --password="$root_password" <<SQL
CREATE USER IF NOT EXISTS '${WP_IMPORT_DB_USER}'@'%';
ALTER USER '${WP_IMPORT_DB_USER}'@'%'
  IDENTIFIED BY '${password_sql}'
  WITH MAX_USER_CONNECTIONS 1;
GRANT SELECT ON \`${database}\`.wp_posts TO '${WP_IMPORT_DB_USER}'@'%';
GRANT SELECT ON \`${database}\`.wp_postmeta TO '${WP_IMPORT_DB_USER}'@'%';
GRANT SELECT ON \`${database}\`.wp_terms TO '${WP_IMPORT_DB_USER}'@'%';
GRANT SELECT ON \`${database}\`.wp_term_taxonomy TO '${WP_IMPORT_DB_USER}'@'%';
GRANT SELECT ON \`${database}\`.wp_term_relationships TO '${WP_IMPORT_DB_USER}'@'%';
GRANT SELECT (ID, display_name) ON \`${database}\`.wp_users TO '${WP_IMPORT_DB_USER}'@'%';
SQL
echo "Read-only import user '${WP_IMPORT_DB_USER}' is ready."
