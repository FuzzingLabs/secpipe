PACKAGE=$(word 1, $(shell uv version))
VERSION=$(word 2, $(shell uv version))

SOURCES=./src

.PHONY: clean format mypy ruff version

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
	uv run ruff format $(SOURCES)

mypy:
	uv run mypy $(SOURCES)

ruff:
	uv run ruff check --fix $(SOURCES)

version:
	@echo '$(PACKAGE)@$(VERSION)'
