# --- Windows/MSYS のパス変換を常に無効化（Linux/Mac でも無害） ---
export MSYS_NO_PATHCONV := 1
export MSYS2_ARG_CONV_EXCL := *

PROJECT ?= texgrep
COMPOSE  = docker compose -f deploy/docker-compose.yml --env-file .env

# 索引のデフォルト。サンプルを使うなら /app/indexer/sample_corpus
INDEX_PROVIDER ?= opensearch
INDEX_INPUT    ?= /app/indexer/sample_corpus

# 起動するサービス（必要ならここで増減）
SERVICES ?= backend frontend opensearch redis

.PHONY: help up down restart ps logs backend-sh frontend-sh shell reindex fmt test bench

help:
	@echo "make up           - build & start $(SERVICES)"
	@echo "make down         - stop & remove"
	@echo "make restart      - restart all services"
	@echo "make ps           - show containers"
	@echo "make logs         - tail logs"
	@echo "make backend-sh   - bash into backend"
	@echo "make frontend-sh  - bash into frontend"
	@echo "make shell        - Django shell_plus"
	@echo "make reindex      - index from $(INDEX_INPUT) (provider=$(INDEX_PROVIDER))"
	@echo "                   e.g. make reindex INDEX_INPUT=/app/data/samples"
	@echo "make fmt/test/bench - code tasks"

up:
	$(COMPOSE) up -d --build $(SERVICES)

down:
	$(COMPOSE) down

restart:
	down up

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f

backend-sh:
	$(COMPOSE) exec backend bash

frontend-sh:
	$(COMPOSE) exec frontend bash

shell:
	$(COMPOSE) exec backend python manage.py shell_plus

reindex:
	$(COMPOSE) exec backend python -m indexer.main --input $(INDEX_INPUT) --provider $(INDEX_PROVIDER)

fmt:
	$(COMPOSE) exec backend ruff format
	$(COMPOSE) exec backend ruff check --fix
	$(COMPOSE) exec frontend npm run lint

test:
	$(COMPOSE) exec backend pytest

bench:
	$(COMPOSE) exec backend python scripts/bench_local.py

# 追加
restart-backend:
	$(COMPOSE) restart backend

api-smoke:
	$(COMPOSE) exec -T backend sh -lc "curl -sS -i -XPOST -H 'Content-Type: application/json' --data '{\"q\":\"\\\\iiint\",\"mode\":\"literal\",\"filters\":{\"source\":\"samples\"},\"size\":5}' http://localhost:8000/api/search || true"

refresh:
	restart reindex

api-health:
	$(COMPOSE) exec -T backend sh -lc "curl -sS -i http://localhost:8000/api/health || true"

api-debug:
	$(COMPOSE) exec -T backend sh -lc "curl -sS -v -XPOST -H 'Content-Type: application/json' --data '{\"q\":\"\\\\iiint\",\"mode\":\"literal\",\"filters\":{\"source\":\"samples\"},\"size\":5}' http://localhost:8000/api/search || true"

api-logs:
	$(COMPOSE) logs backend --tail=200

pi-regex-smoke:
	@$(COMPOSE) exec -T backend sh -lc '\
	  payload=$$(printf "%s" "{\"q\":\"a+\",\"mode\":\"regex\",\"filters\":{\"source\":\"samples\"}}"); \
	  curl -sS -i -XPOST -H "Content-Type: application/json" --data "$$payload" http://localhost:8000/api/search || true \
	'