FROM python:3.12-slim

LABEL maintainer="Debai Team <debai@example.com>"
LABEL description="Debai AI Agent Management System"
LABEL version="1.0.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    git \
    ca-certificates \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI (for Docker Model Runner integration)
RUN install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    chmod a+r /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install -y --no-install-recommends docker-ce-cli && \
    rm -rf /var/lib/apt/lists/*

# Create debai user and group
RUN groupadd -r debai --gid=1000 && \
    useradd -r -g debai --uid=1000 --home-dir=/home/debai --shell=/bin/bash debai && \
    mkdir -p /home/debai && \
    chown -R debai:debai /home/debai

# Set working directory
WORKDIR /app

# Copy project files
COPY --chown=debai:debai pyproject.toml README.md LICENSE ./
COPY --chown=debai:debai src/ ./src/
COPY --chown=debai:debai data/ ./data/

# Install Python dependencies and Debai
RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir gunicorn uvicorn[standard]

# Create required directories
RUN mkdir -p /etc/debai /var/lib/debai /var/log/debai && \
    chown -R debai:debai /etc/debai /var/lib/debai /var/log/debai

# Copy default configuration
RUN cp data/config/debai.yaml /etc/debai/config.yaml && \
    chown debai:debai /etc/debai/config.yaml

# Switch to debai user
USER debai

# Initialize Debai (creates config directories)
RUN debai init || true

# Expose ports
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=40s \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Default command
CMD ["python", "-m", "uvicorn", "debai.api:app", "--host", "0.0.0.0", "--port", "8000"]
