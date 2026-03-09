ARG BASE_IMAGE=fuzzforge-modules-sdk:0.0.1
FROM ${BASE_IMAGE}

# Module metadata is now read from pyproject.toml [tool.fuzzforge.module] section
# See MODULE_METADATA.md for documentation on configuring metadata

COPY ./src /app/src
COPY ./pyproject.toml /app/pyproject.toml

# Remove workspace reference since we're using wheels
RUN sed -i '/\[tool\.uv\.sources\]/,/^$/d' /app/pyproject.toml

RUN uv sync --find-links /wheels
