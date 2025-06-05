# ---
# Purpose:
#   Standardizes and corrects file and directory permissions across the application's
#   deployment path (/opt/thebarcodeapi). It ensures that:
#     - Necessary directories exist.
#     - The current user owns all application files and directories.
#     - Directories have 755 permissions (rwxr-xr-x).
#     - Regular files have 644 permissions (rw-r--r--).
#     - All .sh scripts within /opt/thebarcodeapi are executable (+x).
#     - Sensitive files like the backend .env file have stricter permissions (600: rw-------).
#     - Docker socket permissions are set (though this is often handled by group membership).
#
# Environment Variables (expected from /tmp/env_vars or direct pass for SUDO_PASSWORD):
#   - SUDO_PASSWORD: Password for sudo execution, as all commands modify system paths.
#   - ENVIRONMENT: The deployment environment (e.g., staging, production). Used for ensuring
#                  specific environment-related paths like backup and data directories exist.
#
# Outputs:
#   - Modifies permissions and ownership of files/directories under /opt/thebarcodeapi.
#   - Logs the process of fixing permissions.
# ---
#!/bin/bash
set -e

echo "Starting permission fixing process..."

# Attempt to source environment variables if /tmp/env_vars exists
if [ -f /tmp/env_vars ]; then
  source /tmp/env_vars
  echo "Sourced environment variables from /tmp/env_vars."
else
  echo "Warning: /tmp/env_vars not found. Relying on ENVIRONMENT and SUDO_PASSWORD being directly available."
fi

# Ensure critical variables are set
if [ -z "$SUDO_PASSWORD" ]; then
  echo "Error: SUDO_PASSWORD environment variable is not set."
  exit 1
fi
if [ -z "$ENVIRONMENT" ]; then # ENVIRONMENT is used for path creation
  echo "Error: ENVIRONMENT environment variable is not set."
  exit 1
fi

echo "Ensuring required directories exist for environment: ${ENVIRONMENT}..."
# These directories should ideally be created by more specific setup scripts (e.g., setup-docker-env.sh)
# but ensuring their existence here provides a fallback or verification.
echo "$SUDO_PASSWORD" | sudo -S mkdir -p "/opt/thebarcodeapi/barcodeApi"
echo "$SUDO_PASSWORD" | sudo -S mkdir -p "/opt/thebarcodeapi/${ENVIRONMENT}/releases/data" # For Docker volumes
echo "$SUDO_PASSWORD" | sudo -S mkdir -p "/opt/thebarcodeapi/${ENVIRONMENT}/backups"
echo "$SUDO_PASSWORD" | sudo -S mkdir -p "/opt/thebarcodeapi/${ENVIRONMENT}/current" # For frontend current release
echo "$SUDO_PASSWORD" | sudo -S mkdir -p "/opt/thebarcodeapi/${ENVIRONMENT}/logs"    # For frontend logs

# Set overall ownership for the application's root directory
# All subsequent specific ownerships are fine but this sets a baseline.
echo "Setting ownership of /opt/thebarcodeapi to ${USER}:${USER}..."
echo "$SUDO_PASSWORD" | sudo -S chown -R "${USER}:${USER}" "/opt/thebarcodeapi"

# Set standardized directory permissions (rwxr-xr-x)
echo "Setting directory permissions under /opt/thebarcodeapi to 755..."
echo "$SUDO_PASSWORD" | sudo -S find "/opt/thebarcodeapi" -type d -exec chmod 755 {} \;

# Set standardized file permissions (rw-r--r--)
echo "Setting file permissions under /opt/thebarcodeapi to 644 (excluding scripts)..."
echo "$SUDO_PASSWORD" | sudo -S find "/opt/thebarcodeapi" -type f -not -name "*.sh" -exec chmod 644 {} \;
# (Scripts are handled next)

# Make all .sh scripts within the application path executable
echo "Making all .sh scripts under /opt/thebarcodeapi executable (chmod +x)..."
echo "$SUDO_PASSWORD" | sudo -S find "/opt/thebarcodeapi" -name "*.sh" -exec chmod u+x,g+x,o+x {} \; # Equivalent to +x ensuring execute for all

# Ensure special, stricter permissions for sensitive files like the backend .env
BACKEND_ENV_FILE="/opt/thebarcodeapi/barcodeApi/.env"
echo "Checking permissions for sensitive file: ${BACKEND_ENV_FILE}..."
if [ -f "$BACKEND_ENV_FILE" ]; then
  echo "Setting permissions for ${BACKEND_ENV_FILE} to 600 (rw-------)..."
  echo "$SUDO_PASSWORD" | sudo -S chmod 600 "$BACKEND_ENV_FILE"
  echo "$SUDO_PASSWORD" | sudo -S chown "${USER}:${USER}" "$BACKEND_ENV_FILE" # Ensure owner is runner
else
  echo "Warning: Backend .env file ${BACKEND_ENV_FILE} not found. Skipping specific permission setting."
fi

# Set proper permissions for Docker socket.
# This is often handled by adding the current user to the 'docker' group during Docker installation.
# Manually setting it to 666 can be a security risk if the docker group mechanism is preferred and working.
DOCKER_SOCKET="/var/run/docker.sock"
echo "Checking permissions for Docker socket: ${DOCKER_SOCKET}..."
if [ -S "$DOCKER_SOCKET" ]; then # -S checks if it's a socket
  current_perms=$(stat -c "%a" "$DOCKER_SOCKET")
  current_group=$(stat -c "%G" "$DOCKER_SOCKET")
  if [ "$current_group" == "docker" ] && getent group docker | grep -q "\b${USER}\b"; then
    echo "User ${USER} is in docker group, and socket group is docker. Socket permissions should be managed by Docker daemon (typically 660)."
    # Optionally, ensure it's 660 if group is docker: sudo chmod 660 "$DOCKER_SOCKET"
  else
    echo "Warning: User ${USER} may not be in docker group or socket group is not 'docker'. Current perms: $current_perms."
    echo "Original workflow set Docker socket to 666. Retaining this for now, but review security implications."
    echo "$SUDO_PASSWORD" | sudo -S chmod 666 "$DOCKER_SOCKET"
  fi
else
  echo "Warning: Docker socket ${DOCKER_SOCKET} not found or is not a socket."
fi

# Redundant chowns if the top-level chown -R worked, but confirm specific important paths.
echo "Verifying ownership for specific sub-directories..."
echo "$SUDO_PASSWORD" | sudo -S chown -R "${USER}:${USER}" "/opt/thebarcodeapi/barcodeApi"
echo "$SUDO_PASSWORD" | sudo -S chown -R "${USER}:${USER}" "/opt/thebarcodeapi/${ENVIRONMENT}/backups"
echo "$SUDO_PASSWORD" | sudo -S chown -R "${USER}:${USER}" "/opt/thebarcodeapi/${ENVIRONMENT}/releases"
echo "$SUDO_PASSWORD" | sudo -S chown -R "${USER}:${USER}" "/opt/thebarcodeapi/${ENVIRONMENT}/current" # If it's a symlink, this affects the link itself
echo "$SUDO_PASSWORD" | sudo -S chown -R "${USER}:${USER}" "/opt/thebarcodeapi/${ENVIRONMENT}/logs"


echo "Permissions fixing process completed successfully."
