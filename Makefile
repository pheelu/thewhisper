.DEFAULT_GOAL := help
.PHONY: help up down logs backend frontend migrate revision install fmt lint test

help: ## Mostra questo aiuto
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Avvia Postgres + MinIO
	docker compose up -d

down: ## Ferma l'infrastruttura
	docker compose down

logs: ## Log dell'infrastruttura
	docker compose logs -f

install: ## Installa dipendenze backend e frontend
	cd backend && uv sync
	cd frontend && npm install

backend: ## Avvia il backend in dev (reload)
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend: ## Avvia il frontend in dev
	cd frontend && npm run dev

migrate: ## Applica le migrazioni DB
	cd backend && uv run alembic upgrade head

revision: ## Crea una migrazione autogenerata: make revision m="messaggio"
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

fmt: ## Formatta il codice backend
	cd backend && uv run ruff format . && uv run ruff check --fix .

lint: ## Lint backend
	cd backend && uv run ruff check . && uv run mypy app

test: ## Esegue i test backend
	cd backend && uv run pytest
