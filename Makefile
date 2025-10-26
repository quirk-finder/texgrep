PROJECT?=texgrep
COMPOSE=docker compose -f deploy/docker-compose.yml --env-file .env
INDEX_PROVIDER?=opensearch

up:
$(COMPOSE) up -d --build

down:
$(COMPOSE) down

logs:
$(COMPOSE) logs -f

web:
$(COMPOSE) exec backend python manage.py runserver 0.0.0.0:8000

reindex:
    DJANGO_SETTINGS_MODULE=texgrep.settings python -m indexer.main --input data/samples --provider $(INDEX_PROVIDER)

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
