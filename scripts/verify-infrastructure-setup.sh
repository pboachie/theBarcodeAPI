#!/bin/bash

# ---
# Purpose:
#   Verifies that infrastructure is properly set up before application deployment.
#   Checks for the presence of the infrastructure marker file and essential services.
#
# Environment Variables:
#   - ENVIRONMENT: Deployment environment (e.g., staging, production).
#
# Exit Codes:
#   0: Infrastructure is properly set up
#   1: Infrastructure setup is incomplete or missing
# ---

set -e

if [ -z "$ENVIRONMENT" ]; then
    echo "Error: ENVIRONMENT variable not set"
    exit 1
fi

MARKER_FILE="/opt/thebarcodeapi/${ENVIRONMENT}/.infra_initialized"

echo "=== Verifying Infrastructure Setup ==="
echo "Environment: ${ENVIRONMENT}"
echo "Marker file: ${MARKER_FILE}"

# Check if infrastructure marker file exists
if [ ! -f "${MARKER_FILE}" ]; then
    echo "Error: Infrastructure not initialized. Run the Infrastructure Setup workflow first."
    echo "Expected marker file: ${MARKER_FILE}"
    exit 1
fi

echo "✓ Infrastructure marker file found"

# Verify essential services are available
if ! command -v docker >/dev/null 2>&1; then
    echo "Error: Docker is not installed or not in PATH"
    exit 1
fi
echo "✓ Docker is available"

if ! command -v nginx >/dev/null 2>&1; then
    echo "Error: Nginx is not installed or not in PATH"
    exit 1
fi
echo "✓ Nginx is available"

# Check if environment directory exists
if [ ! -d "/opt/thebarcodeapi/${ENVIRONMENT}" ]; then
    echo "Error: Environment directory not found: /opt/thebarcodeapi/${ENVIRONMENT}"
    exit 1
fi
echo "✓ Environment directory exists"

# Check if essential subdirectories exist
REQUIRED_DIRS=(
    "/opt/thebarcodeapi/${ENVIRONMENT}/releases"
    "/opt/thebarcodeapi/${ENVIRONMENT}/backups"
    "/opt/thebarcodeapi/${ENVIRONMENT}/releases/data"
)

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "${dir}" ]; then
        echo "Error: Required directory not found: ${dir}"
        exit 1
    fi
done
echo "✓ Required directories exist"

# Verify Docker service is active
if ! systemctl is-active --quiet docker; then
    echo "Error: Docker service is not active"
    exit 1
fi
echo "✓ Docker service is active"

# Verify Nginx service is active
if ! systemctl is-active --quiet nginx; then
    echo "Warning: Nginx service is not active (this might be expected for some deployments)"
else
    echo "✓ Nginx service is active"
fi

echo "=== Infrastructure Setup Verification Complete ==="
echo "✓ All infrastructure requirements are met"
exit 0
