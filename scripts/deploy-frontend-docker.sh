#!/bin/bash

echo "Frontend Docker Deployment for theBarcodeAPI"
echo "============================================="

# Determine deployment directory - check if we're in production or development
if [ -d "/opt/thebarcodeapi" ] && [ -f "/opt/thebarcodeapi/docker-compose.yml" ]; then
    DEPLOYMENT_DIR="/opt/thebarcodeapi"
elif [ -f "docker-compose.yml" ]; then
    DEPLOYMENT_DIR="$(pwd)"
else
    echo "❌ Could not find docker-compose.yml file"
    echo "Checked: /opt/thebarcodeapi/docker-compose.yml and $(pwd)/docker-compose.yml"
    exit 1
fi

DOCKER_COMPOSE_FILE="$DEPLOYMENT_DIR/docker-compose.yml"
echo "Using deployment directory: $DEPLOYMENT_DIR"

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

# Always run docker-compose from the directory containing docker-compose.yml
if [ "$PWD" != "$DEPLOYMENT_DIR" ]; then
    echo "Switching to deployment directory: $DEPLOYMENT_DIR"
    cd "$DEPLOYMENT_DIR" || { echo "❌ Failed to cd to $DEPLOYMENT_DIR"; exit 1; }
fi

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
