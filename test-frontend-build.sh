#!/bin/bash

echo "Testing Docker build for barcodeFrontend..."

cd /home/pboachie/thebarcodeapi/barcodeFrontend

echo "Building Docker image..."
if docker build -t barcodefrontend:test-build .; then
    echo "✅ Build successful!"
    echo "Testing the container..."
    if docker run -d --name frontend-test -p 3001:3000 barcodefrontend:test-build; then
        echo "Container started, waiting 10 seconds..."
        sleep 10
        echo "Testing frontend endpoint..."
        if curl -f http://localhost:3001; then
            echo "✅ Frontend is responding!"
        else
            echo "❌ Frontend not responding"
        fi
        echo "Stopping and removing test container..."
        docker stop frontend-test
        docker rm frontend-test
    else
        echo "❌ Container failed to start!"
    fi
    echo "Cleaning up test image..."
    docker rmi barcodefrontend:test-build || true
else
    echo "❌ Build failed!"
    exit 1
fi
