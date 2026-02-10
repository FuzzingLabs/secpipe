.PHONY: lint test format check

lint:
	uv run ruff check src tests
	uv run mypy src

test:
	uv run pytest tests

format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

check: lint test
