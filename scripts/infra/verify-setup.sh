# ---
# Purpose:
#   Verifies the overall infrastructure setup after all other infra scripts have run.
#   It performs checks for:
#     - Existence and basic permissions of key directories.
#     - Existence and executability of critical operational scripts (backup, pre-backup, cleanup, wait-for-it).
#     - Apparent installation of cron jobs (by checking crontab output).
#     - Basic file permissions, including stricter permissions for sensitive files like .env.
#   This script consolidates checks previously done in "Error Check" and "Verify Setup" steps.
#
# Environment Variables (expected from /tmp/env_vars or direct pass for SUDO_PASSWORD):
#   - SUDO_PASSWORD: Password for sudo execution, as many checks involve sudo (e.g., crontab -l, stat).
#   - ENVIRONMENT: The deployment environment (e.g., staging, production), used for constructing
#                  paths to environment-specific directories.
#
# Outputs:
#   - Logs the verification process for various components of the infrastructure.
#   - Exits with an error if critical scripts are missing or not executable.
#   - Issues warnings if cron jobs don't appear to be installed or if .env permissions are not as expected.
# ---
#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "Starting infrastructure setup verification..."

# Attempt to source environment variables
echo "Attempting to source environment variables for setup verification..."
ENV_FILE_SOURCED=false
if [ -n "${GLOBAL_ENV_VARS_FILE}" ] && [ -f "${GLOBAL_ENV_VARS_FILE}" ]; then
  source "${GLOBAL_ENV_VARS_FILE}"
  echo "Sourced environment variables from ${GLOBAL_ENV_VARS_FILE} (via GLOBAL_ENV_VARS_FILE env var)."
  ENV_FILE_SOURCED=true
elif [ -f /tmp/env_vars ]; then
  source /tmp/env_vars
  echo "Sourced environment variables from /tmp/env_vars (fallback)."
  ENV_FILE_SOURCED=true
fi

if [ "$ENV_FILE_SOURCED" = false ]; then
  echo "Warning: Environment variable file not found. Neither GLOBAL_ENV_VARS_FILE (env var: '${GLOBAL_ENV_VARS_FILE}') was valid nor /tmp/env_vars existed. Relying on ENVIRONMENT and SUDO_PASSWORD being directly available."
fi

# Ensure critical variables are set
if [ -z "$SUDO_PASSWORD" ]; then
  echo "Error: SUDO_PASSWORD environment variable is not set."
  exit 1
fi
if [ -z "$ENVIRONMENT" ]; then
  echo "Error: ENVIRONMENT environment variable is not set."
  exit 1
fi

# Function to ensure a directory exists with basic expected ownership and permissions.
# More thorough permission checks are done by fix-permissions.sh; this is a basic existence check.
ensure_directory_exists() {
  local dir_path="$1"
  echo -n "Verifying directory: ${dir_path}... "
  if [ ! -d "$dir_path" ]; then
    echo "NOT FOUND. Attempting to create..."
    # This creation is a fallback; directories should ideally be created by their respective setup scripts.
    echo "$SUDO_PASSWORD" | sudo -S mkdir -p "$dir_path"
    echo "$SUDO_PASSWORD" | sudo -S chown github-runner:github-runner "$dir_path"
    echo "$SUDO_PASSWORD" | sudo -S chmod 755 "$dir_path"
    echo "CREATED."
  else
    echo "Found."
  fi
}

# --- Directory Structure Verification ---
echo "Verifying essential directory structure for environment: ${ENVIRONMENT}..."
ensure_directory_exists "/opt/thebarcodeapi"
ensure_directory_exists "/opt/thebarcodeapi/barcodeApi" # Backend application deployment
ensure_directory_exists "/opt/thebarcodeapi/${ENVIRONMENT}/releases/data" # For Docker persistent data
ensure_directory_exists "/opt/thebarcodeapi/${ENVIRONMENT}/releases/data/postgres"
ensure_directory_exists "/opt/thebarcodeapi/${ENVIRONMENT}/releases/data/redis"
ensure_directory_exists "/opt/thebarcodeapi/${ENVIRONMENT}/backups" # For database/Redis backups
ensure_directory_exists "/opt/thebarcodeapi/${ENVIRONMENT}/current" # Symlink for current frontend release
ensure_directory_exists "/opt/thebarcodeapi/${ENVIRONMENT}/logs"    # For frontend PM2 logs

# --- Critical Scripts Verification (formerly "Error Check" step) ---
echo "Verifying existence and executability of critical operational scripts..."
CRITICAL_OPERATIONAL_SCRIPTS=(
  "/opt/thebarcodeapi/barcodeApi/backup.sh"          # Main backup script
  "/opt/thebarcodeapi/barcodeApi/pre-backup-check.sh" # Wrapper for backup script, checks lock
  "/opt/thebarcodeapi/cleanup.sh"                   # System cleanup script (old releases, Docker prune)
  "/opt/thebarcodeapi/barcodeApi/wait-for-it.sh"    # Utility for Docker startup coordination
)
for script_file_path in "${CRITICAL_OPERATIONAL_SCRIPTS[@]}"; do
  echo -n "Checking script: ${script_file_path}... "
  if [ ! -f "$script_file_path" ]; then
    echo "ERROR: NOT FOUND!"
    # This is critical; these scripts should have been created by previous infra steps.
    exit 1 # Exit if a critical script is missing.
  elif [ ! -x "$script_file_path" ]; then
    echo "ERROR: NOT EXECUTABLE!"
    echo "Attempting to make ${script_file_path} executable..."
    echo "$SUDO_PASSWORD" | sudo -S chmod +x "$script_file_path"
    if [ ! -x "$script_file_path" ]; then # Re-check
        echo "FATAL: Failed to make ${script_file_path} executable. Please check permissions."
        exit 1
    fi
    echo "Made executable."
  else
    echo "Found and executable."
  fi
done

# --- Cron Job Verification (Basic Check) ---
# This performs a simple grep; more robust checking might involve parsing crontab entries more carefully.
echo "Verifying installation of cron jobs (basic check)..."
PRE_BACKUP_CRON_SCRIPT_PATH="/opt/thebarcodeapi/barcodeApi/pre-backup-check.sh"
CLEANUP_CRON_SCRIPT_PATH="/opt/thebarcodeapi/cleanup.sh"

if echo "$SUDO_PASSWORD" | sudo -S crontab -l 2>/dev/null | grep -q -F "$PRE_BACKUP_CRON_SCRIPT_PATH"; then
  echo "Backup cron job appears to be installed."
else
  echo "Warning: Backup cron job for '${PRE_BACKUP_CRON_SCRIPT_PATH}' does not appear in crontab. Check configure-backup-coordination.sh."
fi

if echo "$SUDO_PASSWORD" | sudo -S crontab -l 2>/dev/null | grep -q -F "$CLEANUP_CRON_SCRIPT_PATH"; then
  echo "Cleanup cron job appears to be installed."
else
  echo "Warning: Cleanup cron job for '${CLEANUP_CRON_SCRIPT_PATH}' does not appear in crontab. Check add-cleanup-routine.sh."
fi

# --- Permissions Verification (Spot Check) ---
# fix-permissions.sh should handle comprehensive permission setting. This is a spot check.
echo "Performing spot check on key permissions..."
# Overall ownership of /opt/thebarcodeapi (should be github-runner)
if [ "$(stat -c '%U:%G' /opt/thebarcodeapi)" == "github-runner:github-runner" ]; then
    echo "/opt/thebarcodeapi ownership is OK (github-runner:github-runner)."
else
    echo "Warning: /opt/thebarcodeapi ownership is $(stat -c '%U:%G' /opt/thebarcodeapi), expected github-runner:github-runner."
fi

# Backend .env file permissions
BACKEND_ENV_FILE="/opt/thebarcodeapi/barcodeApi/.env"
if [ -f "$BACKEND_ENV_FILE" ]; then
    actual_perms=$(stat -c "%a" "$BACKEND_ENV_FILE")
    # Expect 600 (rw-------) or 400 (r-------- if only root/runner needs to read for processes)
    if [ "$actual_perms" == "600" ] || [ "$actual_perms" == "400" ]; then
        echo "${BACKEND_ENV_FILE} permissions are OK (${actual_perms})."
    else
        echo "Warning: ${BACKEND_ENV_FILE} permissions are ${actual_perms}. Expected 600 (rw-------) or 400 (r--------)."
    fi
else
    echo "Warning: Backend .env file ${BACKEND_ENV_FILE} not found during permission check."
fi

echo "Infrastructure setup verification process completed."
echo "Review any warnings. Manual verification of cron job schedules and script contents is recommended."
