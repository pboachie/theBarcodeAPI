#!/bin/bash

echo "Frontend Deployment Manager"
echo "=========================="

DEPLOYMENT_TYPE=${1:-"docker"}

case $DEPLOYMENT_TYPE in
    "docker")
        echo "Deploying frontend with Docker..."
        echo "Stopping PM2 processes first..."
        pm2 stop thebarcodeapi-frontend-production 2>/dev/null || true
        pm2 delete thebarcodeapi-frontend-production 2>/dev/null || true
        
        echo "Starting Docker Compose with frontend..."
        cd /opt/thebarcodeapi
        docker-compose up -d barcodefrontend
        
        echo "Checking frontend health..."
        sleep 10
        if curl -f http://localhost:3000; then
            echo "✅ Frontend is running on Docker!"
        else
            echo "❌ Frontend health check failed"
            exit 1
        fi
        ;;
        
    "pm2")
        echo "Deploying frontend with PM2..."
        echo "Stopping Docker frontend first..."
        cd /opt/thebarcodeapi
        docker-compose stop barcodefrontend 2>/dev/null || true
        
        echo "Starting PM2 process..."
        cd /opt/thebarcodeapi/production
        pm2 start ecosystem.config.js --env production
        
        echo "Checking frontend health..."
        sleep 10
        if curl -f http://localhost:3000; then
            echo "✅ Frontend is running on PM2!"
        else
            echo "❌ Frontend health check failed"
            exit 1
        fi
        ;;
        
    *)
        echo "Usage: $0 [docker|pm2]"
        echo "  docker: Deploy using Docker Compose (recommended)"
        echo "  pm2:    Deploy using PM2 process manager"
        exit 1
        ;;
esac

echo "Deployment completed!"
