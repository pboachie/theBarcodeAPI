# ---
# Purpose:
#   Configures and starts the frontend application using PM2 process manager.
#   It involves:
#     - Creating necessary directories for the application and logs.
#     - Copying a templated PM2 ecosystem configuration file.
#     - Replacing placeholders (like __ENVIRONMENT__) in the ecosystem file with actual values.
#     - Managing the PM2 process: deleting any existing instance, flushing logs,
#       starting the new instance with the configured ecosystem file, and saving the PM2 state.
#
# Environment Variables (expected from /tmp/env_vars):
#   - ENVIRONMENT: The deployment environment (e.g., staging, production). Used for paths,
#                  PM2 app naming, and placeholder replacement in the ecosystem template.
#   - SUDO_PASSWORD: Password for sudo execution, used for directory creation, file copying,
#                    permission changes, and potentially by PM2 if it needs sudo for certain operations
#                    (though PM2 commands here are run as the runner user via PM2_HOME).
#
# Script Dependencies:
#   - scripts/infra/templates/ecosystem.config.js.template: The template for PM2 configuration.
#
# Outputs:
#   - Creates and configures the PM2 ecosystem file for the specified environment.
#   - Starts/restarts the frontend application via PM2.
#   - Logs the configuration and PM2 management process.
# ---
#!/bin/bash
set -e

echo "Starting PM2 configuration for frontend..."

# Attempt to source environment variables from /tmp/env_vars
# This file should be created by a preceding step in the GitHub Actions workflow.
if [ -f /tmp/env_vars ]; then
  source /tmp/env_vars
  echo "Sourced environment variables from /tmp/env_vars."
else
  echo "Error: /tmp/env_vars not found. Required variables (ENVIRONMENT, SUDO_PASSWORD) might be missing."
  exit 1
fi

# Ensure critical variables sourced from /tmp/env_vars are available
if [ -z "$ENVIRONMENT" ] || [ -z "$SUDO_PASSWORD" ]; then
  echo "Error: Key environment variables (ENVIRONMENT, SUDO_PASSWORD) from /tmp/env_vars are missing."
  exit 1
fi

# Define paths
APP_BASE_PATH="/opt/thebarcodeapi/${ENVIRONMENT}"
CURRENT_APP_PATH="${APP_BASE_PATH}/current" # Where the live application code is symlinked
LOGS_PATH="${APP_BASE_PATH}/logs"
ECOSYSTEM_TEMPLATE_PATH="scripts/infra/templates/ecosystem.config.js.template" # Relative to PWD of workflow
TARGET_ECOSYSTEM_CONFIG_PATH="${APP_BASE_PATH}/ecosystem.config.js"
PM2_APP_NAME="thebarcodeapi-frontend-${ENVIRONMENT}"

# The workflow's PWD should be the root of the repository checkout
# Verify template exists at the expected path from the PWD
if [ ! -f "$ECOSYSTEM_TEMPLATE_PATH" ]; then
    echo "Error: PM2 ecosystem template not found at ${PWD}/${ECOSYSTEM_TEMPLATE_PATH}"
    exit 1
fi

# Create required directories with proper permissions
echo "Creating required directories: ${CURRENT_APP_PATH}, ${LOGS_PATH}"
echo "$SUDO_PASSWORD" | sudo -S mkdir -p "${CURRENT_APP_PATH}"
echo "$SUDO_PASSWORD" | sudo -S mkdir -p "${LOGS_PATH}"
# github-runner should own the /opt/thebarcodeapi directory and its subdirectories for PM2 management and app files
echo "$SUDO_PASSWORD" | sudo -S chown -R github-runner:github-runner "/opt/thebarcodeapi"
echo "$SUDO_PASSWORD" | sudo -S chmod -R 755 "/opt/thebarcodeapi" # Ensure runner can rwx, others rx

# Configure PM2: Copy template and replace placeholders
echo "Configuring PM2 ecosystem file at ${TARGET_ECOSYSTEM_CONFIG_PATH}..."
echo "$SUDO_PASSWORD" | sudo -S cp "${PWD}/${ECOSYSTEM_TEMPLATE_PATH}" "${TARGET_ECOSYSTEM_CONFIG_PATH}"
echo "$SUDO_PASSWORD" | sudo -S sed -i "s/__ENVIRONMENT__/${ENVIRONMENT}/g" "${TARGET_ECOSYSTEM_CONFIG_PATH}"
echo "$SUDO_PASSWORD" | sudo -S chown github-runner:github-runner "${TARGET_ECOSYSTEM_CONFIG_PATH}"
echo "$SUDO_PASSWORD" | sudo -S chmod 644 "${TARGET_ECOSYSTEM_CONFIG_PATH}" # Readable by all, writable by owner

# PM2 process management
# PM2_HOME must be set to the home directory of the user that will run PM2 (github-runner).
PM2_RUN_CMD="PM2_HOME=/home/github-runner/.pm2 pm2"

echo "Managing PM2 process: ${PM2_APP_NAME}..."
# Delete existing process if it's running to ensure a clean start/reload
echo "Attempting to delete existing PM2 process: ${PM2_APP_NAME} (if any)..."
$PM2_RUN_CMD delete "${PM2_APP_NAME}" || echo "PM2 process ${PM2_APP_NAME} not found or already stopped. This is fine."

# Wait for processes to fully stop (PM2 delete can be asynchronous)
echo "Waiting for PM2 process to fully stop (10 seconds)..."
sleep 10

# Clear PM2 logs before starting to ensure fresh logs for the new instance
echo "Flushing PM2 logs..."
$PM2_RUN_CMD flush || echo "Warning: PM2 flush command failed. Logs might not be cleared."

# Start PM2 with the new configuration
# The ecosystem file's `cwd` directive points to CURRENT_APP_PATH.
# PM2 needs read access to the ecosystem file.
echo "Starting PM2 process ${PM2_APP_NAME} with configuration: ${TARGET_ECOSYSTEM_CONFIG_PATH}"
$PM2_RUN_CMD start "${TARGET_ECOSYSTEM_CONFIG_PATH}"
if [ $? -ne 0 ]; then
    echo "Error: PM2 start command failed for ${TARGET_ECOSYSTEM_CONFIG_PATH}."
    $PM2_RUN_CMD logs --lines 50 # Show all PM2 logs if start fails
    exit 1
fi

# Wait for the process to stabilize after starting
echo "Waiting for PM2 process to stabilize (10 seconds)..."
sleep 10

# Save the current PM2 process list to allow resurrection on server reboot
echo "Saving PM2 process list..."
$PM2_RUN_CMD save --force # --force ensures it overwrites if a save file already exists
echo "PM2 process status after start/save:"
$PM2_RUN_CMD list

# Final permissions check for the application base path (already set, but good for verification)
echo "Verifying final permissions for /opt/thebarcodeapi..."
echo "$SUDO_PASSWORD" | sudo -S chown -R github-runner:github-runner "/opt/thebarcodeapi"
echo "$SUDO_PASSWORD" | sudo -S chmod -R 755 "/opt/thebarcodeapi" # Ensure scripts inside are executable if needed by PM2

# Show recent logs from the application for debugging purposes
echo "Recent application logs from PM2 for ${PM2_APP_NAME}:"
# The log paths are defined in the ecosystem.config.js template.
# Accessing them directly via sudo as they might be owned by root or another user if PM2 runs differently.
ERROR_LOG_PATH="${LOGS_PATH}/err.log" # Path from ecosystem template
OUT_LOG_PATH="${LOGS_PATH}/out.log"   # Path from ecosystem template

if [ -f "$ERROR_LOG_PATH" ]; then
  echo "Error Log (${ERROR_LOG_PATH}):"
  sudo tail -n 30 "$ERROR_LOG_PATH" || echo "Could not read error log."
else
  echo "Error log file not found at $ERROR_LOG_PATH."
fi
if [ -f "$OUT_LOG_PATH" ]; then
  echo "Output Log (${OUT_LOG_PATH}):"
  sudo tail -n 30 "$OUT_LOG_PATH" || echo "Could not read output log."
else
  echo "Output log file not found at $OUT_LOG_PATH."
fi

echo "PM2 configuration and application start process complete."
