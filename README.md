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
- **WebSocket/MCP Support**: Real-time barcode generation via Model Context Protocol
- **AI Assistant Ready**: AGSC (AI/Assistant Generation Service Compatible) server
- **Docker Optimized**: Enhanced health checks and container compatibility

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

    Source the environment variables:

    ```bash
    source .env
    ```

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

## WebSocket/MCP Testing

theBarcodeAPI now includes WebSocket support with Model Context Protocol (MCP) for real-time barcode generation, perfect for AI assistants and other real-time applications.

### Quick Test Connection

Test the WebSocket MCP endpoint before integrating with AI agents:

```bash
# Using the test client endpoint
ws://localhost:8000/api/v1/mcp/ws/test-client
```

### Test with Browser Console

Open your browser's developer console and try:

```javascript
// Connect to the WebSocket MCP endpoint
const ws = new WebSocket('ws://localhost:8000/api/v1/mcp/ws/test-client');

// Initialize MCP session
ws.onopen = function() {
    ws.send(JSON.stringify({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "1.0.0",
            "clientInfo": {
                "name": "browser-test",
                "version": "1.0.0"
            }
        }
    }));
};

// Listen for responses
ws.onmessage = function(event) {
    console.log('Response:', JSON.parse(event.data));
};
```

### Generate Barcodes via WebSocket

Once connected and initialized, generate barcodes in real-time:

```javascript
// Generate a Code128 barcode
ws.send(JSON.stringify({
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "barcode_generator",
        "arguments": {
            "data": "HELLO-WORLD-2024",
            "format": "code128",
            "width": 300,
            "height": 150
        }
    }
}));
```

For detailed WebSocket/MCP documentation and remote connection guides, see:
- [WebSocket MCP Documentation](barcodeAPI/WEBSOCKET_MCP.md)
- [Remote Connections Guide](REMOTE_CONNECTIONS.md)

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
