#!/bin/bash

echo "Frontend Docker Deployment for theBarcodeAPI"
echo "============================================="

DEPLOYMENT_DIR="/opt/thebarcodeapi"
DOCKER_COMPOSE_FILE="$DEPLOYMENT_DIR/docker-compose.yml"

# Function to check if frontend is running
check_frontend_health() {
    local max_attempts=12
    local attempt=1
    
    echo "Checking frontend health (max $max_attempts attempts)..."
    
    while [ $attempt -le $max_attempts ]; do
        echo "Health check attempt $attempt/$max_attempts..."
        
        if curl -f -s http://localhost:3000 > /dev/null 2>&1; then
            echo "✅ Frontend is healthy!"
            return 0
        fi
        
        if [ $attempt -lt $max_attempts ]; then
            echo "Frontend not ready, waiting 5 seconds..."
            sleep 5
        fi
        
        attempt=$((attempt + 1))
    done
    
    echo "❌ Frontend health check failed after $max_attempts attempts"
    return 1
}

# Check if we're in the right directory structure
if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
    echo "❌ Docker compose file not found at $DOCKER_COMPOSE_FILE"
    exit 1
fi

echo "Stopping PM2 processes first..."
pm2 stop thebarcodeapi-frontend-production 2>/dev/null || true
pm2 delete thebarcodeapi-frontend-production 2>/dev/null || true

echo "Switching to deployment directory..."
cd "$DEPLOYMENT_DIR"

# Determine docker compose command
if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

echo "Using Docker Compose command: $COMPOSE_CMD"

echo "Stopping any existing frontend containers..."
$COMPOSE_CMD stop barcodefrontend 2>/dev/null || true
$COMPOSE_CMD rm -f barcodefrontend 2>/dev/null || true

echo "Building and starting frontend container..."
$COMPOSE_CMD up -d --build barcodefrontend

if [ $? -eq 0 ]; then
    echo "Frontend container started successfully!"
    
    # Check container status
    echo "Container status:"
    $COMPOSE_CMD ps barcodefrontend
    
    # Wait a moment for the container to fully start
    echo "Waiting for frontend to start..."
    sleep 15
    
    # Health check
    if check_frontend_health; then
        echo "🎉 Frontend deployment completed successfully!"
        echo "Frontend is accessible at http://localhost:3000"
        
        # Show container logs for verification
        echo "Recent container logs:"
        $COMPOSE_CMD logs --tail=10 barcodefrontend
        
        exit 0
    else
        echo "❌ Frontend deployment failed - health check unsuccessful"
        echo "Container logs:"
        $COMPOSE_CMD logs --tail=20 barcodefrontend
        exit 1
    fi
else
    echo "❌ Failed to start frontend container"
    echo "Container logs:"
    $COMPOSE_CMD logs --tail=20 barcodefrontend
    exit 1
fi
