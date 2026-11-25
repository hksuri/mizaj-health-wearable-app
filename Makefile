.PHONY: install lint test synth dev api web eval eval-run eval-report

export PATH := $(HOME)/.local/bin:$(PATH)

install:
	uv sync --all-packages --group dev
	cd apps/web && pnpm install

lint:
	uv run ruff check apps packages tests scripts
	uv run ruff format --check apps packages tests scripts
	uv run pyright
	cd apps/web && pnpm exec tsc --noEmit
	cd apps/web && pnpm exec eslint . --max-warnings 0

test:
	uv run pytest -q

synth:
	uv run python scripts/make_synthetic_data.py
	@echo "synth target: implement gold build in phase 1.2"

dev:
	@echo "Start api and web with: make api (terminal 1) and make web (terminal 2)"
	@echo "Or: docker compose up"

api:
	uv run uvicorn mizaj.main:app --app-dir apps/api/src --host 127.0.0.1 --port 8000 --reload

web:
	cd apps/web && pnpm dev

eval:
	@echo "eval targets land in phase 2/3"

eval-run:
	@echo "TODO: phase 2"

eval-report:
	@echo "TODO: phase 3"
