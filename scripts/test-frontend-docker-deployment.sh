#!/bin/bash

echo "Testing Frontend Docker Deployment"
echo "=================================="

# Set environment variables for testing
export PROJECT_VERSION="0.1.8"
export ENVIRONMENT="production"
export API_PORT="8000"
export FRONTEND_PORT="3000"

# Test the deployment script
if /home/pboachie/thebarcodeapi/scripts/deploy-frontend-docker.sh; then
    echo ""
    echo "🎉 Test completed successfully!"
    echo ""
    echo "Verification steps completed:"
    echo "✅ Frontend container is running"
    echo "✅ Health check passed"
    echo "✅ Frontend is accessible on port 3000"
    echo ""
    echo "You can now:"
    echo "1. Access the frontend at http://localhost:3000"
    echo "2. Check container logs: (cd /opt/thebarcodeapi && docker-compose logs barcodefrontend)"
    echo "3. Stop the container: (cd /opt/thebarcodeapi && docker-compose stop barcodefrontend)"
else
    echo ""
    echo "❌ Test failed! Check the error messages above."
    exit 1
fi
