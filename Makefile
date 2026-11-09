SHELL := /bin/bash
COMPOSE := docker compose
WPCLI := $(COMPOSE) run --rm wpcli

.PHONY: help up down restart logs reset wp bootstrap dump status skills wp-import-user import import-dry-run test

help:
	@echo "Targets:"
	@echo "  up              Start db + wordpress + phpmyadmin + main app"
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

up:
	$(COMPOSE) up -d db wordpress phpmyadmin main-db main-app

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
	$(COMPOSE) exec db sh -c 'mariadb-dump -u root -p"$$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 --add-drop-table --skip-extended-insert "$$MYSQL_DATABASE"' > db/dump.sql
	@echo "Wrote db/dump.sql ($$(wc -l < db/dump.sql) lines)"

status:
	$(COMPOSE) ps

skills:
	./scripts/link-agent-skills.sh

wp-import-user:
	$(COMPOSE) up -d db
	$(COMPOSE) exec db bash /docker-entrypoint-initdb.d/02-wp-import-user.sh

import:
	$(COMPOSE) run --rm --build wp-import

import-dry-run:
	$(COMPOSE) run --rm --build wp-import sh -c "python manage.py migrate --noinput && python manage.py import_wp --dry-run"

test:
	cd main-app && uv run pytest
