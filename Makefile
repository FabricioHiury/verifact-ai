UV := $(shell command -v uv 2>/dev/null || echo .tools/bin/uv)
PY := .venv/bin/python
COMPOSE := $(shell if docker compose version >/dev/null 2>&1; then echo 'docker compose'; else echo docker-compose; fi)
export UV_CACHE_DIR := $(CURDIR)/.uv-cache
export UV_PYTHON_INSTALL_DIR := $(CURDIR)/.tools/python
.PHONY: setup setup-media setup-social minio-build infra-up infra-down dev dev-web dev-api dev-worker migrate lint format typecheck test test-e2e evaluate health contracts models-pull
setup:
	python3 scripts/init_env.py
	@test -x $(UV) || (python3 -m venv .tools && .tools/bin/pip install uv==0.13.5)
	$(UV) sync --frozen
	pnpm install --frozen-lockfile
setup-media:
	$(UV) sync --frozen --extra mlx --extra diarization
minio-build:
	MINIO_IMAGE=verifact-minio:source-20250907 $(COMPOSE) build minio
setup-social:
	mkdir -p data/downloads
	$(COMPOSE) --profile media build download-proxy downloader
infra-up:
	$(COMPOSE) up -d --wait
models-pull:
	$(PY) scripts/pull_models.py
infra-down:
	$(COMPOSE) down
migrate:
	.venv/bin/alembic -c apps/api/alembic.ini upgrade head
dev:
	$(PY) scripts/dev.py
dev-web:
	$(PY) scripts/dev.py web
dev-api:
	$(PY) scripts/dev.py api
dev-worker:
	$(PY) scripts/dev.py worker
lint:
	.venv/bin/ruff check apps scripts tests infrastructure/docker/downloader
	pnpm lint
format:
	.venv/bin/ruff check --fix apps scripts tests infrastructure/docker/downloader
	.venv/bin/ruff format apps scripts tests infrastructure/docker/downloader
	pnpm format
typecheck:
	.venv/bin/mypy
	pnpm typecheck
test:
	.venv/bin/pytest -m 'not live'
	pnpm test
test-e2e:
	pnpm test:e2e
evaluate:
	.venv/bin/pytest tests/evaluations -m 'not live'
health:
	$(PY) scripts/health.py
contracts:
	$(PY) scripts/export_openapi.py
	pnpm exec openapi-typescript packages/contracts/openapi.json -o packages/contracts/schema.d.ts
