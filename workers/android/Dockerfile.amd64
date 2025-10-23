# FuzzForge Vertical Worker: Android Security
#
# Pre-installed tools for Android security analysis:
# - Android SDK (adb, aapt)
# - apktool (APK decompilation)
# - jadx (Dex to Java decompiler)
# - Frida (dynamic instrumentation)
# - androguard (Python APK analysis)
# - MobSF dependencies
#
# Note: Uses amd64 platform for compatibility with Android 32-bit tools

FROM --platform=linux/amd64 python:3.11-slim-bookworm

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Build essentials
    build-essential \
    git \
    curl \
    wget \
    unzip \
    # Java (required for Android tools)
    openjdk-17-jdk \
    # Android tools dependencies (32-bit libraries for emulated amd64)
    lib32stdc++6 \
    lib32z1 \
    # Frida dependencies
    libc6-dev \
    # XML/Binary analysis
    libxml2-dev \
    libxslt-dev \
    # Network tools
    netcat-openbsd \
    tcpdump \
    # MobSF dependencies
    xfonts-75dpi \
    xfonts-base \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Install wkhtmltopdf (required for MobSF PDF reports)
RUN wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb && \
    apt-get update && \
    apt-get install -y ./wkhtmltox_0.12.6.1-3.bookworm_amd64.deb && \
    rm wkhtmltox_0.12.6.1-3.bookworm_amd64.deb && \
    rm -rf /var/lib/apt/lists/*

# Install Android SDK Command Line Tools
ENV ANDROID_HOME=/opt/android-sdk
ENV PATH="${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:${PATH}"

RUN mkdir -p ${ANDROID_HOME}/cmdline-tools && \
    cd ${ANDROID_HOME}/cmdline-tools && \
    wget -q https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip && \
    unzip -q commandlinetools-linux-9477386_latest.zip && \
    mv cmdline-tools latest && \
    rm commandlinetools-linux-9477386_latest.zip && \
    # Accept licenses
    yes | ${ANDROID_HOME}/cmdline-tools/latest/bin/sdkmanager --licenses && \
    # Install platform tools (adb, fastboot)
    ${ANDROID_HOME}/cmdline-tools/latest/bin/sdkmanager "platform-tools" "build-tools;33.0.0"

# Install apktool
RUN wget -q https://raw.githubusercontent.com/iBotPeaches/Apktool/master/scripts/linux/apktool -O /usr/local/bin/apktool && \
    wget -q https://bitbucket.org/iBotPeaches/apktool/downloads/apktool_2.9.3.jar -O /usr/local/bin/apktool.jar && \
    chmod +x /usr/local/bin/apktool

# Install jadx (Dex to Java decompiler)
RUN wget -q https://github.com/skylot/jadx/releases/download/v1.4.7/jadx-1.4.7.zip -O /tmp/jadx.zip && \
    unzip -q /tmp/jadx.zip -d /opt/jadx && \
    ln -s /opt/jadx/bin/jadx /usr/local/bin/jadx && \
    ln -s /opt/jadx/bin/jadx-gui /usr/local/bin/jadx-gui && \
    rm /tmp/jadx.zip

# Install Python dependencies for Android security tools
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Install androguard (Python APK analysis framework)
RUN pip3 install --no-cache-dir androguard pyaxmlparser

# Install Frida
RUN pip3 install --no-cache-dir frida-tools frida

# Install OpenGrep/Semgrep (expose as opengrep command)
RUN pip3 install --no-cache-dir semgrep==1.45.0 && \
    ln -sf /usr/local/bin/semgrep /usr/local/bin/opengrep

# Install MobSF (Mobile Security Framework)
RUN git clone --depth 1 --branch v3.9.7 https://github.com/MobSF/Mobile-Security-Framework-MobSF.git /app/mobsf && \
    cd /app/mobsf && \
    ./setup.sh

# Install aiohttp for async HTTP requests (used by MobSF scanner module)
RUN pip3 install --no-cache-dir aiohttp

# Create cache directory
RUN mkdir -p /cache && chmod 755 /cache

# Copy worker entrypoint (generic, works for all verticals)
COPY worker.py /app/worker.py

# Create startup script that runs MobSF in background and then starts worker
RUN echo '#!/bin/bash\n\
# Start MobSF server in background with sync workers (avoid Rosetta syscall issues)\n\
echo "Starting MobSF server in background..."\n\
cd /app/mobsf && python3 -m poetry run gunicorn -b 127.0.0.1:8877 \\\n\
    mobsf.MobSF.wsgi:application \\\n\
    --worker-class=sync \\\n\
    --workers=2 \\\n\
    --timeout=3600 \\\n\
    --log-level=error \\\n\
    > /tmp/mobsf.log 2>&1 &\n\
MOBSF_PID=$!\n\
echo "MobSF started with PID: $MOBSF_PID"\n\
\n\
# Wait for MobSF to initialize\n\
sleep 10\n\
\n\
# Generate and store MobSF API key\n\
if [ -f /root/.MobSF/secret ]; then\n\
    SECRET=$(cat /root/.MobSF/secret)\n\
    export MOBSF_API_KEY=$(echo -n "$SECRET" | sha256sum | cut -d " " -f1)\n\
    echo "MobSF API key: $MOBSF_API_KEY"\n\
fi\n\
\n\
# Start worker\n\
echo "Starting Temporal worker..."\n\
exec python3 /app/worker.py\n\
' > /app/start.sh && chmod +x /app/start.sh

# Add toolbox to Python path (mounted at runtime)
ENV PYTHONPATH="/app:/app/toolbox:${PYTHONPATH}"
ENV PYTHONUNBUFFERED=1
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV MOBSF_PORT=8877

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD python3 -c "import sys; sys.exit(0)"

# Run startup script (starts MobSF + worker)
CMD ["/app/start.sh"]
