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
# Under Snap: uses self-contained storage at ~/.fuzzforge/containers/
# Otherwise: uses default podman storage (works on native Linux + macOS)
build-modules:
	@echo "Building FuzzForge module images..."
	@if [ -n "$$SNAP" ]; then \
		echo "Detected Snap environment - using isolated storage at ~/.fuzzforge/containers/"; \
		PODMAN_CMD="podman --root ~/.fuzzforge/containers/storage --runroot ~/.fuzzforge/containers/run"; \
	else \
		echo "Using default podman storage"; \
		PODMAN_CMD="podman"; \
	fi; \
	for module in fuzzforge-modules/*/; do \
		if [ -f "$$module/Dockerfile" ] && \
		   [ "$$module" != "fuzzforge-modules/fuzzforge-modules-sdk/" ] && \
		   [ "$$module" != "fuzzforge-modules/fuzzforge-module-template/" ]; then \
			name=$$(basename $$module); \
			version=$$(grep 'version' "$$module/pyproject.toml" 2>/dev/null | head -1 | sed 's/.*"\(.*\)".*/\1/' || echo "0.1.0"); \
			echo "Building $$name:$$version..."; \
			$$PODMAN_CMD build -t "fuzzforge-$$name:$$version" "$$module" || exit 1; \
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
