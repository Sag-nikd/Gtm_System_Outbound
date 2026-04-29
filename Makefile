.PHONY: install test lint typecheck db-migrate db-reset demo build clean

install:
	pip install -e ".[dev]"

test:
	pytest -v --cov=src --cov-report=term-missing

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

typecheck:
	mypy --strict src/

db-migrate:
	alembic upgrade head

db-reset:
	@echo "Resetting database..."
	rm -f data/gtm_os.db
	alembic upgrade head
	@echo "Database reset complete."

demo:
	gtm pipeline run --mock

build:
	docker build -t gtm-os .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build *.egg-info
