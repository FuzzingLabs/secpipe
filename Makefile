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
		BASE_IMG_PREFIX="localhost/"; \
	else \
		echo "Using Docker"; \
		CONTAINER_CMD="docker"; \
		BASE_IMG_PREFIX=""; \
	fi; \
	SDK_DIR="fuzzforge-modules/fuzzforge-modules-sdk/"; \
	SDK_VERSION=$$(grep -m1 '^version\s*=' "$${SDK_DIR}pyproject.toml" 2>/dev/null | sed 's/^version\s*=\s*//;s/"//g;s/\s*$$//' ); \
	[ -n "$$SDK_VERSION" ] || SDK_VERSION="0.0.1"; \
	echo "Building wheels for fuzzforge-modules-sdk..."; \
	(cd "$$SDK_DIR" && uv build --wheel --out-dir .wheels) || exit 1; \
	SDK_IMG="$${BASE_IMG_PREFIX}fuzzforge-modules-sdk:$$SDK_VERSION"; \
	echo "Building $$SDK_IMG..."; \
	$$CONTAINER_CMD build -t "$$SDK_IMG" "$$SDK_DIR" || exit 1; \
	for module in fuzzforge-modules/*/; do \
		if [ "$$module" = "$$SDK_DIR" ] || [ "$$module" = "fuzzforge-modules/fuzzforge-module-template/" ] || [ ! -f "$$module/Dockerfile" ]; then continue; fi; \
		name=$$(basename $$module); \
		version=$$(grep -m1 '^version\s*=' "$$module/pyproject.toml" 2>/dev/null | sed 's/^version\s*=\s*//;s/"//g;s/\s*$$//'); \
		[ -n "$$version" ] || version="0.0.1"; \
		case $$name in \
			fuzzforge-*) tag="$$name:$$version" ;; \
			*) tag="fuzzforge-$$name:$$version" ;; \
		esac; \
		echo "Building $$tag..."; \
		$$CONTAINER_CMD build \
			--build-arg BASE_IMAGE="$$SDK_IMG" \
			-t "$$tag" "$$module" || exit 1; \
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
