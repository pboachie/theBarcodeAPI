# ---
# Purpose:
#   Sets up the complete Docker environment for the backend application. This includes:
#     - Creating necessary directories for the application, Docker volumes (data, backups), and releases.
#     - Copying backend application files from the workflow's checkout path to the deployment directory.
#     - Templating and creating essential configuration files from templates:
#       - `.env`: For backend service environment variables (database credentials, API keys, etc.).
#       - `docker-compose.yml`: For defining and managing multi-container Docker services.
#       - `backup.sh`: A script for backing up database and Redis data.
#       - `wait-for-it.sh`: A utility script to wait for services to be available.
#     - Setting appropriate permissions and ownership for all created files and directories.
#
# Environment Variables (expected from /tmp/env_vars):
#   - SUDO_PASSWORD: Password for sudo execution, used for all file/directory operations and permission changes.
#   - ENVIRONMENT: The deployment environment (e.g., staging, production), used for path creation and templating.
#   - DB_PASSWORD, POSTGRES_PASSWORD, API_SECRET_KEY, API_MASTER_KEY, API_VERSION:
#     Used for replacing placeholders in the .env and docker-compose.yml templates.
#
# Script Dependencies:
#   - scripts/infra/templates/backend.env.template
#   - scripts/infra/templates/docker-compose.yml.template
#   - scripts/infra/templates/backup.sh.template
#   - scripts/infra/templates/wait-for-it.sh.template
#   The script also expects the main backend application code (barcodeAPI directory) to be present
#   in the GitHub Actions workflow's checkout path.
#
# Outputs:
#   - A fully configured backend application directory (/opt/thebarcodeapi/barcodeAPI) ready for Docker Compose.
#   - Necessary scripts (backup.sh, wait-for-it.sh) placed within this directory.
#   - Logs the setup process.
# ---
#!/bin/bash
set -e

echo "Starting backend Docker environment setup..."

# Attempt to source environment variables from /tmp/env_vars
if [ -f /tmp/env_vars ]; then
  source /tmp/env_vars
  echo "Sourced environment variables from /tmp/env_vars."
else
  echo "Error: /tmp/env_vars not found. This script requires numerous variables from it."
  exit 1
fi

# Ensure all critical variables sourced from /tmp/env_vars are available
REQUIRED_VARS=(
    "SUDO_PASSWORD" "ENVIRONMENT" "DB_PASSWORD" "POSTGRES_PASSWORD"
    "API_SECRET_KEY" "API_MASTER_KEY" "API_VERSION"
)
for var_name in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var_name}" ]; then
    echo "Error: Critical environment variable ${var_name} from /tmp/env_vars is missing."
    exit 1
  fi
done

# Define base paths
APP_DEPLOY_BASE_PATH="/opt/thebarcodeapi"
BACKEND_APP_PATH="${APP_DEPLOY_BASE_PATH}/barcodeAPI"
ENV_SPECIFIC_DATA_PATH="${APP_DEPLOY_BASE_PATH}/${ENVIRONMENT}" # For releases, data volumes, backups

# Path to the checked-out code in the GitHub Actions runner workspace.
# This path might need to be passed as an argument or discovered if it's not fixed.
# Defaulting to a common structure.
WORKFLOW_CHECKOUT_PATH="${GITHUB_WORKSPACE:-/home/github-runner/actions-runner/_work/theBarcodeAPI/theBarcodeAPI}"
SOURCE_BACKEND_CODE_PATH="${WORKFLOW_CHECKOUT_PATH}/barcodeAPI"
SOURCE_TEMPLATES_PATH="${WORKFLOW_CHECKOUT_PATH}/scripts/infra/templates"

echo "Ensuring necessary directories exist for environment: ${ENVIRONMENT}..."
echo "$SUDO_PASSWORD" | sudo -S mkdir -p "${BACKEND_APP_PATH}"
echo "$SUDO_PASSWORD" | sudo -S mkdir -p "${ENV_SPECIFIC_DATA_PATH}/releases" # General releases, not just frontend
echo "$SUDO_PASSWORD" | sudo -S mkdir -p "${ENV_SPECIFIC_DATA_PATH}/releases/data/postgres" # Postgres Docker volume data
echo "$SUDO_PASSWORD" | sudo -S mkdir -p "${ENV_SPECIFIC_DATA_PATH}/releases/data/redis"    # Redis Docker volume data
echo "$SUDO_PASSWORD" | sudo -S mkdir -p "${ENV_SPECIFIC_DATA_PATH}/backups"

# Navigate to the main backend application deployment directory
echo "Changing directory to ${BACKEND_APP_PATH}..."
cd "${BACKEND_APP_PATH}" || { echo "Error: Failed to change directory to ${BACKEND_APP_PATH}"; exit 1; }

# Copy backend application files from the source checkout to the deployment directory
echo "Copying backend application files from ${SOURCE_BACKEND_CODE_PATH} to ${BACKEND_APP_PATH}..."
if [ -d "${SOURCE_BACKEND_CODE_PATH}" ]; then
    # Using rsync for more robust copy, e.g., handling symlinks better, more options if needed.
    # sudo rsync -av --delete "${SOURCE_BACKEND_CODE_PATH}/" . # Alternative
    echo "$SUDO_PASSWORD" | sudo -S cp -Rpf "${SOURCE_BACKEND_CODE_PATH}/"* . # -p preserves mode,ownership,timestamps; -f forces overwrite
else
    echo "Error: Source backend code directory ${SOURCE_BACKEND_CODE_PATH} not found."
    ls -la "${WORKFLOW_CHECKOUT_PATH}" # List checkout path for debugging
    exit 1
fi

# --- Template and Configure Essential Files ---
echo "Templating configuration files..."

# Create .env file from template
echo "  Creating .env file from template: ${SOURCE_TEMPLATES_PATH}/backend.env.template"
echo "$SUDO_PASSWORD" | sudo -S cp "${SOURCE_TEMPLATES_PATH}/backend.env.template" ".env"
echo "$SUDO_PASSWORD" | sudo -S sed -i "s/__DB_PASSWORD__/${DB_PASSWORD}/g" ".env"
echo "$SUDO_PASSWORD" | sudo -S sed -i "s/__POSTGRES_PASSWORD__/${POSTGRES_PASSWORD}/g" ".env"
echo "$SUDO_PASSWORD" | sudo -S sed -i "s/__API_SECRET_KEY__/${API_SECRET_KEY}/g" ".env"
echo "$SUDO_PASSWORD" | sudo -S sed -i "s/__API_MASTER_KEY__/${API_MASTER_KEY}/g" ".env"
echo "$SUDO_PASSWORD" | sudo -S sed -i "s/__API_VERSION__/${API_VERSION}/g" ".env"
echo "$SUDO_PASSWORD" | sudo -S sed -i "s/__ENVIRONMENT__/${ENVIRONMENT}/g" ".env"
echo "$SUDO_PASSWORD" | sudo -S chmod 600 ".env" # Restrict permissions: only owner can read/write
echo "$SUDO_PASSWORD" | sudo -S chown $USER:$USER ".env"

# Create docker-compose.yml from template
echo "  Creating docker-compose.yml from template: ${SOURCE_TEMPLATES_PATH}/docker-compose.yml.template"
echo "$SUDO_PASSWORD" | sudo -S cp "${SOURCE_TEMPLATES_PATH}/docker-compose.yml.template" "docker-compose.yml"
echo "$SUDO_PASSWORD" | sudo -S sed -i "s/__ENVIRONMENT__/${ENVIRONMENT}/g" "docker-compose.yml"
echo "$SUDO_PASSWORD" | sudo -S sed -i "s/__POSTGRES_PASSWORD__/${POSTGRES_PASSWORD}/g" "docker-compose.yml"
echo "$SUDO_PASSWORD" | sudo -S sed -i "s/__DB_PASSWORD__/${DB_PASSWORD}/g" "docker-compose.yml"
echo "$SUDO_PASSWORD" | sudo -S chown $USER:$USER "docker-compose.yml"
echo "$SUDO_PASSWORD" | sudo -S chmod 644 "docker-compose.yml" # Readable by all

# Create backup.sh from template
echo "  Creating backup.sh from template: ${SOURCE_TEMPLATES_PATH}/backup.sh.template"
echo "$SUDO_PASSWORD" | sudo -S cp "${SOURCE_TEMPLATES_PATH}/backup.sh.template" "backup.sh"
echo "$SUDO_PASSWORD" | sudo -S sed -i "s/__ENVIRONMENT__/${ENVIRONMENT}/g" "backup.sh"
# Inject SUDO_PASSWORD into the backup script if it needs to run sudo commands internally
# This is generally not ideal; better to grant specific NOPASSWD sudo rights if possible.
# The original template for backup.sh uses `echo "$SUDO_PASSWORD" | sudo -S cp ...`
# So, the SUDO_PASSWORD variable needs to be available inside backup.sh.
# One way is to embed it, another is that backup.sh sources /tmp/env_vars itself.
# Current backup.sh template does: echo "$SUDO_PASSWORD" | sudo -S cp ...
# This means the SUDO_PASSWORD variable is literally "$SUDO_PASSWORD" string.
# It should be: echo "${SUDO_PASSWORD}" | sudo -S cp ...
# The sed command below tries to fix this if the template has the literal "$SUDO_PASSWORD".
echo "$SUDO_PASSWORD" | sudo -S sed -i "s/echo \"\\\$SUDO_PASSWORD\"/echo \"${SUDO_PASSWORD}\"/g" "backup.sh"
echo "$SUDO_PASSWORD" | sudo -S chmod +x "backup.sh"
echo "$SUDO_PASSWORD" | sudo -S chown $USER:$USER "backup.sh"

# Create wait-for-it.sh from template
echo "  Creating wait-for-it.sh from template: ${SOURCE_TEMPLATES_PATH}/wait-for-it.sh.template"
echo "$SUDO_PASSWORD" | sudo -S cp "${SOURCE_TEMPLATES_PATH}/wait-for-it.sh.template" "wait-for-it.sh"
echo "$SUDO_PASSWORD" | sudo -S chmod +x "wait-for-it.sh"
echo "$SUDO_PASSWORD" | sudo -S chown $USER:$USER "wait-for-it.sh"

# Ensure start.sh (copied from source repo) is executable
# This script is typically used as the CMD or ENTRYPOINT in the Dockerfile.
echo "Ensuring start.sh is executable..."
if [ -f "./start.sh" ]; then
    echo "$SUDO_PASSWORD" | sudo -S chmod +x "./start.sh"
else
    echo "Warning: start.sh not found in ${BACKEND_APP_PATH}/. It might be part of the Docker image already."
fi

# Set final overall permissions for the application deployment directory
# This ensures the github-runner user owns everything and has appropriate execution rights.
echo "Setting final permissions for ${APP_DEPLOY_BASE_PATH}..."
echo "$SUDO_PASSWORD" | sudo -S chown -R $USER:$USER "${APP_DEPLOY_BASE_PATH}"
# Set base backend app path to 755, scripts inside should already be +x
echo "$SUDO_PASSWORD" | sudo -S chmod -R 755 "${BACKEND_APP_PATH}"
# Re-ensure .env has strict permissions after chmod -R
if [ -f "${BACKEND_APP_PATH}/.env" ]; then
    echo "$SUDO_PASSWORD" | sudo -S chmod 600 "${BACKEND_APP_PATH}/.env"
fi

echo "Backend Docker environment setup completed successfully."
