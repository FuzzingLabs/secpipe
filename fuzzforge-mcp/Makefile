PACKAGE=$(word 1, $(shell uv version))
VERSION=$(word 2, $(shell uv version))

PODMAN?=/usr/bin/podman

ARTIFACTS?=./dist
SOURCES=./src
TESTS=./tests

.PHONY: bandit clean cloc format image mypy pytest ruff version wheel

bandit:
	uv run bandit --recursive $(SOURCES)

clean:
	@find . -type d \( \
		-name '*.egg-info' \
		-o -name '.mypy_cache' \
		-o -name '.pytest_cache' \
		-o -name '.ruff_cache' \
		-o -name '__pycache__' \
	\) -printf 'removing directory %p\n' -exec rm -rf {} +

cloc:
	cloc $(SOURCES) $(TESTS)

format:
	uv run ruff format $(SOURCES) $(TESTS)

image:
	$(PODMAN) build \
		--build-arg PACKAGE=$(PACKAGE) \
		--file ./Dockerfile \
		--no-cache \
		--tag $(PACKAGE):$(VERSION) \
		--volume $(ARTIFACTS):/wheels

mypy:
	uv run mypy $(SOURCES) $(TESTS)

pytest:
	uv run pytest -v $(TESTS)

ruff:
	uv run ruff check --fix $(SOURCES) $(TESTS)

version:
	@echo '$(PACKAGE)@$(VERSION)'

wheel:
	uv build --out-dir $(ARTIFACTS)
