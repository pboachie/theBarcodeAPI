# Stage 1: Build base
FROM python:3.9-slim-buster as builder-base

# Set build arguments and environment variables
ARG DEBIAN_FRONTEND=noninteractive
ARG PYTHON_ENV=production
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=${DEBIAN_FRONTEND} \
    PYTHON_ENV=${PYTHON_ENV}

# Install build dependencies in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Stage 2: Install Python dependencies
FROM builder-base as builder-deps

WORKDIR /build

# Install runtime dependencies in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    netcat-openbsd \
    curl \
    gcc \
    zlib1g-dev \
    libjpeg-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && groupadd -g 1000 github-runner \
    && useradd -u 1000 -g github-runner -m github-runner

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --upgrade bcrypt psutil

# Stage 3: Final runtime
FROM python:3.9-slim-buster

# Runtime environment setup
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder-deps /usr/local/lib/python3.9/site-packages/ /usr/local/lib/python3.9/site-packages/

# Copy application files
COPY . .

# Set permissions
RUN chown -R github-runner:github-runner /app \
    && chmod -R 755 /app \
    && chmod +x /app/start.sh /app/init-db.sh

# Switch to non-root user
USER github-runner

# Set up volumes and expose port
VOLUME ["/app/data", "/app/logs"]
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["./start.sh"]