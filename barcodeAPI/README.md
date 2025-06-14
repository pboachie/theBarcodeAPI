# Barcode API Project

This project is a barcode generation and management API built with FastAPI, PostgreSQL, and Redis.

## Project Structure

```
barcode/
├── alembic/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── barcode.py
│   │   ├── health.py
│   │   ├── token.py
│   │   └── usage.py
│   ├── __init__.py
│   ├── barcode_generator.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   ├── main.py
│   ├── models.py
│   ├── rate_limiter.py
│   ├── redis.py
│   ├── schemas.py
│   └── security.py
├── tests/
│   ├── __init__.py
│   ├── concurrent_tester.py
│   ├── test_barcode.py
│   ├── test_health.py
│   └── test_usage.py
├── .env
├── .env.example
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── init-db.sh
├── README.md
├── requirements.txt
└── start.sh
```

## Prerequisites

- Docker
- Docker Compose

## Getting Started

1. Clone the repository:
   ```
   git clone git@github.com:pboachie/boachiefamily.net.git
   cd barcode-api
   ```

2. Create a `.env` file based on the `.env.example` and fill in the necessary values:
   ```
   cp .env.example .env
   ```

3. Build and run the Docker containers:
   ```
   docker-compose up --build
   ```

4. The API will be available at `http://localhost:8000`.

## API Documentation

Once the application is running, you can access the API documentation at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## WebSocket/MCP Support

The API now includes **authenticated** WebSocket support with Model Context Protocol (MCP) for real-time barcode generation:

### 🔐 Authentication Required

**Step 1: Get Client ID**
```bash
# Request authentication (rate limited: 1 per 30 minutes)
curl -X POST "http://localhost:8000/api/v1/mcp/auth" \
     -H "Content-Type: application/json" \
     -d "{}"
```

**Step 2: Connect with WebSocket URL**
```bash
# Use the websocket_url from the auth response
ws://localhost:8000/api/v1/mcp/ws/YOUR-CLIENT-ID
```

### Documentation
- [WebSocket MCP Technical Guide](WEBSOCKET_MCP.md)
- [Remote Connections & Testing Guide](../REMOTE_CONNECTIONS.md)

### Test Script
```bash
python3 tests/test_websocket_mcp.py
```

**Important Notes:**
- Client IDs expire in 30 minutes
- Authentication is rate limited (1 request per 30 minutes per IP)
- Invalid client IDs will be rejected with WebSocket close code 4003

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

```
docker-compose run api pytest
```

## Deployment

The project is containerized and can be deployed using Docker and Docker Compose. Adjust the `docker-compose.yml` file as needed for your production environment.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.
