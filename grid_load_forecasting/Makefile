.PHONY: dev test test-math test-api seed migrate lint fmt docker-up docker-down

dev:
	docker compose up -d postgres && \
	DATABASE_URL=postgresql+asyncpg://grid:grid@localhost:5432/griddb \
	uvicorn app.main:app --reload --port 8000

test:
	pytest tests/test_api.py tests/test_forecaster.py -q --asyncio-mode=auto

test-math:
	pytest tests/test_forecaster.py -v

test-api:
	pytest tests/test_api.py -v

seed:
	python scripts/seed_db.py --nodes 10 --days 90

migrate:
	alembic upgrade head

lint:
	ruff check app/ tests/ scripts/
	black --check app/ tests/ scripts/

fmt:
	ruff check --fix app/ tests/ scripts/
	black app/ tests/ scripts/

docker-up:
	docker compose up -d --wait

docker-down:
	docker compose down -v
