.PHONY: help install sync format lint typecheck test build-hub-images clean

SHELL := /bin/bash

# Default target
help:
	@echo "SecPipe AI Development Commands"
	@echo ""
	@echo "  make install       - Install all dependencies"
	@echo "  make sync          - Sync shared packages from upstream"
	@echo "  make format        - Format code with ruff"
	@echo "  make lint          - Lint code with ruff"
	@echo "  make typecheck     - Type check with mypy"
	@echo "  make test          - Run all tests"
	@echo "  make build-hub-images  - Build all mcp-security-hub images"
	@echo "  make clean             - Clean build artifacts"
	@echo ""

# Install all dependencies
install:
	uv sync

# Sync shared packages from upstream secpipe-core
sync:
	@if [ -z "$(UPSTREAM)" ]; then \
		echo "Usage: make sync UPSTREAM=/path/to/secpipe-core"; \
		exit 1; \
	fi
	./scripts/sync-upstream.sh $(UPSTREAM)

# Format all packages
format:
	@for pkg in packages/secpipe-*/; do \
		if [ -f "$$pkg/pyproject.toml" ]; then \
			echo "Formatting $$pkg..."; \
			cd "$$pkg" && uv run ruff format . && cd -; \
		fi \
	done

# Lint all packages
lint:
	@for pkg in packages/secpipe-*/; do \
		if [ -f "$$pkg/pyproject.toml" ]; then \
			echo "Linting $$pkg..."; \
			cd "$$pkg" && uv run ruff check . && cd -; \
		fi \
	done

# Type check all packages
typecheck:
	@for pkg in packages/secpipe-*/; do \
		if [ -f "$$pkg/pyproject.toml" ] && [ -f "$$pkg/mypy.ini" ]; then \
			echo "Type checking $$pkg..."; \
			cd "$$pkg" && uv run mypy . && cd -; \
		fi \
	done

# Run all tests
test:
	@for pkg in packages/secpipe-*/; do \
		if [ -f "$$pkg/pytest.ini" ]; then \
			echo "Testing $$pkg..."; \
			cd "$$pkg" && uv run pytest && cd -; \
		fi \
	done

# Build all mcp-security-hub images for the firmware analysis pipeline
build-hub-images:
	@bash scripts/build-hub-images.sh

# Clean build artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
