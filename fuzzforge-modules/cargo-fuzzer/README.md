# FuzzForge Modules - FIXME

## Installation

### Python

```shell
# install the package (users)
uv sync
# install the package and all development dependencies (developers)
uv sync --all-extras
```

### Container

```shell
# build the image
make build
# run the container
mkdir -p "${PWD}/data" "${PWD}/data/input" "${PWD}/data/output"
echo '{"settings":{},"resources":[]}' > "${PWD}/data/input/input.json"
podman run --rm \
    --volume "${PWD}/data:/data" \
    '<name>:<version>' 'uv run module'
```

## Usage

```shell
uv run module
```

## Development tools

```shell
# run ruff (formatter)
make format
# run mypy (type checker)
make mypy
# run tests (pytest)
make pytest
# run ruff (linter)
make ruff
```

See the file `Makefile` at the root of this directory for more tools.
