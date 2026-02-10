.PHONY: help install sync format lint typecheck test build-modules clean

SHELL := /bin/bash

# Default target
help:
	@echo "FuzzForge OSS Development Commands"
	@echo ""
	@echo "  make install       - Install all dependencies"
	@echo "  make sync          - Sync shared packages from upstream"
	@echo "  make format        - Format code with ruff"
	@echo "  make lint          - Lint code with ruff"
	@echo "  make typecheck     - Type check with mypy"
	@echo "  make test          - Run all tests"
	@echo "  make build-modules - Build all module container images"
	@echo "  make clean         - Clean build artifacts"
	@echo ""

# Install all dependencies
install:
	uv sync

# Sync shared packages from upstream fuzzforge-core
sync:
	@if [ -z "$(UPSTREAM)" ]; then \
		echo "Usage: make sync UPSTREAM=/path/to/fuzzforge-core"; \
		exit 1; \
	fi
	./scripts/sync-upstream.sh $(UPSTREAM)

# Format all packages
format:
	@for pkg in packages/fuzzforge-*/; do \
		if [ -f "$$pkg/pyproject.toml" ]; then \
			echo "Formatting $$pkg..."; \
			cd "$$pkg" && uv run ruff format . && cd -; \
		fi \
	done

# Lint all packages
lint:
	@for pkg in packages/fuzzforge-*/; do \
		if [ -f "$$pkg/pyproject.toml" ]; then \
			echo "Linting $$pkg..."; \
			cd "$$pkg" && uv run ruff check . && cd -; \
		fi \
	done

# Type check all packages
typecheck:
	@for pkg in packages/fuzzforge-*/; do \
		if [ -f "$$pkg/pyproject.toml" ] && [ -f "$$pkg/mypy.ini" ]; then \
			echo "Type checking $$pkg..."; \
			cd "$$pkg" && uv run mypy . && cd -; \
		fi \
	done

# Run all tests
test:
	@for pkg in packages/fuzzforge-*/; do \
		if [ -f "$$pkg/pytest.ini" ]; then \
			echo "Testing $$pkg..."; \
			cd "$$pkg" && uv run pytest && cd -; \
		fi \
	done

# Build all module container images
# Uses Docker by default, or Podman if FUZZFORGE_ENGINE=podman
build-modules:
	@echo "Building FuzzForge module images..."
	@if [ "$$FUZZFORGE_ENGINE" = "podman" ]; then \
		if [ -n "$$SNAP" ]; then \
			echo "Using Podman with isolated storage (Snap detected)"; \
			CONTAINER_CMD="podman --root ~/.fuzzforge/containers/storage --runroot ~/.fuzzforge/containers/run"; \
		else \
			echo "Using Podman"; \
			CONTAINER_CMD="podman"; \
		fi; \
	else \
		echo "Using Docker"; \
		CONTAINER_CMD="docker"; \
	fi; \
	for module in fuzzforge-modules/*/; do \
		if [ -f "$$module/Dockerfile" ] && \
		   [ "$$module" != "fuzzforge-modules/fuzzforge-modules-sdk/" ] && \
		   [ "$$module" != "fuzzforge-modules/fuzzforge-module-template/" ]; then \
			name=$$(basename $$module); \
			version=$$(grep 'version' "$$module/pyproject.toml" 2>/dev/null | head -1 | sed 's/.*"\(.*\\)".*/\\1/' || echo "0.1.0"); \
			echo "Building $$name:$$version..."; \
			$$CONTAINER_CMD build -t "fuzzforge-$$name:$$version" "$$module" || exit 1; \
		fi \
	done
	@echo ""
	@echo "✓ All modules built successfully!"

# Clean build artifacts
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
