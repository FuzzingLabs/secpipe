PACKAGE=$(word 1, $(shell uv version))
VERSION=$(word 2, $(shell uv version))

PODMAN?=/usr/bin/podman

SOURCES=./src
TESTS=./tests

.PHONY: bandit build clean format mypy pytest ruff version

bandit:
	uv run bandit --recursive $(SOURCES)

build:
	$(PODMAN) build --file ./Dockerfile --no-cache --tag $(PACKAGE):$(VERSION)

save: build
	$(PODMAN) save --format oci-archive --output /tmp/$(PACKAGE)-$(VERSION).oci $(PACKAGE):$(VERSION)

clean:
	@find . -type d \( \
		-name '*.egg-info' \
		-o -name '.mypy_cache' \
		-o -name '.pytest_cache' \
		-o -name '.ruff_cache' \
		-o -name '__pycache__' \
	\) -printf 'removing directory %p\n' -exec rm -rf {} +

cloc:
	cloc $(SOURCES)

format:
	uv run ruff format $(SOURCES) $(TESTS)

mypy:
	uv run mypy $(SOURCES)

pytest:
	uv run pytest $(TESTS)

ruff:
	uv run ruff check --fix $(SOURCES) $(TESTS)

version:
	@echo '$(PACKAGE)@$(VERSION)'
