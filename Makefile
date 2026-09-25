.PHONY: install dev db-up db-down migrate seed run test lint fmt

install:
	pip install -e ".[dev]"

# Sobe tudo local em SQLite (sem Docker/Postgres): migra + seed + servidor com reload.
# Acesse http://localhost:8000  (admin@orcamento.com.br / admin123)
DEV_DB ?= sqlite:///./dev.db
dev:
	DATABASE_URL="$(DEV_DB)" alembic upgrade head
	DATABASE_URL="$(DEV_DB)" python -m scripts.seed
	DATABASE_URL="$(DEV_DB)" uvicorn app.main:app --reload

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
