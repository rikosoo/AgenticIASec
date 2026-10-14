.PHONY: up down test lint setup

PY ?= python3

setup: ## cria o .env local se não existir
	@test -f .env || (cp .env.example .env && echo ".env criado a partir de .env.example")

up: setup ## sobe db, api e web
	docker compose up --build

down:
	docker compose down

.venv:
	$(PY) -m venv .venv
	.venv/bin/pip install -q -e "apps/api[dev]" -e "packages/detection[dev]"

apps/web/node_modules: apps/web/package-lock.json
	cd apps/web && npm ci

test: .venv apps/web/node_modules ## testes de api, detection e web
	cd apps/api && ../../.venv/bin/pytest -q
	cd packages/detection && ../../.venv/bin/pytest -q
	cd apps/web && npm test

lint: .venv apps/web/node_modules
	.venv/bin/ruff check apps/api packages/detection
	cd apps/web && npm run lint
