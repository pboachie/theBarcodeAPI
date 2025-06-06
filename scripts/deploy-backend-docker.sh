# ---
# Purpose:
#   Manages the deployment of the backend application using Docker Compose.
#   It handles data backups, stops old containers, starts new ones (potentially building images),
#   and performs health checks on the services.
#   If no changes are detected (via $CHANGES variable), it only verifies health.
#
# Environment Variables:
#   Sourced from /tmp/env_vars:
#   - ENVIRONMENT: Deployment environment (e.g., staging, production).
#   - SUDO_PASSWORD: Password for sudo operations.
#   - DB_PASSWORD, POSTGRES_PASSWORD, API_SECRET_KEY, API_MASTER_KEY, API_VERSION:
#     These are primarily used by Docker Compose via the .env file, but ENVIRONMENT and SUDO_PASSWORD
#     are used directly by this script for paths and privileged commands.
#
#   Sourced from /tmp/docker_vars:
#   - DOCKER_COMPOSE: The specific docker compose command to use (e.g., "docker-compose" or "docker compose").
#
#   Passed directly by the workflow:
#   - CHANGES: A boolean-like string ("true" or "false") indicating if code changes were detected
#              by a preceding step (e.g., check-backend-changes.sh).
#
# Outputs:
#   - Deploys or reconfigures the backend Docker containers.
#   - Creates backups of database and Redis data.
#   - Logs deployment progress and health check status.
#   - Exits with an error if deployment or health checks fail.
# ---
#!/bin/bash
set -e

# Source environment variables from common files set up by the workflow
if [ ! -f "/tmp/env_vars" ]; then
    echo "Error: Environment variable file /tmp/env_vars not found."
    exit 1
fi
source /tmp/env_vars
echo "Sourced /tmp/env_vars"

if [ ! -f "/tmp/docker_vars" ]; then
    echo "Error: Docker Compose command file /tmp/docker_vars not found."
    exit 1
fi
source /tmp/docker_vars
echo "Sourced /tmp/docker_vars. DOCKER_COMPOSE is set to: ${DOCKER_COMPOSE}"

export PROJECT_VERSION="${API_VERSION}"

# Ensure critical variables sourced from /tmp/env_vars are available
if [ -z "$ENVIRONMENT" ] || [ -z "$SUDO_PASSWORD" ]; then
    echo "Error: Key environment variables (ENVIRONMENT, SUDO_PASSWORD) from /tmp/env_vars are missing."
    exit 1
fi
if [ -z "$CHANGES" ]; then
    echo "Error: CHANGES environment variable is not set. This should be passed from the workflow."
    exit 1
fi

# Navigate to the backend application directory where docker-compose.yml is located
TARGET_DIR="/opt/thebarcodeapi/barcodeApi"
echo "Changing directory to ${TARGET_DIR}"
cd "${TARGET_DIR}" || { echo "Error: Failed to change directory to ${TARGET_DIR}"; exit 1; }

echo "Starting backend deployment..."
echo "Using DOCKER_COMPOSE command: ${DOCKER_COMPOSE}"
echo "Changes detected: ${CHANGES}"

# If no changes detected, just check health of existing services and exit
if [ "$CHANGES" == "false" ]; then
  echo "No changes detected in backend files. Verifying health of existing services only..."

  # Check if services are running, attempt to start if not (e.g., after a reboot)
  if ! $DOCKER_COMPOSE ps | grep -q "Up"; then # This check might be too simple if some services are up and others aren't
    echo "Some or all services are not running. Attempting to start them with '$DOCKER_COMPOSE up -d'..."
    $DOCKER_COMPOSE up -d # This will start all services defined in docker-compose.yml
  fi

  # Verify health of essential services
  for service in "db" "redis" "barcodeapi"; do
    echo "Verifying health of service: $service..."
    # Timeout for health check attempts for each service
    timeout 300 bash -c "until $DOCKER_COMPOSE ps $service 2>/dev/null | grep -q 'healthy'; do
      echo 'Waiting for $service to become healthy...'
      $DOCKER_COMPOSE ps $service # Show status during wait
      sleep 10 # Increased sleep interval
    done" || { echo "Error: Service $service did not become healthy in time."; $DOCKER_COMPOSE logs $service; exit 1; }
    echo "Service $service is healthy."
  done

  echo "Backend health verified successfully for existing services."
  exit 0
fi

# --- Full deployment process if CHANGES is true ---
echo "Changes detected. Proceeding with full backend deployment..."

# Create backup directory
BACKUP_DIR="/opt/thebarcodeapi/${ENVIRONMENT}/backups/$(date +%Y%m%d_%H%M%S)"
echo "Creating backup directory: ${BACKUP_DIR}"
echo "$SUDO_PASSWORD" | sudo -S mkdir -p "${BACKUP_DIR}"
echo "$SUDO_PASSWORD" | sudo -S chown -R $USER:$USER "${BACKUP_DIR}" # $USER is the runner user

# Function to safely backup PostgreSQL
backup_postgres() {
    echo "Attempting PostgreSQL backup..."
    if $DOCKER_COMPOSE ps db 2>/dev/null | grep -q "Up"; then # Check if 'db' service is running
        if $DOCKER_COMPOSE exec -T db pg_isready -U postgres > /dev/null 2>&1; then # Check if postgres inside container is ready
            echo "PostgreSQL is ready, creating backup..."
            $DOCKER_COMPOSE exec -T db pg_dumpall -U postgres > "${BACKUP_DIR}/postgres_backup.sql" || {
                echo "Warning: Failed to create PostgreSQL backup."
                return 1 # Indicate failure
            }
            echo "PostgreSQL backup completed successfully: ${BACKUP_DIR}/postgres_backup.sql"
            return 0 # Indicate success
        else
            echo "PostgreSQL container is up but not ready for backup."
        fi
    else
      echo "PostgreSQL container (db) is not running."
    fi
    echo "Skipping PostgreSQL backup."
    return 0 # Not a failure if service wasn't running/ready
}

# Function to safely backup Redis
backup_redis() {
    echo "Attempting Redis backup..."
    if $DOCKER_COMPOSE ps redis 2>/dev/null | grep -q "Up"; then # Check if 'redis' service is running
        if $DOCKER_COMPOSE exec -T redis redis-cli ping | grep -q "PONG"; then # Check if redis inside container is responsive
            echo "Redis is ready, creating backup..."
            # Ensure Redis saves its data to disk
            $DOCKER_COMPOSE exec -T redis redis-cli SAVE || {
                echo "Warning: Failed to execute Redis SAVE command."
                # Continue to attempt copy if SAVE fails but dump file might exist
            }
            # Copy the RDB file from the Docker volume
            # The volume path /data inside the container must match docker-compose.yml
            REDIS_RDB_HOST_PATH="/opt/thebarcodeapi/${ENVIRONMENT}/releases/data/redis/dump.rdb"
            if [ -f "$REDIS_RDB_HOST_PATH" ]; then
                 echo "$SUDO_PASSWORD" | sudo -S cp "$REDIS_RDB_HOST_PATH" "${BACKUP_DIR}/redis_dump.rdb" || {
                    echo "Warning: Failed to copy Redis dump file from $REDIS_RDB_HOST_PATH."
                    return 1 # Indicate failure
                }
                echo "Redis backup completed successfully: ${BACKUP_DIR}/redis_dump.rdb"
                return 0 # Indicate success
            else
                echo "Warning: Redis dump file ($REDIS_RDB_HOST_PATH) not found on host after SAVE command."
                return 1
            fi
        else
            echo "Redis container is up but not responsive (PONG failed)."
        fi
    else
        echo "Redis container (redis) is not running."
    fi
    echo "Skipping Redis backup."
    return 0 # Not a failure if service wasn't running/ready
}

# Perform backups
echo "Performing data backups before deployment..."
backup_postgres
backup_redis

# Stop current containers before making changes
echo "Stopping current Docker services (if any)..."
$DOCKER_COMPOSE down || echo "Note: 'docker-compose down' reported an error, possibly no services were running."

# Preserve existing data by copying from persistent volume paths to backup (already done by backup functions if they use these paths)
# The setup-docker-env.sh script should ensure these directories are correctly configured for Docker volumes.
# This is more of a safeguard or could be for non-volume data if any.
echo "Ensuring critical data directories are backed up (PostgreSQL)..."
if [ -d "/opt/thebarcodeapi/${ENVIRONMENT}/releases/data/postgres" ]; then
    echo "$SUDO_PASSWORD" | sudo -S cp -R "/opt/thebarcodeapi/${ENVIRONMENT}/releases/data/postgres" "${BACKUP_DIR}/postgres_data_snapshot"
fi
echo "Ensuring critical data directories are backed up (Redis)..."
if [ -d "/opt/thebarcodeapi/${ENVIRONMENT}/releases/data/redis" ]; then
    echo "$SUDO_PASSWORD" | sudo -S cp -R "/opt/thebarcodeapi/${ENVIRONMENT}/releases/data/redis" "${BACKUP_DIR}/redis_data_snapshot"
fi

# Set up data directories with correct permissions (Docker often needs specific UIDs or open permissions)
# These permissions are critical for Docker volumes if the container user is not root.
# The user ID 999 is often used by official images like postgres.
echo "Verifying and setting up data directory permissions..."
for data_path_segment in "postgres" "redis"; do
    path="/opt/thebarcodeapi/${ENVIRONMENT}/releases/data/${data_path_segment}"
    echo "$SUDO_PASSWORD" | sudo -S mkdir -p "$path"
    # For postgres, user 999 and group 999 with 700 permissions is common.
    # For redis, user 999 and group 999 with 755 might be needed if redis runs as non-root but needs broader access.
    # Adjust these based on the actual users inside your containers.
    if [ "$data_path_segment" == "postgres" ]; then
        echo "$SUDO_PASSWORD" | sudo -S chown -R 999:999 "$path"
        echo "$SUDO_PASSWORD" | sudo -S chmod -R 700 "$path"
    else # Assuming Redis or other services
        echo "$SUDO_PASSWORD" | sudo -S chown -R 999:999 "$path" # Example, adjust if Redis runs as different user
        echo "$SUDO_PASSWORD" | sudo -S chmod -R 755 "$path"
    fi
done

# Rebuild and start services, or just start if image is pre-built and up-to-date.
# The docker/build-push-action in the workflow should have built and loaded the image as 'barcodeapi:latest'.
echo "Starting Docker services with '$DOCKER_COMPOSE up -d'..."
if docker image inspect barcodeapi:latest >/dev/null 2>&1; then
  echo "Image 'barcodeapi:latest' found. Using it to start services."
  # '--force-recreate' can be added if containers need to be definitely restarted even if config hasn't changed
  # '--always-recreate-deps' if dependencies also need to be recreated.
  $DOCKER_COMPOSE up -d --remove-orphans # Remove any orphaned containers from previous versions
else
  echo "Image 'barcodeapi:latest' not found. Attempting to build 'barcodeapi' service and then start all services."
  # This implies the workflow's build step might have failed or tags are different.
  # Building here can be slow; prefer ensuring image is built by workflow's docker/build-push-action.
  $DOCKER_COMPOSE build --no-cache barcodeapi # Build the 'barcodeapi' service specifically if needed
  $DOCKER_COMPOSE up -d --remove-orphans
fi

# Health check function for individual services
check_container_health() {
    local service_name="$1"
    local timeout_seconds="$2"
    local start_time=$(date +%s)
    local end_time=$((start_time + timeout_seconds))

    echo "Performing health check for service: ${service_name} (timeout: ${timeout_seconds}s)..."
    while [ $(date +%s) -lt $end_time ]; do
        # Check Docker Compose health status if defined, otherwise check if container is running
        if $DOCKER_COMPOSE ps "${service_name}" 2>/dev/null | grep -q "healthy"; then
            echo "Service ${service_name} is healthy."
            return 0
        elif ! $DOCKER_COMPOSE ps "${service_name}" 2>/dev/null | grep -q "Up"; then # Check if it's even Up
            echo "Service ${service_name} is not Up. Current status:"
            $DOCKER_COMPOSE ps "${service_name}"
            return 1 # Service is down
        fi
        echo "Waiting for ${service_name} to become healthy... (Status: $($DOCKER_COMPOSE ps ${service_name} | grep ${service_name} || echo "Not found"))"
        sleep 10 # Check every 10 seconds
    done

    echo "Error: Service ${service_name} failed to become healthy within ${timeout_seconds} seconds."
    $DOCKER_COMPOSE ps "${service_name}" # Show final status
    $DOCKER_COMPOSE logs "${service_name}" --tail 50 # Show recent logs
    return 1
}

# Check health of all essential services
ESSENTIAL_SERVICES=("db" "redis" "barcodeapi")
for service in "${ESSENTIAL_SERVICES[@]}"; do
    if ! check_container_health "$service" 300; then # 5 minutes timeout per service
        echo "Critical Error: Service $service failed its health check during deployment."
        # Consider a rollback strategy here if possible
        exit 1
    fi
done

echo "Backend deployment completed successfully. All essential services are healthy."
