.PHONY: help install sync format lint typecheck test build-modules build-modules-sdk build-modules-images clean

SHELL := /bin/bash

# Container image configuration
SDK_DIR         := fuzzforge-modules/fuzzforge-modules-sdk/
MODULE_TEMPLATE := fuzzforge-modules/fuzzforge-module-template/
SDK_VERSION     := $(shell scripts/pyproject-version.sh $(SDK_DIR)pyproject.toml)
BASE_IMG_PREFIX := $(if $(filter podman,$(FUZZFORGE_ENGINE)),localhost/,)
SDK_IMG         := $(BASE_IMG_PREFIX)fuzzforge-modules-sdk:$(SDK_VERSION)

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
	@echo "  make build-modules-sdk - Build the SDK base image"
	@echo "  make build-modules-images - Build all module images (requires SDK image)"
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

# Build all module container images (SDK first, then modules)
# Uses Docker by default, or Podman if FUZZFORGE_ENGINE=podman
build-modules: build-modules-sdk build-modules-images
	@echo ""
	@echo "✓ All modules built successfully!"

# Build the SDK base image (also builds its Python wheel)
build-modules-sdk:
	@source scripts/container-env.sh; \
	echo "Building wheels for fuzzforge-modules-sdk..."; \
	(cd "$(SDK_DIR)" && uv build --wheel --out-dir .wheels) || exit 1; \
	echo "Building $(SDK_IMG)..."; \
	$$CONTAINER_CMD build -t "$(SDK_IMG)" "$(SDK_DIR)" || exit 1

# Build all module images (requires SDK image to exist)
build-modules-images:
	@source scripts/container-env.sh; \
	for module in fuzzforge-modules/*/; do \
		[ "$$module" = "$(SDK_DIR)" ] && continue; \
		[ "$$module" = "$(MODULE_TEMPLATE)" ] && continue; \
		[ -f "$$module/Dockerfile" ] || continue; \
		name=$$(basename "$$module"); \
		version=$$(scripts/pyproject-version.sh "$$module/pyproject.toml"); \
		case $$name in \
			fuzzforge-*) tag="$$name:$$version" ;; \
			*) tag="fuzzforge-$$name:$$version" ;; \
		esac; \
		echo "Building $$tag..."; \
		$$CONTAINER_CMD build --build-arg BASE_IMAGE="$(SDK_IMG)" -t "$$tag" "$$module" || exit 1; \
	done

# Clean build artifacts
clean:
	@for dir in __pycache__ .pytest_cache .mypy_cache .ruff_cache "*.egg-info"; do \
		find . -type d -name "$$dir" -exec rm -rf {} + 2>/dev/null || true; \
	done
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
