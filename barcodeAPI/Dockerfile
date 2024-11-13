# Use slim Python base image
FROM python:3.9-slim-buster

# Set build arguments with defaults
ARG DEBIAN_FRONTEND=noninteractive
ARG PYTHON_ENV=production
ARG APP_USER=github-runner
ARG APP_GROUP=github-runner
ARG APP_UID=1000
ARG APP_GID=1000

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

# Create github-runner user and group if they don't exist
RUN groupadd -g ${APP_GID} ${APP_GROUP} || true && \
    useradd -u ${APP_UID} -g ${APP_GROUP} -s /bin/bash -m ${APP_USER} || true

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --upgrade bcrypt psutil

# Copy the startup script and make it executable
COPY start.sh init-db.sh ./
RUN chmod +x /app/start.sh && \
    chmod +x /app/init-db.sh

# Copy all remaining files
COPY . .

# Set correct permissions
RUN chown -R ${APP_USER}:${APP_GROUP} /app && \
    chmod -R 755 /app

# Switch to github-runner user
USER ${APP_USER}

# Set up volumes for persistent data
VOLUME ["/app/data", "/app/logs"]

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["./start.sh"]