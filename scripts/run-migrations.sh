# ---
# Purpose:
#   Executes database migrations using Alembic within the running backend API container.
#   It determines the correct Docker Compose command and ensures the .env file
#   (which contains database connection details) has appropriate permissions before running migrations.
#
# Environment Variables (expected as input from the calling workflow):
#   - SUDO_PASSWORD: Password for sudo execution, as Docker Compose commands and chown/chmod
#                    might require sudo depending on the runner's setup.
#
# Outputs:
#   - Runs Alembic database migrations.
#   - Logs migration status.
#   - Exits with the status of the migration command (0 for success, non-zero for failure).
# ---
#!/bin/bash
set -e

# Ensure SUDO_PASSWORD is set
if [ -z "$SUDO_PASSWORD" ]; then
  echo "Error: SUDO_PASSWORD environment variable is not set."
  exit 1
fi

echo "Starting database migration process..."

# Navigate to the backend application directory
APP_DIR="/opt/thebarcodeapi/barcodeApi"
echo "Changing directory to ${APP_DIR}..."
cd "${APP_DIR}" || { echo "Error: Failed to change directory to ${APP_DIR}"; exit 1; }

# Always run docker-compose from the directory containing docker-compose.yml
if [ "$PWD" != "/opt/thebarcodeapi" ]; then
    echo "Switching to /opt/thebarcodeapi for docker-compose commands."
    cd /opt/thebarcodeapi || { echo "❌ Failed to cd to /opt/thebarcodeapi"; exit 1; }
fi

# Determine the correct docker compose command available on the system
if command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
else
  echo "Error: Neither 'docker-compose' nor 'docker compose' command found. Cannot run migrations."
  exit 1
fi
echo "Using Docker Compose command: $COMPOSE_CMD"

# Set permissions for the .env file.
# The API container, when running migrations, will need to read this file.
# The user/group (www-data:www-data) and permissions (644) should align with
# how the application inside the container accesses its environment variables if this .env is mounted or copied.
# Note: If .env is built into the image and not mounted, these host permissions are less critical for the container itself.
# However, other scripts or processes might rely on these permissions.
ENV_FILE_PATH="${APP_DIR}/.env"
echo "Setting permissions for .env file at ${ENV_FILE_PATH}..."
if [ -f "$ENV_FILE_PATH" ]; then
  echo "${SUDO_PASSWORD}" | sudo -S chown www-data:www-data "$ENV_FILE_PATH"
  echo "${SUDO_PASSWORD}" | sudo -S chmod 644 "$ENV_FILE_PATH"
  echo "Permissions set for ${ENV_FILE_PATH}."
else
  echo "Warning: ${ENV_FILE_PATH} not found. Migrations might fail if DB connection details are missing."
  # Depending on setup, the .env file might be created by a previous step (e.g. create-backend-env-file.sh)
  # or sourced directly by the container without a host-side .env file.
fi

# Run database migrations using Alembic.
# The command is executed inside the 'barcodeapi' service container.
# `-T` disables pseudo-tty allocation, suitable for non-interactive exec commands.
echo "Running Alembic database migrations..."
echo "${SUDO_PASSWORD}" | sudo -S $COMPOSE_CMD exec -T barcodeapi alembic upgrade head
MIGRATION_STATUS=$? # Capture the exit status of the migration command

# Check migration status and provide feedback
if [ $MIGRATION_STATUS -eq 0 ]; then
  echo "Database migrations completed successfully."
else
  echo "Error: Database migration failed with status ${MIGRATION_STATUS}."
  echo "Fetching recent logs from the 'barcodeapi' service for debugging..."
  echo "${SUDO_PASSWORD}" | sudo -S $COMPOSE_CMD logs --tail 50 barcodeapi # Show last 50 log lines from the barcodeapi container
fi

# Exit with the migration status, so GitHub Actions can correctly reflect success or failure
echo "Exiting with migration status: ${MIGRATION_STATUS}."
exit $MIGRATION_STATUS
