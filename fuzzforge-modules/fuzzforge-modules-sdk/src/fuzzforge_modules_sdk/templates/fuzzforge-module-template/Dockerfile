FROM localhost/fuzzforge-modules-sdk:0.1.0

# Module metadata is read from pyproject.toml [tool.fuzzforge.module] section
# See MODULE_METADATA.md for documentation on configuring metadata

COPY ./src /app/src
COPY ./pyproject.toml /app/pyproject.toml

# Remove workspace reference since we're using wheels
RUN sed -i '/\[tool\.uv\.sources\]/,/^$/d' /app/pyproject.toml

RUN uv sync --find-links /wheels
