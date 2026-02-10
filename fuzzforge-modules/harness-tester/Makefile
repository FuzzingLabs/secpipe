.PHONY: help build clean format lint test

help:
	@echo "Available targets:"
	@echo "  build  - Build Docker image"
	@echo "  clean  - Remove build artifacts"
	@echo "  format - Format code with ruff"
	@echo "  lint   - Lint code with ruff and mypy"
	@echo "  test   - Run tests"

build:
	docker build -t fuzzforge-harness-tester:0.1.0 .

clean:
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +

format:
	uv run ruff format ./src ./tests

lint:
	uv run ruff check ./src ./tests
	uv run mypy ./src

test:
	uv run pytest tests/ -v
