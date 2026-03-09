ARG BASE_IMAGE=fuzzforge-modules-sdk:0.0.1
FROM ${BASE_IMAGE}

# Module metadata is now read from pyproject.toml [tool.fuzzforge.module] section

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust toolchain
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Rust analysis tools (skipping cargo-geiger as it's heavy)
# RUN cargo install cargo-geiger --locked || true
RUN cargo install cargo-audit --locked || true

COPY ./src /app/src
COPY ./pyproject.toml /app/pyproject.toml

# Remove workspace reference since we're using wheels
RUN sed -i '/\[tool\.uv\.sources\]/,/^$/d' /app/pyproject.toml

RUN uv sync --find-links /wheels
