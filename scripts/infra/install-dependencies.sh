# ---
# Purpose:
#   Checks for and installs essential system dependencies required for the application infrastructure.
#   This includes:
#     - Nginx (web server/reverse proxy)
#     - Node.js (for frontend runtime and PM2)
#     - PM2 (process manager for Node.js applications)
#     - Docker Engine (containerization platform)
#     - Docker Compose (for defining and running multi-container Docker applications)
#   It attempts to be idempotent by checking if a dependency already exists before installing.
#   It also verifies the installations and ensures the current user is in the 'docker' group.
#
# Environment Variables:
#   - SUDO_PASSWORD: (Implicitly used if this script is called with `sudo -S bash script.sh`)
#                    Required for apt-get install, systemctl, usermod, and other privileged operations.
#
# Outputs:
#   - Installs missing dependencies.
#   - Adds current user to the 'docker' group if not already a member.
#   - Logs the installation and verification process.
#   - Exits with an error if a critical installation or verification fails.
# ---
#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "Starting system dependency installation check and setup..."

# Function to check if a command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Function to install Docker Compose (both standalone and as CLI plugin)
install_docker_compose() {
  echo "Installing Docker Compose..."
  # Define Docker Compose version for consistency
  # Check https://github.com/docker/compose/releases for latest versions
  local compose_version="v2.24.6" # Example: Using a specific version

  # Create directories for Docker CLI plugins if they don't exist
  # User-specific plugin directory (for `docker compose` run by user)
  mkdir -p "$HOME/.docker/cli-plugins/"
  # System-wide plugin directory (might require sudo for this path)
  # Using /usr/local/lib/docker/cli-plugins as it's often in PATH for root
  echo "$SUDO_PASSWORD" | sudo -S mkdir -p "/usr/local/lib/docker/cli-plugins"


  # Download Docker Compose binary to a common system location
  local compose_url="https://github.com/docker/compose/releases/download/${compose_version}/docker-compose-$(uname -s)-$(uname -m)"
  echo "Downloading Docker Compose from ${compose_url}..."
  curl -SL "${compose_url}" -o "./docker-compose-temp"

  echo "Installing docker-compose to /usr/local/bin/docker-compose..."
  echo "$SUDO_PASSWORD" | sudo -S mv "./docker-compose-temp" "/usr/local/bin/docker-compose"
  echo "$SUDO_PASSWORD" | sudo -S chmod +x "/usr/local/bin/docker-compose"

  # Also ensure it's available as a CLI plugin for `docker compose` syntax
  echo "Installing as Docker CLI plugin to /usr/local/lib/docker/cli-plugins/docker-compose..."
  echo "$SUDO_PASSWORD" | sudo -S cp "/usr/local/bin/docker-compose" "/usr/local/lib/docker/cli-plugins/docker-compose"

  # Symlink for older `docker-compose` command if desired, though `/usr/local/bin` should be in PATH
  if [ ! -L "/usr/bin/docker-compose" ] && [ -f "/usr/local/bin/docker-compose" ]; then
      echo "Creating symlink /usr/bin/docker-compose -> /usr/local/bin/docker-compose"
      echo "$SUDO_PASSWORD" | sudo -S ln -sf "/usr/local/bin/docker-compose" "/usr/bin/docker-compose"
  fi

  echo "Docker Compose installation attempt finished."
}

# --- Nginx ---
echo "Checking Nginx..."
if ! command_exists nginx; then
  echo "Installing Nginx..."
  apt-get update -qq # Update package lists quietly
  apt-get install -y nginx
else
  echo "Nginx already installed."
fi

# --- Node.js (Version 20.x) ---
echo "Checking Node.js..."
if ! command_exists node; then
  echo "Installing Node.js 20.x..."
  # Download and run NodeSource setup script for Node.js 20.x
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
else
  echo "Node.js already installed."
  node -v # Display current version
fi

# --- PM2 (Process Manager for Node.js) ---
echo "Checking PM2..."
if ! command_exists pm2; then
  echo "Installing PM2 globally via npm..."
  # Ensure npm is available (should be with Node.js)
  if command_exists npm; then
    npm install -g pm2
  else
    echo "Error: npm command not found, cannot install PM2."
    exit 1
  fi
else
  echo "PM2 already installed."
  pm2 --version # Display current version
fi

# --- Docker Engine ---
echo "Checking Docker Engine..."
if ! command_exists docker; then
  echo "Installing Docker Engine..."
  apt-get update -qq
  apt-get install -y ca-certificates curl gnupg lsb-release

  # Add Docker’s official GPG key
  echo "$SUDO_PASSWORD" | sudo -S mkdir -p "/etc/apt/keyrings"
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

  # Set up the Docker repository
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

  apt-get update -qq
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin # Include buildx plugin

  echo "Starting and enabling Docker service..."
  systemctl start docker
  systemctl enable docker

  echo "Adding current user '$USER' to the 'docker' group..."
  usermod -aG docker "$USER" || echo "Warning: Failed to add $USER to docker group. May require manual intervention or relogin."
else
  echo "Docker Engine already installed."
fi

# --- Docker Compose ---
echo "Checking Docker Compose..."
# Check for both `docker compose` (v2 plugin) and `docker-compose` (v1 standalone)
if ! (docker compose version >/dev/null 2>&1 || docker-compose --version >/dev/null 2>&1) ; then
  install_docker_compose
else
  echo "Docker Compose (or plugin) already installed."
  docker compose version || docker-compose --version # Display current version
fi

# --- Verification of all installations ---
echo "Verifying installations by checking versions..."
declare -A commands_to_verify=(
  ["Nginx"]="nginx -v"
  ["Node.js"]="node -v"
  ["npm"]="npm -v"
  ["PM2"]="pm2 --version"
  ["Docker"]="docker --version"
  ["Docker Compose"]="docker compose version || docker-compose --version" # Try plugin first, then standalone
)

for name in "${!commands_to_verify[@]}"; do
  echo -n "Verifying $name: "
  if eval "${commands_to_verify[$name]}" >/dev/null 2>&1; then
    echo "OK ($(${commands_to_verify[$name]} 2>&1 | head -n 1))"
  else
    echo "FAILED. $name might not be installed correctly."
    # exit 1 # Decide if this should be a fatal error
  fi
done

# Ensure current user is part of the 'docker' group for non-root Docker access
echo "Verifying '$USER' Docker group membership..."
if groups "$USER" | grep -q '\bdocker\b'; then
  echo "'$USER' is already a member of the 'docker' group."
else
  echo "Attempting to add '$USER' to 'docker' group..."
  usermod -aG docker "$USER"
  if groups "$USER" | grep -q '\bdocker\b'; then
     echo "'$USER' successfully added to 'docker' group."
     echo "NOTE: A logout/login or new session might be required for group changes to take full effect for the runner's current session."
  else
     echo "Warning: Failed to add '$USER' to 'docker' group or verification failed. Docker commands might require sudo."
  fi
fi

echo "All dependency installations and checks completed."

# Display final versions for confirmation
echo "--- Final Installed Versions ---"
nginx -v 2>&1
node -v
npm -v
PM2_HOME="${HOME:-/home/$USER}/.pm2" pm2 --version # Ensure PM2_HOME if checking version as current user
docker --version
docker compose version || docker-compose --version || echo "Docker Compose not found for version display."
echo "--------------------------------"
