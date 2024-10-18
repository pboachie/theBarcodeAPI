#!/bin/bash

set -e # Exit on error

DEPLOY_DIR="/opt/thebarcodeapi"
RELEASE_DIR="${DEPLOY_DIR}/releases"
CURRENT_LINK="${DEPLOY_DIR}/current"
NEW_RELEASE="${RELEASE_DIR}/release-$(date +%Y%m%d%H%M%S)"
BUILD_DIR="./build"

# Create new release directory
sudo mkdir -p "${NEW_RELEASE}"

# Create the release and current directories if they don't exist
sudo mkdir -p "${RELEASE_DIR}"
sudo mkdir -p "${CURRENT_LINK}"

# Copy new files to release directory
sudo cp -R ${BUILD_DIR}/* "${NEW_RELEASE}"

# Switch to new release
sudo ln -sfn "${NEW_RELEASE}" "${CURRENT_LINK}"

# Remove old releases, keeping the last 5
cd "${RELEASE_DIR}" && ls -1dt */ | tail -n +6 | xargs sudo rm -rf

# Reload Nginx
sudo systemctl reload nginx

echo "Deployment completed successfully."