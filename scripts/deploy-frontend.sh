# ---
# Purpose:
#   Manages the deployment of the Next.js frontend application.
#   If changes are detected (via $STEPS_CHECK_FRONTEND_CHANGES_OUTPUTS_CHANGES), it creates a new release
#   directory, copies build artifacts (from .next, public, package files), installs production dependencies,
#   updates symlinks (/opt/thebarcodeapi/${ENVIRONMENT}/current), and cleans up old releases.
#   It then (re)starts the application using PM2 and performs a health check.
#   If the health check fails, it attempts to roll back to the previous release.
#
# Environment Variables (expected as input from the calling workflow):
#   - ENVIRONMENT: The deployment environment (e.g., staging, production). Used for paths and PM2 app name.
#   - SUDO_PASSWORD: Password for sudo execution, used for directory operations, chown, chmod, and symlinking.
#   - STEPS_CHECK_FRONTEND_CHANGES_OUTPUTS_CHANGES: A boolean-like string ("true" or "false") indicating
#     if code changes were detected by a preceding step (e.g., check-frontend-changes.sh).
#
# Outputs:
#   - Deploys the frontend application to the server.
#   - Manages PM2 process for the frontend.
#   - Logs deployment progress, health check status, and errors.
#   - Exits with an error if deployment, health checks, or rollback fails.
# ---
#!/bin/bash
set -e

# Dynamic PM2_HOME detection
if [ "$USER" = "root" ]; then
    PM2_HOME_DIR="/root/.pm2"
else
    PM2_HOME_DIR="${HOME:-/home/$USER}/.pm2"
fi

# Ensure critical variables are set
if [ -z "$ENVIRONMENT" ] || [ -z "$SUDO_PASSWORD" ] || [ -z "$STEPS_CHECK_FRONTEND_CHANGES_OUTPUTS_CHANGES" ]; then
  echo "Error: Required environment variables (ENVIRONMENT, SUDO_PASSWORD, STEPS_CHECK_FRONTEND_CHANGES_OUTPUTS_CHANGES) are not set."
  exit 1
fi

echo "Starting frontend deployment for environment: ${ENVIRONMENT}"
echo "Changes detected: ${STEPS_CHECK_FRONTEND_CHANGES_OUTPUTS_CHANGES}"

# Store current commit hash in the build workspace (this will be copied to the release).
# This helps in tracking what commit is in which release.
echo "Storing current commit hash..."
git rev-parse HEAD > .git-commit

# Function for health check against the locally running frontend application
check_health() {
  local url="http://localhost:3000" # Assuming frontend runs on port 3000
  local max_workers=2 # Number of PM2 instances (or conceptual workers)
  local seconds_per_worker=30 # Time allocated per worker for startup
  # Max attempts for curl, derived from total time allowed for workers to start, checking every 5 seconds
  local max_attempts=$((seconds_per_worker * max_workers / 5))

  echo "Starting health check for ${url}... Will try $max_attempts times (${seconds_per_worker}s per worker, total ${max_attempts}*5s)."

  for i in $(seq 1 $max_attempts); do
    # Use curl to check if the frontend is responding successfully (HTTP 2xx)
    if curl -s -f -m 5 "$url" > /dev/null; then # -s silent, -f fail fast, -m 5s timeout
      echo "Health check passed on attempt $i for ${url}."
      return 0 # Success
    fi
    echo "Health check attempt $i/$max_attempts for ${url} failed..."

    # Log PM2 status and recent app logs periodically during health check failures for debugging
    if [ $((i % 5)) -eq 0 ]; then # Every 5 attempts (25 seconds)
      echo "Current PM2 status:"
      PM2_HOME="${PM2_HOME_DIR}" pm2 list # Ensure PM2_HOME is set if runner user is different
      echo "Recent logs for thebarcodeapi-frontend-${ENVIRONMENT}:"
      PM2_HOME="${PM2_HOME_DIR}" pm2 logs "thebarcodeapi-frontend-${ENVIRONMENT}" --lines 20 --nostream
    fi
    sleep 5 # Wait before retrying
  done

  echo "Health check failed for ${url} after $max_attempts attempts."
  echo "Final PM2 status:"
  PM2_HOME="${PM2_HOME_DIR}" pm2 list
  echo "Recent logs for thebarcodeapi-frontend-${ENVIRONMENT} (last 50 lines):"
  PM2_HOME="${PM2_HOME_DIR}" pm2 logs "thebarcodeapi-frontend-${ENVIRONMENT}" --lines 50 --nostream
  return 1 # Failure
}

# Base directories for application deployment
APP_BASE_PATH="/opt/thebarcodeapi/${ENVIRONMENT}"
RELEASES_PATH="${APP_BASE_PATH}/releases"
CURRENT_LINK_PATH="${APP_BASE_PATH}/current" # Symlink to the current release
PREVIOUS_RELEASE_LINK="${APP_BASE_PATH}/previous" # Symlink to the previous release (for rollback)

# Ensure base directories exist with proper permissions (runner should own /opt/thebarcodeapi for creating subdirs)
echo "Ensuring base directories exist: ${RELEASES_PATH}, ${CURRENT_LINK_PATH}"
echo "${SUDO_PASSWORD}" | sudo -S mkdir -p "${RELEASES_PATH}" # -p creates parent dirs if they don't exist
echo "${SUDO_PASSWORD}" | sudo -S chown -R "${USER}:${USER}" "/opt/thebarcodeapi" # Runner owns the top dir

# Deployment steps if changes are detected
if [ "${STEPS_CHECK_FRONTEND_CHANGES_OUTPUTS_CHANGES}" == "true" ]; then
  echo "Changes detected, proceeding with new release creation."
  TIMESTAMP=$(date +%Y%m%d%H%M%S)
  NEW_RELEASE_PATH="${RELEASES_PATH}/release-${TIMESTAMP}"

  echo "Creating new release directory: ${NEW_RELEASE_PATH}"
  echo "${SUDO_PASSWORD}" | sudo -S mkdir -p "${NEW_RELEASE_PATH}"

  echo "Copying build artifacts to new release directory..."
  # Copy Next.js build output, public assets, package files, and the .git-commit file
  echo "${SUDO_PASSWORD}" | sudo -S cp -R ./barcodeFrontend/.next "${NEW_RELEASE_PATH}/"
  echo "${SUDO_PASSWORD}" | sudo -S cp -R ./barcodeFrontend/public "${NEW_RELEASE_PATH}/"
  echo "${SUDO_PASSWORD}" | sudo -S cp ./barcodeFrontend/package.json ./barcodeFrontend/package-lock.json ./.git-commit "${NEW_RELEASE_PATH}/"

  # Set ownership and basic permissions for the new release (runner needs to install deps)
  echo "${SUDO_PASSWORD}" | sudo -S chown -R "${USER}:${USER}" "${NEW_RELEASE_PATH}"
  echo "${SUDO_PASSWORD}" | sudo -S chmod -R 755 "${NEW_RELEASE_PATH}" # Read/execute for all, write for owner

  echo "Installing production dependencies in new release directory..."
  cd "${NEW_RELEASE_PATH}" || { echo "Error: Failed to cd into ${NEW_RELEASE_PATH}"; exit 1; }
  # Install only production dependencies to keep the release lean
  npm ci --omit=dev
  if [ $? -ne 0 ]; then
    echo "Error: npm ci --omit=dev failed in ${NEW_RELEASE_PATH}"
    exit 1
  fi
  cd - # Return to previous directory (workflow workspace)

  # Symlink management for atomic deployments
  echo "Updating symlinks for new release..."
  # If CURRENT_DIR is a real directory (not a symlink, e.g., first deployment manually copied)
  if [ -d "${CURRENT_LINK_PATH}" ] && [ ! -L "${CURRENT_LINK_PATH}" ]; then
    echo "Warning: ${CURRENT_LINK_PATH} is a directory, not a symlink. Converting..."
    # Move its content to a release-like directory to preserve it as a potential 'previous' version
    if [ -d "${CURRENT_LINK_PATH}/.next" ] || [ -d "${CURRENT_LINK_PATH}/public" ]; then # Check if it looks like a valid app
      INITIAL_RELEASE_PATH="${RELEASES_PATH}/initial-release-$(date +%s)"
      echo "Moving content of ${CURRENT_LINK_PATH} to ${INITIAL_RELEASE_PATH}"
      echo "${SUDO_PASSWORD}" | sudo -S mv "${CURRENT_LINK_PATH}" "${INITIAL_RELEASE_PATH}"
      echo "Linking ${INITIAL_RELEASE_PATH} as previous release: ${PREVIOUS_RELEASE_LINK}"
      echo "${SUDO_PASSWORD}" | sudo -S ln -sfn "${INITIAL_RELEASE_PATH}" "${PREVIOUS_RELEASE_LINK}"
    else
      # If not a valid app, just remove it to make way for the symlink
      echo "Removing non-symlink ${CURRENT_LINK_PATH} as it does not appear to be a valid deployment."
      echo "${SUDO_PASSWORD}" | sudo -S rm -rf "${CURRENT_LINK_PATH}"
    fi
  # If CURRENT_DIR is already a symlink and points to an existing release
  elif [ -L "${CURRENT_LINK_PATH}" ] && [ -e "${CURRENT_LINK_PATH}" ]; then
    CURRENT_ACTUAL_RELEASE=$(readlink -f "${CURRENT_LINK_PATH}")
    echo "Current release is ${CURRENT_ACTUAL_RELEASE}. Setting it as previous: ${PREVIOUS_RELEASE_LINK}"
    echo "${SUDO_PASSWORD}" | sudo -S ln -sfn "${CURRENT_ACTUAL_RELEASE}" "${PREVIOUS_RELEASE_LINK}"
  fi

  # Final permissions for the new release (web server user www-data needs to read files)
  echo "Setting final permissions for new release: ${NEW_RELEASE_PATH}"
  echo "${SUDO_PASSWORD}" | sudo -S chown -R www-data:www-data "${NEW_RELEASE_PATH}" # Nginx/Apache user
  echo "${SUDO_PASSWORD}" | sudo -S chmod -R 755 "${NEW_RELEASE_PATH}" # Ensure readability

  # Atomically switch the 'current' symlink to the new release
  echo "Activating new release: linking ${NEW_RELEASE_PATH} to ${CURRENT_LINK_PATH}"
  echo "${SUDO_PASSWORD}" | sudo -S ln -sfn "${NEW_RELEASE_PATH}" "${CURRENT_LINK_PATH}"

  # Cleanup old releases (keep last 3)
  echo "Cleaning up old releases in ${RELEASES_PATH} (keeping last 3)..."
  cd "${RELEASES_PATH}" || { echo "Error: Failed to cd into ${RELEASES_PATH} for cleanup"; exit 1; }
  # List directories by modification time (newest first), skip first 3, delete rest
  echo "${SUDO_PASSWORD}" | sudo -S ls -1dt release-*/ | tail -n +4 | xargs -r rm -rf
  cd - # Return to previous directory
else
  echo "No frontend changes detected. Skipping new release creation."
fi

# PM2 process management
# PM2_HOME needs to be set for the user running PM2
PM2_APP_NAME="thebarcodeapi-frontend-${ENVIRONMENT}"
PM2_ECOSYSTEM_CONFIG="${APP_BASE_PATH}/ecosystem.config.js" # This file should be created by infra-ci.yml

echo "Managing PM2 process: ${PM2_APP_NAME}"
if ! PM2_HOME="${PM2_HOME_DIR}" pm2 list | grep -q "${PM2_APP_NAME}"; then
  echo "PM2 process ${PM2_APP_NAME} not found. Starting new instance..."
  # Ensure current directory exists for PM2 CWD, though actual CWD is in ecosystem file
  if [ ! -d "${CURRENT_LINK_PATH}" ]; then
    echo "Error: Current application directory ${CURRENT_LINK_PATH} does not exist. Cannot start PM2."
    exit 1
  fi
  # PM2 start command needs to be run from a directory that makes sense if ecosystem paths are relative,
  # or use absolute paths in ecosystem file. CWD for app is set in ecosystem.config.js.
  # Infra setup should ensure ecosystem.config.js is in ${APP_BASE_PATH}
  if [ ! -f "${PM2_ECOSYSTEM_CONFIG}" ]; then
      echo "Error: PM2 ecosystem config file not found at ${PM2_ECOSYSTEM_CONFIG}"
      exit 1
  fi
  PM2_HOME="${PM2_HOME_DIR}" pm2 start "${PM2_ECOSYSTEM_CONFIG}"
else
  echo "PM2 process ${PM2_APP_NAME} found. Reloading..."
  PM2_HOME="${PM2_HOME_DIR}" pm2 reload "${PM2_APP_NAME}" --update-env # Reloads with 0 downtime
fi
# Save current PM2 process list to be resurrected on reboot
PM2_HOME="${PM2_HOME_DIR}" pm2 save --force
echo "PM2 process status:"
PM2_HOME="${PM2_HOME_DIR}" pm2 list

# Health check and rollback if needed
echo "Performing post-deployment health check..."
if ! check_health; then
  echo "Health check failed after deployment/reload. Attempting rollback..."
  if [ -L "$PREVIOUS_RELEASE_LINK" ] && [ -e "$PREVIOUS_RELEASE_LINK" ]; then
    PREVIOUS_ACTUAL_RELEASE=$(readlink -f "$PREVIOUS_RELEASE_LINK")
    echo "Rolling back to previous release: ${PREVIOUS_ACTUAL_RELEASE}"
    echo "${SUDO_PASSWORD}" | sudo -S ln -sfn "${PREVIOUS_ACTUAL_RELEASE}" "${CURRENT_LINK_PATH}"

    echo "Restarting PM2 process for rollback..."
    PM2_HOME="${PM2_HOME_DIR}" pm2 reload "${PM2_APP_NAME}" --update-env
    PM2_HOME="${PM2_HOME_DIR}" pm2 save --force

    echo "Performing health check after rollback..."
    if ! check_health; then
      echo "CRITICAL: Rollback failed! Site may be down. Manual intervention required."
      PM2_HOME="${PM2_HOME_DIR}" pm2 list
      PM2_HOME="${PM2_HOME_DIR}" pm2 logs "${PM2_APP_NAME}" --lines 100 --nostream
      exit 1 # Critical failure
    fi
    echo "Rollback to ${PREVIOUS_ACTUAL_RELEASE} successful, but the new deployment failed."
    exit 1 # Indicate that the original deployment failed despite successful rollback
  else
    echo "Error: No previous release available for rollback at ${PREVIOUS_RELEASE_LINK}. Site may be down."
    exit 1 # Critical failure, no rollback path
  fi
fi

echo "Frontend deployment successful and health check passed!"