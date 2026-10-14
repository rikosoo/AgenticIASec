.PHONY: up down test lint setup ner test-e2e

PY ?= python3

setup: ## cria o .env local se não existir
	@test -f .env || (cp .env.example .env && echo ".env criado a partir de .env.example")

up: setup ## sobe db, api e web
	docker compose up --build

down:
	docker compose down

.venv:
	$(PY) -m venv .venv
	.venv/bin/pip install -q -e "packages/detection[dev]" && .venv/bin/pip install -q -e "apps/api[dev]" -e "packages/adapters/claude_code_hook[dev]"

apps/web/node_modules: apps/web/package-lock.json
	cd apps/web && npm ci

apps/extension/node_modules: apps/extension/package-lock.json
	cd apps/extension && PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm ci

test: .venv apps/web/node_modules apps/extension/node_modules ## testes de api, detection e web
	cd apps/api && ../../.venv/bin/pytest -q
	cd packages/detection && ../../.venv/bin/pytest -q
	cd packages/adapters/claude_code_hook && ../../../.venv/bin/pytest -q
	cd apps/web && npm test
	cd apps/extension && npm test

lint: .venv apps/web/node_modules apps/extension/node_modules
	.venv/bin/ruff check apps/api packages/detection packages/adapters
	cd apps/web && npm run lint
	cd apps/extension && npm run lint

SPACY_MODELS = https://github.com/explosion/spacy-models/releases/download
ner: .venv ## instala Presidio e os modelos spaCy (pt, en) para o NER opcional
	.venv/bin/pip install -q -e "packages/detection[ner]"
	.venv/bin/pip install -q $(SPACY_MODELS)/pt_core_news_sm-3.8.0/pt_core_news_sm-3.8.0-py3-none-any.whl \
		$(SPACY_MODELS)/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

test-e2e: apps/extension/node_modules ## extensão em Chromium real (defina CHROMIUM_PATH)
	cd apps/extension && npm run test:e2e
