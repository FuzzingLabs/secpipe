PACKAGE=$(word 1, $(shell uv version))
VERSION=$(word 2, $(shell uv version))

ARTIFACTS?=./dist

SOURCES=./src
TESTS=./tests

.PHONY: bandit clean format mypy pytest ruff version wheel

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

wheel:
	uv build --out-dir $(ARTIFACTS)
