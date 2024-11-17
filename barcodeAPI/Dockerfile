# Stage 1: Build base
FROM python:3.9-slim-buster as builder-base

# Set build arguments and environment variables
ARG DEBIAN_FRONTEND=noninteractive
ARG PYTHON_ENV=production
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=${DEBIAN_FRONTEND} \
    PYTHON_ENV=${PYTHON_ENV}

# Install build dependencies first in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    zlib1g-dev \
    libjpeg-dev \
    libfreetype6-dev \
    postgresql-client \
    netcat-openbsd \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/*

# Create github-runner user and group
RUN (groupadd -g 1000 github-runner || true) && \
    (useradd -u 1000 -g github-runner -m github-runner || true)

# Copy requirements first to leverage Docker cache
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --upgrade bcrypt psutil

# Copy application files
COPY . .

# Set correct permissions
RUN chmod +x /app/start.sh && \
    chmod +x /app/init-db.sh && \
    chown -R github-runner:github-runner /app && \
    chmod -R 755 /app

# Switch to github-runner user
USER github-runner

# Set up volumes for persistent data
VOLUME ["/app/data", "/app/logs"]

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["./start.sh"]