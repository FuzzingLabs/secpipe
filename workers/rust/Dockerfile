# FuzzForge Vertical Worker: Rust/Native Security
#
# Pre-installed tools for Rust and native binary security analysis:
# - Rust toolchain (rustc, cargo)
# - AFL++ (fuzzing)
# - cargo-fuzz (Rust fuzzing)
# - gdb (debugging)
# - valgrind (memory analysis)
# - AddressSanitizer/MemorySanitizer support
# - Common reverse engineering tools

FROM rust:1.83-slim-bookworm

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Build essentials
    build-essential \
    cmake \
    git \
    curl \
    wget \
    pkg-config \
    libssl-dev \
    # AFL++ dependencies
    clang \
    llvm \
    # Debugging and analysis tools
    gdb \
    valgrind \
    strace \
    # Binary analysis (binutils includes objdump, readelf, etc.)
    binutils \
    # Network tools
    netcat-openbsd \
    tcpdump \
    # Python for Temporal worker
    python3 \
    python3-pip \
    python3-venv \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Install AFL++
RUN git clone https://github.com/AFLplusplus/AFLplusplus /tmp/aflplusplus && \
    cd /tmp/aflplusplus && \
    make all && \
    make install && \
    cd / && \
    rm -rf /tmp/aflplusplus

# Install Rust toolchain components (nightly required for cargo-fuzz)
RUN rustup install nightly && \
    rustup default nightly && \
    rustup component add rustfmt clippy && \
    rustup target add x86_64-unknown-linux-musl

# Install cargo-fuzz and other Rust security tools
RUN cargo install --locked \
    cargo-fuzz \
    cargo-audit \
    cargo-outdated \
    cargo-tree

# Install Python dependencies for Temporal worker
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Create cache directory for downloaded targets
RUN mkdir -p /cache && chmod 755 /cache

# Copy worker entrypoint
COPY worker.py /app/worker.py

# Add toolbox to Python path (mounted at runtime)
ENV PYTHONPATH="/app:/app/toolbox:${PYTHONPATH}"
ENV PYTHONUNBUFFERED=1

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)"

# Run worker
CMD ["python3", "/app/worker.py"]
