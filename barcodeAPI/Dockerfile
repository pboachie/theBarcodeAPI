# Stage 1: Build stage
FROM python:3.9-slim-buster as builder

# Build args
ARG DEBIAN_FRONTEND=noninteractive
ARG PYTHON_ENV=production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=${DEBIAN_FRONTEND} \
    PYTHON_ENV=${PYTHON_ENV}

# Set work directory
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir bcrypt psutil

# Stage 2: Final stage
FROM python:3.9-slim-buster

# Runtime args
ARG DEBIAN_FRONTEND=noninteractive
ARG PYTHON_ENV=production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=${DEBIAN_FRONTEND} \
    PYTHON_ENV=${PYTHON_ENV}

# Set work directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    netcat-openbsd \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/*

# Create github-runner user and group
RUN (groupadd -g 1000 github-runner || true) && \
    (useradd -u 1000 -g github-runner -m github-runner || true)

# Copy installed dependencies from builder
COPY --from=builder /usr/local/lib/python3.9/site-packages/ /usr/local/lib/python3.9/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

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