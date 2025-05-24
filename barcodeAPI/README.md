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

## MCP Server for Barcode Generation

The file `barcodeAPI/app/mcp_server.py` provides Model Context Protocol (MCP) tools for barcode generation. This allows compatible MCP clients to interface with the barcode generation capabilities of this application.

### Running the Server Directly

You can run the MCP server directly from the root directory of the project (the directory containing the `barcodeAPI` folder) using the following command:

```bash
python -m barcodeAPI.app.mcp_server
```

The server communicates over `stdio` (standard input/output).

### Client Configuration Example

A generic MCP client might be configured to launch this server using a JSON configuration similar to the following:

```json
{
    "mcpServers": {
        "barcode_generator_mcp": {
            "command": "python",
            "args": [
                "-m",
                "barcodeAPI.app.mcp_server"
            ],
            "working_directory": "/path/to/your/project/root"
        }
    }
}
```

**Notes:**
- `"barcode_generator_mcp"` is the name provided during `FastMCP` initialization in `mcp_server.py`.
- Replace `"/path/to/your/project/root"` with the actual absolute path to the root directory of this project (i.e., the directory where the `barcodeAPI` folder is located).

### Testing the MCP Server

Unit tests for the MCP server are located in `barcodeAPI/app/tests/test_mcp_server.py`. You can run these tests from the project root directory using pytest:

```bash
pytest barcodeAPI/app/tests/test_mcp_server.py
```

Alternatively, if pytest is configured to discover tests (e.g., via `pyproject.toml` or `pytest.ini`), you might be able to run all tests, including MCP server tests, with a simple:

```bash
pytest
```

To test the MCP server with a real MCP client, you would:
1. Ensure the server can be run, e.g., `python -m barcodeAPI.app.mcp_server` from the project root.
2. Configure your MCP client to connect to this server, using the details provided in the "Client Configuration Example" section above.
3. Invoke the `generate_barcode_mcp` tool through your MCP client's interface, providing the necessary arguments (data, format, etc.).
4. Observe the output in your client, which should be a base64 encoded image string on success, or an error message on failure.
