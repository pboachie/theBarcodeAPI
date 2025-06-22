# Use slim Python base image
FROM --platform=linux/amd64 python:3.10-slim-buster AS builder-base

# Set build arguments with defaults
ARG DEBIAN_FRONTEND=noninteractive
ARG PYTHON_ENV=production
ARG VERSION_ARG=0.0.0-dockerfile-default

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=${DEBIAN_FRONTEND}
ENV PYTHON_ENV=${PYTHON_ENV}
ENV APP_VERSION=${VERSION_ARG}

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    netcat-traditional \
    curl \
    gcc \
    g++ \
    make \
    zlib1g-dev \
    libjpeg62-turbo-dev \
    libfreetype6-dev \
    libpng-dev \
    dos2unix \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/* \
    && rm -rf /tmp/*

# Create appuser user and group
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m appuser

# Copy requirements first to leverage Docker cache
COPY --chown=appuser:appuser requirements.txt .

# Upgrade pip and install Python dependencies with retry logic
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --timeout 300 --retries 3 -r requirements.txt && \
    pip install --no-cache-dir --timeout 300 --retries 3 --upgrade bcrypt psutil

# Copy application files
COPY --chown=appuser:appuser . .

# Ensure scripts have correct line endings (LF) and set permissions
RUN dos2unix /app/start.sh && \
    dos2unix /app/init-db.sh && \
    chmod +x /app/start.sh && \
    chmod +x /app/init-db.sh && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app

# Switch to appuser user
USER appuser

# Set up volumes for persistent data
VOLUME ["/app/data", "/app/logs"]

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["./start.sh"]