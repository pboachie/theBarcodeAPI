# DockerFile

# Use the official Python image
FROM python:3.9-slim-buster

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    netcat-openbsd \
    curl \
    gcc \
    zlib1g-dev \
    libjpeg-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --upgrade bcrypt psutil

# Copy project files
COPY . .
COPY .env .

# Update alembic.ini
RUN DATABASE_URL=$(grep DATABASE_URL .env | cut -d '=' -f2) && \
    sed -i "s|<POSTGRES_URL>|${DATABASE_URL}|g" alembic.ini

# Set up the startup script
COPY start.sh .
RUN chmod +x start.sh

# Run the startup script
CMD ["./start.sh"]