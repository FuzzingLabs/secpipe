# FuzzForge Vertical Worker: Secret Detection
#
# Pre-installed tools for secret detection:
# - Gitleaks v8.18.0
# - TruffleHog v3.63.2
# - Temporal worker

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Build essentials
    build-essential \
    # Development tools
    git \
    curl \
    wget \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Install Gitleaks v8.18.0
RUN wget -q https://github.com/gitleaks/gitleaks/releases/download/v8.18.0/gitleaks_8.18.0_linux_x64.tar.gz && \
    tar -xzf gitleaks_8.18.0_linux_x64.tar.gz && \
    mv gitleaks /usr/local/bin/ && \
    chmod +x /usr/local/bin/gitleaks && \
    rm gitleaks_8.18.0_linux_x64.tar.gz

# Install TruffleHog v3.63.2
RUN wget -q https://github.com/trufflesecurity/trufflehog/releases/download/v3.63.2/trufflehog_3.63.2_linux_amd64.tar.gz && \
    tar -xzf trufflehog_3.63.2_linux_amd64.tar.gz && \
    mv trufflehog /usr/local/bin/ && \
    chmod +x /usr/local/bin/trufflehog && \
    rm trufflehog_3.63.2_linux_amd64.tar.gz

# Verify installations
RUN gitleaks version && trufflehog --version

# Install Python dependencies for Temporal worker
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Create cache directory for downloaded targets
RUN mkdir -p /cache && chmod 755 /cache

# Copy worker entrypoint
COPY worker.py /app/worker.py

# Add toolbox and AI module to Python path (mounted at runtime)
ENV PYTHONPATH="/app:/app/toolbox:/app/ai_src:${PYTHONPATH}"
ENV PYTHONUNBUFFERED=1

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)"

# Run worker
CMD ["python3", "/app/worker.py"]
