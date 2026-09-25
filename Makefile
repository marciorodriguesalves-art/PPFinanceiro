.PHONY: install dev db-up db-down migrate seed run test lint fmt

install:
	pip install -e ".[dev]"

# Sobe tudo local em SQLite (sem Docker/Postgres): migra + seed + servidor com reload.
# Porta 8137 por padrão (a 8000 costuma estar ocupada por outro projeto).
# Acesse http://localhost:8137  (admin@orcamento.com.br / admin123)
# Trocar a porta:  make dev PORT=9000
DEV_DB ?= sqlite:///./dev.db
PORT ?= 8137
dev:
	DATABASE_URL="$(DEV_DB)" alembic upgrade head
	DATABASE_URL="$(DEV_DB)" python -m scripts.seed
	DATABASE_URL="$(DEV_DB)" uvicorn app.main:app --reload --port $(PORT)

db-up:
	docker compose up -d db

db-down:
	docker compose down

migrate:
	alembic upgrade head

seed:
	python -m scripts.seed

run:
	uvicorn app.main:app --reload

test:
	pytest

lint:
	ruff check .

fmt:
	ruff check --fix . && ruff format .
