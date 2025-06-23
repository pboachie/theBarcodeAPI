# theBarcodeAPI

Welcome to theBarcodeAPI - Your go-to solution for barcode generation and processing!

live demo: https://thebarcodeapi.com

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

    Source the environment variables:

    ```bash
    source .env
    ```

3. **Build and run the Docker containers:**
    - BACKEND:
        ```bash
        cd theBarcodeapi/barcodeApi/
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

## MCP Integration

theBarcodeAPI includes **Model Context Protocol (MCP)** support for AI assistants and other applications, providing seamless barcode generation capabilities through HTTP streaming.

### 🚀 Quick Start

The MCP server uses an HTTP streaming endpoint for communication:

```bash
# Test MCP endpoint
curl -X POST "http://localhost:8000/api/v1/mcp-server/mcp/" \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/call",
       "params": {
         "name": "generate_barcode",
         "arguments": {
           "data": "TEST123",
           "format": "code128",
           "width": 300,
           "height": 150
         }
       }
     }'
```

### 📍 MCP Endpoint

**HTTP Streaming MCP:**
- `POST /api/v1/mcp-server/mcp/` - HTTP streaming endpoint for MCP communication

### 🔧 VS Code Integration

To use with VS Code, add this to your `settings.json`:

```json
{
  "mcp": {
    "servers": {
      "theBarcodeAPI": {
        "type": "http",
        "url": "http://localhost:8000/api/v1/mcp-server/mcp/"
      }
    }
  }
}
```

For remote connections, replace `localhost:8000` with your server URL.

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
