# theBarcodeAPI

Welcome to theBarcodeAPI - Your go-to solution for barcode generation and processing!

## Overview

theBarcodeAPI is a powerful and flexible showcase website designed to demonstrate various barcode-related operations. Whether you need to generate barcodes, decode existing ones, or integrate barcode functionality into your applications, theBarcodeAPI has got you covered.

## Features

- Generate multiple barcode formats (e.g., QR, Code128, EAN-13)
- Decode barcodes from images
- Customize barcode appearance and size
- High-performance and scalable architecture
- Easy-to-use RESTful API

## Project Structure

The project is organized into several key components:

- **app/**: Contains the main application code, including API endpoints, database models, and utility functions.
  - **api/**: Houses the FastAPI routes for barcode generation, health checks, token management, and usage statistics.
  - **barcode_generator.py**: Module responsible for generating barcodes in various formats.
  - **config.py**: Configuration settings for the application.
  - **database.py**: Database connection and session management.
  - **models.py**: SQLAlchemy models representing database tables.
- **tests/**: Contains unit and integration tests for the application.
- **alembic/**: Manages database migrations using Alembic.
- **Dockerfile**: Defines the Docker image for the application.
- **docker-compose.yml**: Configures Docker services for local development.
- **requirements.txt**: Lists Python dependencies.
- **start.sh**: Startup script to initialize and run the application.

## How It Works

theBarcodeAPI is built with FastAPI for high-performance asynchronous API capabilities. It uses PostgreSQL as the primary database and Redis for rate limiting and caching.

- **Barcode Generation**: The application uses the `barcode_generator.py` module to generate barcodes in various formats based on user input.
- **API Endpoints**: Defined in the `app/api/` directory, the endpoints handle requests for generating barcodes, checking application health, managing tokens, and retrieving usage statistics.
- **Database Operations**: SQLAlchemy models in `models.py` interact with PostgreSQL to store and retrieve data.
- **Rate Limiting**: Implemented using Redis in `rate_limiter.py` to control API usage and prevent abuse.
- **Security**: JWT authentication is managed using tokens, with security configurations defined in `security.py`.

## Getting Started

To get started with theBarcodeAPI, you can run the project locally or access it via our hosted platform.

### Prerequisites

- Docker
- Docker Compose (docker-compose)

### Running Locally

1. **Clone the repository:**

    ```bash
    git clone git@github.com:pboachie/boachiefamily.net.git
    cd barcode-api
    ```

2. **Create a `.env` file:**

    ```bash
    cp .env.example .env
    ```

    Fill in the necessary values in the `.env` file.

3. **Build and run the Docker containers:**
    - BACKEND:
        ```bash
        cd theBarcodeapi/barcodeAPI/
        docker-compose up --build
        ```
    - FRONTEND:
        ```bash
        cd theBarcodeAPI/
        npm install
        npm run dev

4. **Access the API:**

    The API will be available at `http://localhost:8000`.

## API Documentation

Once the application is running, you can access the API documentation at:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

## Environment Variables

Key environment variables:

- `API_VERSION`: The version of the API
- `SECRET_KEY`: Secret key for JWT token generation
- `MASTER_API_KEY`: Master API key for administrative access
- `ALGORITHM`: Algorithm used for JWT token generation
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Expiration time for access tokens
- `REDIS_URL`: URL for Redis connection
- `DATABASE_URL`: URL for PostgreSQL database connection

## Database Migrations

Database migrations are handled using Alembic. The `start.sh` script automatically applies migrations on startup.

## Testing

To run the tests, use the following command:

```bash
docker-compose run api pytest