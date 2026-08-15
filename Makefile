.PHONY: dev dev-api dev-web test lint build reproduce

dev:
	@echo "Run 'make dev-api' and 'make dev-web' in separate terminals."

dev-api:
	uv run --project apps/api --extra science uvicorn exoswarm.api.app:app --reload --port 8000

dev-web:
	pnpm --dir apps/web dev

test:
	uv run --project apps/api --extra science pytest apps/api/tests

lint:
	uv run --project apps/api ruff check apps/api/src apps/api/tests scripts
	pnpm --dir apps/web lint
	pnpm --dir apps/web typecheck

build:
	uv run --project apps/api --extra science python -c "from exoswarm.api.app import app; assert app.title == 'ExoSwarm API'"
	pnpm --dir apps/web build

reproduce:
	uv run --project apps/api --extra science python scripts/reproduce.py
