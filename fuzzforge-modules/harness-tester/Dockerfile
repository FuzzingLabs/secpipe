FROM localhost/fuzzforge-modules-sdk:0.1.0

# Module metadata is now read from pyproject.toml [tool.fuzzforge.module] section

# Install build tools and Rust nightly for compiling and testing fuzz harnesses
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain nightly
ENV PATH="/root/.cargo/bin:${PATH}"

# Install cargo-fuzz for testing harnesses
RUN cargo install cargo-fuzz --locked || true

COPY ./src /app/src
COPY ./pyproject.toml /app/pyproject.toml
COPY ./README.md /app/README.md

# Remove workspace reference since we're using wheels
RUN sed -i '/\[tool\.uv\.sources\]/,/^$/d' /app/pyproject.toml

RUN uv sync --find-links /wheels
