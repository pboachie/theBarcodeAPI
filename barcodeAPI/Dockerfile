# Dockerfile
FROM python:3.9-slim-buster

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

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
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --upgrade bcrypt psutil

# Copy init.db.sh and set permissions
COPY init-db.sh ./
RUN chmod +x init-db.sh

# Copy scripts and set permissions
COPY start.sh scripts/* ./
RUN chmod +x start.sh && \
    if [ -d "scripts" ]; then chmod +x scripts/*.sh; fi

# Copy project files
COPY . .
COPY .env .

# Update alembic.ini
RUN DATABASE_URL=$(grep DATABASE_URL .env | cut -d '=' -f2) && \
    sed -i "s|<POSTGRES_URL>|${DATABASE_URL}|g" alembic.ini

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["./start.sh"]