PROJECT?=texgrep
COMPOSE=docker compose -f deploy/docker-compose.yml --env-file .env

up:
$(COMPOSE) up -d --build

down:
$(COMPOSE) down

logs:
$(COMPOSE) logs -f

web:
$(COMPOSE) exec backend python manage.py runserver 0.0.0.0:8000

reindex:
$(COMPOSE) exec backend python manage.py tex_reindex --source samples --limit 100

shell:
$(COMPOSE) exec backend python manage.py shell_plus

fmt:
$(COMPOSE) exec backend ruff format
$(COMPOSE) exec backend ruff check --fix
$(COMPOSE) exec frontend npm run lint

test:
$(COMPOSE) exec backend pytest

bench:
$(COMPOSE) exec backend python scripts/bench_local.py

.PHONY: up down logs web reindex shell fmt test bench
