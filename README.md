# 🔢 theBarcodeAPI

> **A modern, full-stack barcode generation platform showcasing enterprise-grade web development practices**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-thebarcodeapi.com-blue?style=for-the-badge)](https://thebarcodeapi.com/)
[![API Status](https://img.shields.io/badge/API%20Status-Online-green?style=for-the-badge)](https://api.thebarcodeapi.com/health)

## 🚀 Portfolio Showcase

**theBarcodeAPI** is a comprehensive barcode generation platform that demonstrates modern full-stack development practices, scalable architecture, and professional-grade API design. This project serves as a showcase of advanced web development skills including real-time processing, API rate limiting, database optimization, and containerized deployment.

### 🌟 **Live Platform**: [https://thebarcodeapi.com/](https://thebarcodeapi.com/)

---

## 📋 Project Overview

A production-ready barcode generation service featuring a sleek Next.js frontend and a high-performance FastAPI backend. The platform supports multiple barcode formats, real-time generation, bulk processing, and includes comprehensive API management with authentication and rate limiting.

### 🎯 **Key Achievements**
- **Performance**: Sub-second barcode generation with Redis caching
- **Scalability**: Containerized architecture supporting concurrent users
- **Integration**: Model Context Protocol (MCP) server for AI assistant integration
- **Security**: JWT authentication with role-based access control
- **Monitoring**: Comprehensive usage analytics and health monitoring

## ✨ Features & Capabilities

### 🔧 **Core Features**
- **Multi-format Support**: QR Code, Code128, Code39, EAN-13, UPC-A, and more
- **Real-time Generation**: Instant barcode creation with live preview
- **Bulk Processing**: Generate hundreds of barcodes simultaneously
- **Custom Styling**: Adjustable dimensions, colors, and text options
- **High-Resolution Output**: Vector and raster formats with customizable DPI

### 🏗️ **Technical Features**
- **RESTful API**: Comprehensive API with OpenAPI/Swagger documentation
- **Rate Limiting**: Redis-based intelligent throttling
- **Caching Layer**: Optimized performance with strategic caching
- **Database Persistence**: PostgreSQL with Alembic migrations
- **Health Monitoring**: Real-time system status and metrics
- **MCP Integration**: AI assistant compatibility via Model Context Protocol

## 🛠️ Technology Stack

### **Frontend**
- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS + Radix UI Components
- **State Management**: React Hooks with optimistic updates
- **Animations**: Framer Motion

### **Backend**
- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Cache**: Redis for session management and rate limiting
- **Authentication**: JWT with bcrypt password hashing
- **API Documentation**: Auto-generated OpenAPI/Swagger

### **Infrastructure**
- **Containerization**: Docker & Docker Compose
- **Database Migrations**: Alembic
- **Testing**: pytest with comprehensive test coverage
- **Deployment**: Production-ready with environment configuration

### **Integrations**
- **MCP Server**: Model Context Protocol for AI assistant integration via the `/api/v1/mcp/sse` endpoint.
- **Server-Sent Events**: Real-time communication
- **Bulk Processing**: Asynchronous batch operations

## 🏗️ Architecture & Design

### **System Architecture**
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Next.js       │────│   FastAPI        │────│   PostgreSQL    │
│   Frontend      │    │   Backend        │    │   Database      │
│                 │    │                  │    │                 │
│ • React/TS      │    │ • Python 3.11+  │    │ • Data Models   │
│ • Tailwind CSS  │    │ • SQLAlchemy     │    │ • Migrations    │
│ • Radix UI      │    │ • Pydantic       │    │ • Indexing      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌──────────────────┐             │
         └──────────────│      Redis       │─────────────┘
                        │   Cache Layer    │
                        │                  │
                        │ • Rate Limiting  │
                        │ • Session Store  │
                        │ • Caching        │
                        └──────────────────┘
```

### **Project Structure**
```
thebarcodeapi/
├── 🐳 docker-compose.yml  # Main Docker Compose file for all services
│
├── 🎨 barcodeFrontend/    # Next.js Frontend Application
│   ├── app/
│   ├── components/
│   ├── public/
│   ├── Dockerfile          # Frontend Docker configuration
│   └── README.md           # Frontend specific documentation
│
├── 🔧 barcodeApi/        # FastAPI Backend Application
│   ├── app/
│   ├── alembic/
│   ├── Dockerfile          # Backend Docker configuration
│   └── README.md           # Backend specific documentation
│
├── .gitignore
├── LICENSE
└── README.md             # This file
```

## ⚙️ CI/CD & Deployment Process

This project uses GitHub Actions for automated CI/CD. For a detailed explanation of the deployment workflows, scripts, and infrastructure setup, please refer to the [Deployment Process Documentation (DEPLOYMENT.md)](DEPLOYMENT.md).

## 🚀 Quick Start

### **Prerequisites**
- Docker & Docker Compose
- Git

### **1. Clone & Setup Environment**
```bash
# Clone the repository
git clone https://github.com/pboachie/theBarcodeAPI.git
cd theBarcodeAPI

# Create a root .env file (if it doesn't exist) for global settings.
# This file is used by docker-compose.yml.
# Add the following line, customizing the version as needed:
echo "PROJECT_VERSION=0.1.8" >> .env
# (Or manually create/edit .env in the project root with PROJECT_VERSION=0.1.8)

# Setup backend environment (API keys, database credentials, etc.)
# This .env file is specific to the backend service.
# Navigate to the backend directory
cd barcodeApi
cp .env.example .env
# Edit barcodeApi/.env with your specific backend configuration
cd .. # Return to root

# Frontend environment (if needed)
# Check barcodeFrontend/README.md if specific .env setup is needed there.
# NEXT_PUBLIC_API_URL for the frontend is typically set in docker-compose.yml.
```

### **2. Run with Docker Compose (Recommended)**
This is the easiest way to get the entire platform running.
```bash
# From the project root directory (thebarcodeapi/)
docker-compose up --build

# Platform will be available:
# - Frontend: http://localhost:3000 (or as configured in docker-compose.yml)
# - Backend API: http://localhost:8000 (or as configured in docker-compose.yml)
# - API Documentation: http://localhost:8000/docs
```

### **3. Local Development Details**
For detailed instructions on running the frontend or backend services independently for development (e.g., without Docker, or for more granular control), please refer to their respective README files:

- **Frontend Development**: See `barcodeFrontend/README.md`
- **Backend Development**: See `barcodeApi/README.md`

### **4. Access the Application**
Once running via Docker Compose:
- **Frontend**: `http://localhost:3000` (default)
- **API Documentation**: `http://localhost:8000/docs` (default)
- **API Health Check**: `http://localhost:8000/health` (default)

## 📚 API Documentation

### **Interactive Documentation**
- **Swagger UI**: `https://api.thebarcodeapi.com/docs`
- **ReDoc**: `https://api.thebarcodeapi.com/redoc`

### **Key Endpoints**
```http
POST   /api/v1/generate      # Generate single barcode
POST   /api/v1/bulk          # Bulk barcode generation
GET    /api/v1/health        # System health status
POST   /api/v1/token         # Authentication
GET    /api/v1/usage         # Usage statistics
```

### **Example API Call**
```bash
curl -X POST "https://api.thebarcodeapi.com/api/v1/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "data": "HELLO123",
    "format": "code128",
    "width": 400,
    "height": 200,
    "show_text": true
  }'
```

## 🤖 MCP Server Integration

This project includes a **Model Context Protocol (MCP) server** for seamless AI assistant integration. The MCP endpoint is `/api/v1/mcp/sse`.

### **Connection Details**
- **Production MCP Endpoint**: `https://api.thebarcodeapi.com/api/v1/mcp/sse`
- **Local MCP Endpoint (when running via Docker Compose)**: `http://localhost:8000/api/v1/mcp/sse` (or your configured API port). Refer to `barcodeApi/README.md` for details on MCP if running the backend standalone.

### **Available MCP Tools**
- `generate_barcode`: Provides comprehensive barcode generation capabilities. It supports numerous formats and customization options (e.g., data content, barcode type, dimensions, colors, image format, text display, DPI, checksums, etc.). Refer to the tool's schema for a full list of parameters.

### **Usage Example (Illustrative)**
The following shows an illustrative example of how an MCP client might request a barcode generation:
```json
{
  "method": "tools/call",
  "params": {
    "name": "generate_barcode",
    "arguments": {
      "data": "SAMPLE123",
      "format": "CODE128",  // Example: Use a valid format from BarcodeFormatEnum (e.g., QRCODE, CODE128, EAN13)
      "width": 300,
      "height": 300,
      "image_format": "PNG", // Example: PNG, JPEG, SVG, etc.
      "show_text": true
    }
  }
}
```
**Note**: The exact structure of the `params` and the specific values for enums like `format` and `image_format` should align with the MCP server's registration and the tool's schema definition. The tool name `generate_barcode` corresponds to the function available to the MCP system.

## 🧪 Development & Testing

### **Running Tests**
```bash
# Backend tests (run from project root)
docker-compose run barcodeApi pytest
# Or for local backend dev, see barcodeApi/README.md

# Frontend tests (run from barcodeFrontend directory)
cd barcodeFrontend
npm test # Or yarn test, if applicable
cd ..
```

### **Environment Configuration**
Key environment variables:
- `SECRET_KEY`: JWT signing key
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `MASTER_API_KEY`: Administrative access key

## 📈 Performance & Monitoring

### **Key Metrics**
- **Response Time**: < 200ms average for barcode generation
- **Throughput**: 1000+ requests per minute
- **Uptime**: 99.9% availability target
- **Cache Hit Rate**: 85%+ for repeated requests

### **Monitoring Features**
- Real-time health checks
- Usage analytics and reporting
- Error tracking and logging
- Performance metrics collection

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
