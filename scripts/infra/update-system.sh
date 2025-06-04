# ---
# Purpose:
#   Updates the system's package list and upgrades installed packages.
#   This script is intended to be run with sudo privileges.
#
# Environment Variables:
#   - SUDO_PASSWORD: (Implicitly used if this script is called with `sudo -S bash script.sh`)
#                    Not directly used by the script's commands but required by the calling
#                    GitHub Actions step to execute the script with sudo.
#
# Outputs:
#   - Updates package lists (apt-get update).
#   - Upgrades all currently installed packages to their newest versions (apt-get upgrade -y).
#   - Logs the process.
# ---
#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "Starting system package update and upgrade process..."

# Update package lists from repositories
echo "Updating package lists (apt-get update)..."
apt-get update -qq # -qq for quieter output, less verbose

# Upgrade installed packages to their newest versions
# -y automatically answers yes to prompts
echo "Upgrading installed packages (apt-get upgrade -y)..."
apt-get upgrade -y -qq # -qq for quieter output

echo "System package update and upgrade completed."
