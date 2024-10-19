#!/bin/bash

set -e

echo "Starting deployment..."

# Create releases directory
mkdir -p /opt/thebarcodeapi/releases

# Create new release directory
NEW_RELEASE="/opt/thebarcodeapi/releases/release-$(date +%Y%m%d%H%M%S)"
echo "Creating new release directory: $NEW_RELEASE"
mkdir -p "$NEW_RELEASE"

# Copy build files
echo "Copying build files to new release directory"
cp -R /home/github-runner/actions-runner/_work/theBarcodeAPI/theBarcodeAPI/build/. "$NEW_RELEASE/"

# Update symlink
echo "Creating symlink to new release"
ln -sfn "$NEW_RELEASE" /opt/thebarcodeapi/current

# Clean up old releases
echo "Cleaning up old releases"
cd /opt/thebarcodeapi/releases && ls -1dt */ | tail -n +6 | xargs rm -rf

# Reload nginx
echo "Reloading nginx"
systemctl reload nginx

# Change ownership
echo "Changing ownership of /opt/thebarcodeapi"
chown -R www-data:www-data /opt/thebarcodeapi

echo "Deployment completed"