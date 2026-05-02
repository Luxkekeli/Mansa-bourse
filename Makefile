# MANSA — common commands
# Usage: make <target>

.PHONY: help install install-dev test test-unit test-e2e lint format security \
        seed dump-data run prod build clean zip

help:
	@echo "MANSA targets:"
	@echo "  install       Install Python deps (production)"
	@echo "  install-dev   Install Python + dev deps + npm"
	@echo "  test          pytest unit + integration"
	@echo "  test-e2e      Playwright e2e tests (requires running stack)"
	@echo "  lint          ruff check"
	@echo "  format        ruff format + ruff check --fix"
	@echo "  security      bandit + pip-audit"
	@echo "  seed          Seed DB tickers/dividends/fundamentals from app.html"
	@echo "  dump-data     Generate frontend/src/data.ts from DB"
	@echo "  run           Dev server (Flask, port 5000)"
	@echo "  prod          Production server (gunicorn)"
	@echo "  build         Vite frontend build (P1-1, scaffold only)"
	@echo "  clean         Remove caches and build artifacts"
	@echo "  zip           Build the latest release ZIP"

install:
	pip install -r server/requirements.txt

install-dev: install
	pip install -r server/requirements-dev.txt
	@command -v npm >/dev/null 2>&1 && npm install || echo "npm not found — skipping frontend deps"

test:
	python -m pytest tests/unit tests/integration -q

test-unit:
	python -m pytest tests/unit -q

test-e2e:
	npx playwright test

lint:
	python -m ruff check server/ tests/ scripts/

format:
	python -m ruff check --fix server/ tests/ scripts/

security:
	python -m bandit -c pyproject.toml -r server/ scripts/ -ll
	@command -v pip-audit >/dev/null 2>&1 && pip-audit -r server/requirements.txt || echo "pip-audit not installed"

seed:
	python scripts/seed_from_app_html.py

dump-data:
	python scripts/dump_tickers_to_data_ts.py

run:
	FLASK_ENV=development python -m flask --app server.api_server run --port 5000

prod:
	gunicorn -w 4 -b 127.0.0.1:5000 server.api_server:app

build:
	npm run build

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	rm -rf frontend/dist test-results playwright-report

zip:
	python scripts/build_session5_zip.py
