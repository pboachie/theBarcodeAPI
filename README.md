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

theBarcodeAPI now includes **multiple MCP endpoints** for real-time barcode generation, perfect for AI assistants and other applications:

- **WebSocket MCP** (authenticated): Real-time bidirectional communication
- **HTTP MCP** (no auth): RESTful MCP protocol for simple integrations
- **SSE MCP** (authenticated): Server-sent events for legacy support

### 🚀 Quick Start Options

**Option 1: HTTP MCP (No Authentication Required)**

Perfect for testing! Try it immediately:

```bash
# Test HTTP MCP endpoint - no auth needed
curl -X POST "http://localhost:8000/api/v1/mcp/tools/call" \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/call",
       "params": {
         "name": "barcode_generator",
         "arguments": {
           "data": "TEST123",
           "format": "code128"
         }
       }
     }'
```

**Option 2: WebSocket MCP (Authentication Required)**

### 🔐 Authentication Required

**Important**: All WebSocket connections now require a valid client ID. You must obtain a client ID from the auth endpoint before connecting.

### Step 1: Get a Client ID

**Rate Limited**: 1 request per 30 minutes per IP address.

```bash
# Request a client ID (replace localhost:8000 with your server)
curl -X POST "http://localhost:8000/api/v1/mcp/auth" \
     -H "Content-Type: application/json" \
     -d "{}"
```

Response:
```json
{
  "client_id": "550e8400-e29b-41d4-a716-446655440000",
  "expires_in": 1800,
  "websocket_url": "ws://localhost:8000/api/v1/mcp/ws/550e8400-e29b-41d4-a716-446655440000"
}
```

### Step 2: Connect to WebSocket

Use the `websocket_url` from the auth response:

```javascript
// Connect using the authenticated WebSocket URL
const ws = new WebSocket('ws://localhost:8000/api/v1/mcp/ws/550e8400-e29b-41d4-a716-446655440000');

// Initialize MCP session
ws.onopen = function() {
    console.log('Connected to MCP WebSocket');
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

ws.onerror = function(error) {
    console.error('WebSocket error:', error);
};
```

### Step 3: Generate Barcodes

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

### ⚠️ Important Notes

- **Client IDs expire in 30 minutes** - you'll need to get a new one if it expires
- **Rate limiting**: Only 1 client ID per 30 minutes per IP address
- **Invalid client IDs**: WebSocket will close with code 4003 if client ID is invalid/expired
- **Authentication first**: Always get a client ID before attempting WebSocket connection

### Testing with Different Tools

**Browser Console**: Copy the JavaScript code above
**Python**: Use `websockets` library with the authenticated URL
**Command Line**: Use `websocat` or similar tools with the full WebSocket URL

For detailed WebSocket/MCP documentation and remote connection guides, see:
- [WebSocket MCP Documentation](barcodeAPI/WEBSOCKET_MCP.md)
- [Remote Connections Guide](REMOTE_CONNECTIONS.md)

### 📍 All Available MCP Endpoints

**HTTP MCP Endpoints (No Auth):**
- `POST /api/v1/mcp/initialize` - Initialize MCP session
- `POST /api/v1/mcp/tools/list` - List available tools
- `POST /api/v1/mcp/tools/call` - Execute barcode generation
- `POST /api/v1/mcp/resources/list` - List available resources
- `POST /api/v1/mcp/resources/read` - Read resource data

**Authenticated Endpoints:**
- `POST /api/v1/mcp/auth` - Get client ID (rate limited)
- `WS /api/v1/mcp/ws/{client_id}` - WebSocket MCP connection
- `GET /api/v1/mcp/sse/{client_id}` - Server-sent events stream
- `GET /api/v1/mcp/status` - Connection status and metrics

## Environment Variables

Key environment variables:
- `SECRET_KEY`: JWT signing key (backend)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `MASTER_API_KEY`: Administrative access key
- `NEXT_PUBLIC_APP_VERSION`: Frontend version display

## 📈 Performance & Monitoring

### **Key Metrics**
- **Response Time**: < 200ms average for barcode generation
- **Throughput**: 1000+ requests per minute
- **Uptime**: 99.9% availability target
- **Cache Hit Rate**: 85%+ for repeated requests

### **Monitoring Features**
- Real-time health checks via `/health` endpoint
- Usage analytics and reporting
- Error tracking and structured logging
- Performance metrics collection
- Docker container health monitoring

### **Production Deployment**
- **Containerized**: Full Docker Compose orchestration
- **Scalable**: Horizontal scaling ready
- **Persistent**: Data persistence via Docker volumes
- **Secure**: Environment-based configuration
- **Monitored**: Comprehensive logging and health checks

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### **Development Setup**
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes with tests
4. Submit a pull request

### **Contribution Guidelines**
- Follow existing code style and conventions
- Add tests for new functionality
- Update documentation as needed
- Ensure all tests pass before submitting

## 👨‍💻 About the Developer

**Prince Boachie-Darquah**
- 📧 **Email**: [princeboachie@gmail.com](mailto:princeboachie@gmail.com)
- 💼 **LinkedIn**: [www.linkedin.com/in/prince-boachie-darquah-a574947b](https://www.linkedin.com/in/prince-boachie-darquah-a574947b)
- 🌐 **Portfolio**: [github.com/pboachie](https://github.com/pboachie)

*This project demonstrates expertise in full-stack development, API design, containerization, and modern web technologies. It showcases the ability to build scalable, production-ready applications with comprehensive testing and documentation.*

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Built with ❤️ using my fingers and some AI**

[🚀 View Live Demo](https://thebarcodeapi.com/) • [📖 API Docs](https://api.thebarcodeapi.com/docs) • [🤝 Connect on LinkedIn](https://www.linkedin.com/in/prince-boachie-darquah-a574947b)

</div>
