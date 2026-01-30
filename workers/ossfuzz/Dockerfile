# OSS-Fuzz Worker - Generic fuzzing using OSS-Fuzz infrastructure
FROM gcr.io/oss-fuzz-base/base-builder:latest

# Install Python, Docker CLI, and dependencies (use Python 3.8 from base image)
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    git \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python3 -m pip install --upgrade pip

# Install Temporal Python SDK and dependencies
RUN pip3 install --no-cache-dir \
    temporalio==1.5.0 \
    boto3==1.34.50 \
    pyyaml==6.0.1 \
    psutil==5.9.8

# Create necessary directories
RUN mkdir -p /app /cache /corpus /output

# Set environment variables
ENV PYTHONPATH=/app
ENV WORKER_VERTICAL=ossfuzz
ENV MAX_CONCURRENT_ACTIVITIES=2
ENV CACHE_DIR=/cache
ENV CACHE_MAX_SIZE=50GB
ENV CACHE_TTL=30d

# Clone OSS-Fuzz repo (will be cached in /cache by worker)
# This is just to have helper scripts available
RUN git clone --depth=1 https://github.com/google/oss-fuzz.git /opt/oss-fuzz

# Copy worker code
COPY worker.py /app/
COPY activities.py /app/
COPY requirements.txt /app/

WORKDIR /app

# Run worker
CMD ["python3", "worker.py"]
