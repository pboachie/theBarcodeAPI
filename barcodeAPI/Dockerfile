# Use slim Python base image
FROM --platform=linux/amd64 python:3.9-slim-buster as builder-base

# Set build arguments with defaults
ARG DEBIAN_FRONTEND=noninteractive
ARG PYTHON_ENV=production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=${DEBIAN_FRONTEND} \
    PYTHON_ENV=${PYTHON_ENV}

# Set work directory
WORKDIR /app

# Install system dependencies - grouped to reduce layers
RUN apt-get update && apt-get install -y \
    postgresql-client \
    netcat-openbsd \
    curl \
    gcc \
    zlib1g-dev \
    libjpeg-dev \
    libfreetype6-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/*

# Copy and set up entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create logs directory with proper permissions
RUN mkdir -p /app/logs && chmod 777 /app/logs

# Create a non-root user for production
RUN if [ "$PYTHON_ENV" = "production" ]; then \
        groupadd -r appuser && useradd -r -g appuser appuser && \
        chown -R appuser:appuser /app; \
    fi

# Switch to non-root user in production
USER ${PYTHON_ENV=production && echo "appuser" || echo "root"}
# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --upgrade bcrypt psutil

# Copy application files
COPY . .

# Set correct permissions
RUN chmod +x /app/start.sh && \
    chmod +x /app/init-db.sh && \
    chmod -R 755 /app

# Set up volumes for persistent data
VOLUME ["/app/data", "/app/logs"]

# Expose port
EXPOSE 8000

# Health check - check both HTTP and WebSocket endpoints
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health && python3 check_websocket_health.py || exit 1

# Set entrypoint and command
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--loop", "uvloop", "--http", "httptools"]

