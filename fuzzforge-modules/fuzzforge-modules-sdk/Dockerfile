# FuzzForge Modules SDK - Base image for all modules
#
# This image provides:
# - Python 3.14 with uv package manager
# - Pre-built wheels for common dependencies
# - Standard module directory structure

FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

# Install system dependencies commonly needed by modules
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set up application directory structure
WORKDIR /app

# Create FuzzForge standard directories
RUN mkdir -p /fuzzforge/input /fuzzforge/output

# Copy wheels directory (built by parent Makefile)
COPY .wheels /wheels

# Set up uv for the container
ENV UV_SYSTEM_PYTHON=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Default entrypoint - modules override this
ENTRYPOINT ["uv", "run", "module"]
