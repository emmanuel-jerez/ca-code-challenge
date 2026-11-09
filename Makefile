SHELL := /bin/bash
COMPOSE := docker compose
WPCLI := $(COMPOSE) run --rm wpcli
AUTH_KEY := secrets/jwt_ed25519.pem

.PHONY: help up down restart logs reset wp bootstrap dump status skills wp-import-user import import-dry-run test contracts auth-key auth-import auth-import-dry-run auth-map test-auth test-shared check-shared

help:
	@echo "Targets:"
	@echo "  up              Start db + wordpress + phpmyadmin + main app + auth service"
	@echo "  down            Stop containers (preserve data)"
	@echo "  reset           Stop containers AND wipe DB volume (full cold start on next 'up')"
	@echo "  logs            Tail wordpress + db logs"
	@echo "  wp ARGS=\"...\" Run wp-cli inside the stack (e.g. make wp ARGS=\"plugin list\")"
	@echo "  bootstrap       One-shot: install WP core + plugins + seed all content"
	@echo "  dump            Export current DB to db/dump.sql"
	@echo "  status          Show running services"
	@echo "  skills          Link .agents/skills into .claude/skills for Claude Code"
	@echo "  wp-import-user  Create the read-only MariaDB user on an existing db volume"
	@echo "  import          Import WordPress content into the main app (safe to re-run)"
	@echo "  import-dry-run  Same checks and counts, then roll back"
	@echo "  test            Run the main app's tests (needs main-db running)"
	@echo "  auth-key        Generate the auth service's Ed25519 signing key (once)"
	@echo "  auth-import     Import WordPress users into the auth service (safe to re-run)"
	@echo "  auth-import-dry-run  Same checks and counts, then roll back"
	@echo "  auth-map        Write secrets/user-map.json (wp_user_id -> external_id)"
	@echo "  test-auth       Run the auth service's tests (needs auth-db running)"
	@echo "  test-shared     Run the shared library's tests, types and lint (no Django project)"
	@echo "  check-shared    Check the library's version was bumped and both services re-locked"
	@echo "  contracts       Regenerate contracts/ from the API after an intended change"

# The auth service won't start without its signing key, so make it first.
up: $(AUTH_KEY)
	$(COMPOSE) up -d db wordpress phpmyadmin main-db main-app auth-db auth-service

down:
	$(COMPOSE) down

reset:
	$(COMPOSE) down -v
	@echo "Volume wiped. Run 'make up' to start fresh from db/dump.sql"

logs:
	$(COMPOSE) logs -f wordpress db

wp:
	$(WPCLI) $(ARGS)

bootstrap:
	$(COMPOSE) run --rm --entrypoint bash wpcli /scripts/seed.sh

dump:
	@mkdir -p db
	$(COMPOSE) exec db sh -c 'mariadb-dump -u root -p"$$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 --add-drop-table --skip-extended-insert --ignore-table="$$MYSQL_DATABASE.auth_import_users" "$$MYSQL_DATABASE"' > db/dump.sql
	@echo "Wrote db/dump.sql ($$(wc -l < db/dump.sql) lines)"

status:
	$(COMPOSE) ps

skills:
	./scripts/link-agent-skills.sh

wp-import-user:
	$(COMPOSE) up -d --wait db
	$(COMPOSE) exec db bash /docker-entrypoint-initdb.d/02-wp-import-user.sh
	$(COMPOSE) exec db bash /docker-entrypoint-initdb.d/03-wp-auth-import-user.sh

import:
	$(COMPOSE) run --rm --build wp-import

import-dry-run:
	$(COMPOSE) run --rm --build wp-import sh -c "python manage.py migrate --noinput && python manage.py import_wp --dry-run"

test:
	cd main-app && uv run pytest

contracts:
	cd main-app && UPDATE_CONTRACTS=1 uv run pytest catalog/tests/test_brand_list_contract.py

# Generated in the auth image, so it needs only Docker. A file target: made
# once, never overwritten. To rotate, follow ADR 0033.
auth-key: $(AUTH_KEY)

$(AUTH_KEY):
	@mkdir -p secrets
	$(COMPOSE) build auth-service
	docker run --rm --user 0:0 --network none -v "$(CURDIR)/secrets:/secrets" \
		brandreviews/auth-service:local python keygen.py /secrets/jwt_ed25519.pem

auth-import:
	$(COMPOSE) run --rm --build auth-import

auth-import-dry-run:
	$(COMPOSE) run --rm --build auth-import sh -c "python manage.py migrate --noinput && python manage.py import_wp_users --dry-run"

# The map the main app's import will read to fill Reviewer.auth_user_id (ADR 0020).
auth-map:
	@mkdir -p secrets
	$(COMPOSE) exec -T auth-service python manage.py export_user_map > secrets/user-map.json
	@echo "Wrote secrets/user-map.json"

test-auth:
	cd auth-service && uv run pytest

test-shared:
	cd shared-lib && uv run pytest && uv run mypy src tests && uv run ruff check && uv run ruff format --check

# A library change must bump its version (ADR 0025); a bump makes each
# service's `uv lock --check` fail until it re-locks.
check-shared:
	scripts/check-shared-lib-version.sh
	cd main-app && uv lock --check
	cd auth-service && uv lock --check
