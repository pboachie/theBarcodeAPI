#!/bin/bash

# Set variables
DEPLOY_DIR="/opt/thebarcodeapi"
RELEASE_DIR="${DEPLOY_DIR}/releases"
CURRENT_LINK="${DEPLOY_DIR}/current"
UNUQUE_ID=$(date +%s)
NEW_RELEASE="${RELEASE_DIR}/$(date +%Y%m%d%H%M%S"+${UNUQUE_ID}")"

# Create new release directory
mkdir -p "${NEW_RELEASE}"

# Copy new files to release directory
cp -R build/* "${NEW_RELEASE}"

# Switch to new release
ln -sfn "${NEW_RELEASE}" "${CURRENT_LINK}"

# Remove old releases, keeping the last 5
cd "${RELEASE_DIR}" && ls -1dt */ | tail -n +6 | xargs rm -rf

# Reload web server (adjust as needed)
sudo systemctl reload nginx