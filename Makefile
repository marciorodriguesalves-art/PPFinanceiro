.PHONY: install dev db-up db-down migrate seed run test lint fmt

install:
	pip install -e ".[dev]"

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
