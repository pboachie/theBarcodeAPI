# 🔧 Barcode API Backend

> **High-performance FastAPI backend powering theBarcodeAPI platform**

This is the backend service for theBarcodeAPI, built with FastAPI, PostgreSQL, and Redis. It provides a comprehensive barcode generation API with authentication, rate limiting, and Model Context Protocol (MCP) support.

## 🚀 Features

### **Core API Capabilities**
- **Multi-format Barcode Generation**: Support for 15+ barcode formats
- **Bulk Processing**: Asynchronous batch barcode generation
- **Real-time Processing**: Sub-second response times
- **High Availability**: Production-ready with health monitoring

### **Enterprise Features**
- **JWT Authentication**: Secure token-based authentication
- **Rate Limiting**: Redis-based intelligent throttling
- **Usage Analytics**: Comprehensive tracking and reporting
- **API Documentation**: Auto-generated OpenAPI/Swagger docs
- **Database Migrations**: Alembic-managed schema evolution

### **Advanced Integrations**
- **MCP Server**: Model Context Protocol for AI assistant integration
- **Server-Sent Events**: Real-time communication support
- **Caching Layer**: Redis-powered performance optimization
- **Background Tasks**: Asynchronous job processing

## 🔌 VS Code MCP Integration

To integrate the Barcode API's MCP server with VS Code for AI assistant capabilities, you need to configure your VS Code `settings.json` file. This allows VS Code to communicate with the MCP server.

1.  **Open VS Code Settings**:
    *   Press `Ctrl+,` (Windows/Linux) or `Cmd+,` (macOS) to open the Settings UI.
    *   Click on the "Open Settings (JSON)" icon in the top right corner to open the `settings.json` file directly.

2.  **Add MCP Server Configuration**:
    Add the following JSON snippet to your `settings.json` file. If you already have an `"mcp.servers"` object, add `"theBarcodeAPI"` entry to it.

    ```json
    "mcp": {
        "servers": {
            "theBarcodeAPI": {
                "type": "sse",
                "url": "http://localhost:8000/api/v1/mcp/sse"
            }
        }
    }
    ```

3.  **Using a Remote or Local IP for the MCP Endpoint**:
    *   The definitive MCP server endpoint for the Barcode API is `/api/v1/mcp/sse`. This is the sole path to be used by any MCP client.
    *   **Local Backend**: If the Barcode API backend is running on the same machine as your MCP client (e.g., VS Code), the correct URL is `http://localhost:8000/api/v1/mcp/sse`.
    *   **Remote/Network Backend**: If the backend is running on a different machine (on your local network or a remote server), replace `localhost` with that machine's IP address or resolvable hostname. For example: `http://192.168.1.10:8000/api/v1/mcp/sse` or `http://your-remote-server.com/api/v1/mcp/sse`.
    *   **Port Accessibility**: Ensure that the API port (default `8000`, or as configured) is accessible from the client machine over the network. Firewalls or network configurations might need adjustment.

After correctly configuring this in your `settings.json`, your MCP client (like VS Code) will be able to communicate with the Barcode API's MCP server. It is important to note that only the `/api/v1/mcp/sse` endpoint is supported for MCP. Any older endpoints (e.g., those involving `/mcp/cmd`) are deprecated and will not work.

## 🏗️ Architecture

### **Technology Stack**
- **Framework**: FastAPI 0.104+ (Python 3.11+)
- **Database**: PostgreSQL with SQLAlchemy 2.0 ORM
- **Cache**: Redis for sessions and rate limiting
- **Authentication**: JWT with bcrypt password hashing
- **Testing**: pytest with 90%+ coverage
- **Containerization**: Docker & Docker Compose

### **Project Structure**
```
├── app/
│   ├── api/                    # API route handlers
│   │   ├── barcode.py         # Barcode generation endpoints
│   │   ├── health.py          # Health check endpoints
│   │   ├── token.py           # Authentication endpoints
│   │   ├── usage.py           # Analytics endpoints
│   │   └── admin.py           # Administrative endpoints
│   │
│   ├── barcode_generator.py   # Core barcode generation logic
│   ├── mcp_server.py          # Model Context Protocol server
│   ├── rate_limiter.py        # Redis-based rate limiting
│   ├── security.py            # Authentication & authorization
│   ├── models.py              # SQLAlchemy database models
│   ├── schemas.py             # Pydantic request/response schemas
│   ├── database.py            # Database connection management
│   ├── redis.py               # Redis connection management
│   ├── config.py              # Configuration management
│   └── main.py                # FastAPI application factory
│
├── tests/                     # Comprehensive test suite
│   ├── test_barcode.py        # Barcode generation tests
│   ├── test_health.py         # Health check tests
│   ├── test_usage.py          # Analytics tests
│   └── test_mcp_server.py     # MCP server tests
│
├── alembic/                   # Database migrations
│   ├── versions/              # Migration files
│   └── env.py                 # Migration environment
│
├── docker-compose.yml         # Service orchestration
├── Dockerfile                 # Container configuration
├── requirements.txt           # Python dependencies
├── pytest.ini               # Test configuration
└── start.sh                  # Application startup script
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose (for running as part of the whole system)
- Python 3.11+ (for local standalone backend development)

### 1. Environment Setup (for Backend)
Ensure you have a `.env` file inside the `barcodeApi` directory. You can copy the example:
```bash
# Make sure you are in the barcodeApi directory
cp .env.example .env
# Edit ./barcodeApi/.env with your backend-specific configuration
```

### 2. Run with Docker (as part of the full platform)
The backend is managed by the `docker-compose.yml` file in the project root.
```bash
# From the project root directory (parent of barcodeApi and barcodeFrontend)
docker-compose up --build barcodeApi
# Or to run all services:
# docker-compose up --build

# API available at: http://localhost:8000 (or as configured in docker-compose.yml)
# Swagger docs: http://localhost:8000/docs
```

### 3. Local Standalone Backend Development
If you want to run only the backend locally, without Docker:
```bash
# Navigate to the barcodeApi directory
# cd barcodeApi # This line is not needed if already editing barcodeApi/README.md

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations (ensure PostgreSQL is running and accessible)
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Versioning

The application version is available within the backend via the `APP_VERSION` environment variable (which populates `settings.API_VERSION` in `app/config.py`). This variable is set during the Docker build process, originating from the `PROJECT_VERSION` defined in the root `.env` file and passed via Docker Compose.

## 📋 Environment Configuration

### **Required Variables**
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/barcodeapi

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-super-secret-key-here
MASTER_API_KEY=your-master-api-key

# JWT Configuration
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Application
API_VERSION=1.0.0
ENVIRONMENT=development
```

### **Optional Variables**
```bash
# Rate Limiting
RATE_LIMIT_REQUESTS=50
RATE_LIMIT_WINDOW=60

# Performance
CACHE_TTL=300
MAX_BULK_SIZE=100

# Monitoring
LOG_LEVEL=INFO
SENTRY_DSN=your-sentry-dsn
```

## 📊 API Endpoints

### **Barcode Generation**
```http
POST   /api/v1/generate        # Generate single barcode
POST   /api/v1/bulk            # Bulk generation (up to 100)
GET    /api/v1/formats         # List supported formats
```

### **Authentication**
```http
POST   /api/v1/token           # Generate access token
POST   /api/v1/token/refresh   # Refresh token
POST   /api/v1/register        # User registration
```

### **Monitoring & Analytics**
```http
GET    /health                 # Health check
GET    /metrics                # Performance metrics
GET    /api/v1/usage           # Usage statistics
GET    /api/v1/usage/user/{id} # User-specific usage
```

### **MCP Server**
```http
GET    /api/v1/mcp/sse                    # Server-Sent Events endpoint for real-time communication and MCP commands
```

### **Example API Calls**

#### **Generate QR Code**
```bash
curl -X POST "http://localhost:8000/api/v1/generate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "data": "https://thebarcodeapi.com",
    "format": "qr",
    "width": 300,
    "height": 300,
    "image_format": "PNG"
  }'
```

#### **Bulk Generation**
```bash
curl -X POST "http://localhost:8000/api/v1/bulk" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "items": [
      {"data": "ITEM001", "format": "code128"},
      {"data": "ITEM002", "format": "code128"},
      {"data": "ITEM003", "format": "code128"}
    ],
    "options": {
      "width": 200,
      "height": 100,
      "show_text": true
    }
  }'
```

## 🤖 MCP Server Integration

The backend includes a comprehensive MCP server for AI assistant integration. The primary endpoint for MCP communication is `/api/v1/mcp/sse`.

### **Connection Setup for MCP Clients (e.g., VS Code)**

To connect an MCP-compatible client, configure it to use the server's `/api/v1/mcp/sse` endpoint. The server uses FastMCP, which handles tool calls over this Server-Sent Events (SSE) connection.

**Example `settings.json` for VS Code:**

*   **Local Development:**
    If the Barcode API server is running locally (e.g., `http://localhost:8000`):
    ```json
    {
      "mcp": {
        "servers": {
          "theBarcodeAPI_local": {
            "type": "sse",
            "url": "http://localhost:8000/api/v1/mcp/sse",
            "description": "Local Barcode API MCP Server"
          }
        }
      }
    }
    ```

*   **Remote/Production:**
    If the Barcode API is deployed (e.g., `https://api.thebarcodeapi.com`):
    ```json
    {
      "mcp": {
        "servers": {
          "theBarcodeAPI_remote": {
            "type": "sse",
            "url": "https://api.thebarcodeapi.com/api/v1/mcp/sse",
            "description": "Remote Barcode API MCP Server"
          }
        }
      }
    }
    ```

**Important Notes:**
- The URL for the MCP server should always point to the `/api/v1/mcp/sse` path.
- Any older or different MCP endpoints (like `/mcp/cmd` or paths ending in `/messages/`) are deprecated and should not be used.
- The MCP client will send JSON-RPC `tools/call` requests over the established SSE connection to this endpoint.

### **Available MCP Tools**
- **`generate_barcode`**: Full-featured barcode generation
  - Supports all 15+ barcode formats
  - 20+ customization parameters
  - Returns base64-encoded image data

## 🔌 MCP Client Configuration

To connect an MCP-compatible client (like a VS Code extension or an AI agent) to this server, you need to configure the client with the server's SSE endpoint: `/api/v1/mcp/sse`. The server uses FastMCP, which handles commands over this single SSE connection.

### **Local Development Example**

If you are running the Barcode API server locally (e.g., via `docker-compose up` or `uvicorn app.main:app --reload`), the MCP SSE endpoint is:

```
http://localhost:8000/api/v1/mcp/sse
```

Here's an example of how you might configure this in a client's `settings.json` (e.g., for a VS Code extension):

```json
{
  "mcp": {
    "servers": {
      "theBarcodeAPI_local": {
        "type": "sse",
        "url": "http://localhost:8000/api/v1/mcp/sse",
        "description": "Local Barcode API MCP Server"
      }
    }
  }
}
```

### **Remote/Production Example**

When the Barcode API is deployed to a production environment (e.g., `https://api.thebarcodeapi.com`), the MCP SSE endpoint will be:

```
https://api.thebarcodeapi.com/api/v1/mcp/sse
```

The client configuration would look like this:

```json
{
  "mcp": {
    "servers": {
      "theBarcodeAPI_remote": {
        "type": "sse",
        "url": "https://api.thebarcodeapi.com/api/v1/mcp/sse",
        "description": "Remote Barcode API MCP Server"
      }
    }
  }
}
```
**Note**: Ensure your client sends MCP JSON-RPC requests (typically via HTTP POST if not using a library that abstracts this over SSE) to the `/api/v1/mcp/sse` endpoint. FastMCP routes commands sent to this SSE mount path. The `/messages/` suffix is not used.

## 🧪 Testing

### **Run Test Suite**
```bash
# All tests
pytest

# Specific test file
pytest tests/test_barcode.py

# With coverage (requires pytest-cov)
pip install pytest-cov
pytest --cov=app tests/

# Integration tests only
pytest -m integration

# Unit tests only
pytest -m "not integration"
```

### **Test Categories**
- **Unit Tests**: Individual component testing
- **Integration Tests**: Database and Redis integration
- **API Tests**: Endpoint behavior validation
- **Performance Tests**: Load and stress testing
- **MCP Tests**: Model Context Protocol functionality

## 🔧 Database Management

### **Migrations**
```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# View migration history
alembic history
```

### **Database Schema**
- **Users**: Authentication and user management
- **Tokens**: JWT token tracking and blacklisting
- **BarcodeRequests**: Generation request logging
- **UsageStats**: Analytics and usage tracking
- **RateLimits**: Rate limiting state management

## 📈 Performance & Monitoring

### **Performance Metrics**
- **Response Time**: < 200ms average
- **Throughput**: 1000+ req/min sustained
- **Cache Hit Rate**: 85%+ for repeated requests
- **Database Pool**: Optimized connection management

### **Monitoring Endpoints**
```http
GET /health                    # Basic health check
GET /health/detailed          # Comprehensive system status
GET /metrics                  # Prometheus-compatible metrics
GET /api/v1/stats            # Application statistics
```

### **Logging Configuration**
```python
# Structured JSON logging
LOG_CONFIG = {
    "version": 1,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    }
}
```

## 🚀 Deployment

### **Docker Production**
```bash
# Build production image
docker build -t barcodeapi:latest .

# Run with production config
docker run -p 8000:8000 \
  -e DATABASE_URL=$DATABASE_URL \
  -e REDIS_URL=$REDIS_URL \
  barcodeapi:latest
```

### **Environment-Specific Configs**
- **Development**: Local debugging enabled, verbose logging
- **Staging**: Production-like with additional monitoring
- **Production**: Optimized for performance and security

## 🤝 Contributing

### **Development Guidelines**
1. Follow PEP 8 style guidelines
2. Add type hints for all functions
3. Write comprehensive tests (aim for 90%+ coverage)
4. Update API documentation for new endpoints
5. Include migration files for schema changes

### **Code Quality Tools**
```bash
# Format code
black app/

# Sort imports
isort app/

# Type checking
mypy app/

# Linting
flake8 app/
```

## 📚 Additional Resources

- **FastAPI Documentation**: [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
- **SQLAlchemy 2.0**: [https://docs.sqlalchemy.org/](https://docs.sqlalchemy.org/)
- **Alembic Migrations**: [https://alembic.sqlalchemy.org/](https://alembic.sqlalchemy.org/)
- **Redis Documentation**: [https://redis.io/documentation](https://redis.io/documentation)
- **MCP Specification**: [https://modelcontextprotocol.io/](https://modelcontextprotocol.io/)

---

**Built with ❤️ by Prince Boachie-Darquah**
- 📧 [princeboachie@gmail.com](mailto:princeboachie@gmail.com)
- 💼 [LinkedIn](https://www.linkedin.com/in/prince-boachie-darquah-a574947b)
