#!/bin/bash
set -e # Exit on error

# Define absolute paths
DEPLOY_DIR="/opt/thebarcodeapi"
RELEASE_DIR="${DEPLOY_DIR}/releases"
CURRENT_LINK="${DEPLOY_DIR}/current"
BUILD_DIR="$(pwd)/build"

# Create new release directory
mkdir -p "${RELEASE_DIR}"
NEW_RELEASE="${RELEASE_DIR}/release-$(date +%Y%m%d%H%M%S)"
mkdir -p "${NEW_RELEASE}"

# Copy new files to release directory
cp -R "${BUILD_DIR}/." "${NEW_RELEASE}/"

# Switch to new release
ln -sfn "${NEW_RELEASE}" "${CURRENT_LINK}"

# Remove old releases, keeping the last 5
cd "${RELEASE_DIR}" && ls -1dt */ | tail -n +6 | xargs rm -rf

# Reload Nginx
systemctl reload nginx

echo "Deployment completed successfully."