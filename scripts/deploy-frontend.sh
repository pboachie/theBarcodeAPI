#!/bin/bash

# Frontend deployment script with robust PM2 process management
# This script handles deployment of the Next.js frontend with proper PM2 process management by name

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] ${message}${NC}"
}

# Function to check if PM2 process exists by name
pm2_process_exists() {
    local process_name=$1
    PM2_HOME="/home/github-runner/.pm2" pm2 list | grep -q "$process_name" 2>/dev/null
}

# Function to check if PM2 process is running by name
pm2_process_running() {
    local process_name=$1
    PM2_HOME="/home/github-runner/.pm2" pm2 list | grep "$process_name" | grep -q "online" 2>/dev/null
}

# Function for health check
check_health() {
    local url="http://localhost:3000"
    local max_workers=2
    local seconds_per_worker=30
    local max_attempts=$((seconds_per_worker * max_workers / 5))

    print_status "$BLUE" "Starting health check... Will try $max_attempts times (${seconds_per_worker}s per worker)"

    for i in $(seq 1 $max_attempts); do
        if curl -s -f -m 5 "$url" > /dev/null; then
            print_status "$GREEN" "Health check passed on attempt $i"
            return 0
        fi
        print_status "$YELLOW" "Health check attempt $i/$max_attempts..."

        if [ $((i % 5)) -eq 0 ]; then
            print_status "$BLUE" "Current PM2 status:"
            PM2_HOME="/home/github-runner/.pm2" pm2 list
            print_status "$BLUE" "Recent logs:"
            PM2_HOME="/home/github-runner/.pm2" pm2 logs "thebarcodeapi-frontend-${ENVIRONMENT}" --lines 10 --nostream || true
        fi

        sleep 5
    done

    print_status "$RED" "Health check failed after $max_attempts attempts. Final PM2 status:"
    PM2_HOME="/home/github-runner/.pm2" pm2 list
    print_status "$RED" "Recent logs:"
    PM2_HOME="/home/github-runner/.pm2" pm2 logs "thebarcodeapi-frontend-${ENVIRONMENT}" --lines 50 --nostream || true
    return 1
}

# Function to safely reload PM2 process by name
pm2_reload_by_name() {
    local process_name=$1
    
    print_status "$BLUE" "Attempting to reload PM2 process: $process_name"
    
    # Check if process exists
    if ! pm2_process_exists "$process_name"; then
        print_status "$YELLOW" "PM2 process '$process_name' not found, starting new instance..."
        cd "/opt/thebarcodeapi/${ENVIRONMENT}/current"
        PM2_HOME="/home/github-runner/.pm2" pm2 start "/opt/thebarcodeapi/${ENVIRONMENT}/ecosystem.config.js"
        return $?
    fi
    
    # Process exists, reload it
    print_status "$BLUE" "Reloading PM2 process '$process_name'..."
    PM2_HOME="/home/github-runner/.pm2" pm2 reload "$process_name" --update-env
    local reload_status=$?
    
    if [ $reload_status -eq 0 ]; then
        print_status "$GREEN" "PM2 process '$process_name' reloaded successfully"
        PM2_HOME="/home/github-runner/.pm2" pm2 save --force
    else
        print_status "$RED" "Failed to reload PM2 process '$process_name'"
        return $reload_status
    fi
    
    return 0
}

# Function to handle PM2 restart as fallback
pm2_restart_by_name() {
    local process_name=$1
    
    print_status "$YELLOW" "Attempting to restart PM2 process: $process_name"
    
    if pm2_process_exists "$process_name"; then
        PM2_HOME="/home/github-runner/.pm2" pm2 restart "$process_name"
        local restart_status=$?
        
        if [ $restart_status -eq 0 ]; then
            print_status "$GREEN" "PM2 process '$process_name' restarted successfully"
            PM2_HOME="/home/github-runner/.pm2" pm2 save --force
        else
            print_status "$RED" "Failed to restart PM2 process '$process_name'"
            return $restart_status
        fi
    else
        print_status "$YELLOW" "PM2 process '$process_name' not found, starting new instance..."
        cd "/opt/thebarcodeapi/${ENVIRONMENT}/current"
        PM2_HOME="/home/github-runner/.pm2" pm2 start "/opt/thebarcodeapi/${ENVIRONMENT}/ecosystem.config.js"
    fi
    
    return 0
}

# Main deployment function
main() {
    # Validate required environment variables
    if [ -z "$ENVIRONMENT" ]; then
        print_status "$RED" "Error: ENVIRONMENT variable not set"
        exit 1
    fi
    
    if [ -z "$SUDO_PASSWORD" ]; then
        print_status "$RED" "Error: SUDO_PASSWORD variable not set"
        exit 1
    fi
    
    local process_name="thebarcodeapi-frontend-${ENVIRONMENT}"
    local current_dir="/opt/thebarcodeapi/${ENVIRONMENT}/current"
    local previous_release_link="/opt/thebarcodeapi/${ENVIRONMENT}/previous"
    
    print_status "$BLUE" "Starting frontend deployment for environment: $ENVIRONMENT"
    print_status "$BLUE" "Process name: $process_name"
    
    # Store current commit hash
    git rev-parse HEAD > .git-commit
    
    # Ensure base directories exist with proper permissions
    print_status "$BLUE" "Setting up deployment directories..."
    echo "$SUDO_PASSWORD" | sudo -S mkdir -p /opt/thebarcodeapi/${ENVIRONMENT}/{releases,current}
    echo "$SUDO_PASSWORD" | sudo -S chown -R github-runner:github-runner /opt/thebarcodeapi
    
    # Check if changes were detected (passed as argument)
    local has_changes=${1:-"true"}
    
    if [ "$has_changes" == "true" ]; then
        print_status "$BLUE" "Changes detected, performing full deployment..."
        
        TIMESTAMP=$(date +%Y%m%d%H%M%S)
        NEW_RELEASE="/opt/thebarcodeapi/${ENVIRONMENT}/releases/release-${TIMESTAMP}"
        
        # Create and setup new release directory
        print_status "$BLUE" "Creating new release directory: $NEW_RELEASE"
        echo "$SUDO_PASSWORD" | sudo -S mkdir -p "$NEW_RELEASE"
        echo "$SUDO_PASSWORD" | sudo -S cp -R ./.next "$NEW_RELEASE/"
        echo "$SUDO_PASSWORD" | sudo -S cp -R ./public "$NEW_RELEASE/"
        echo "$SUDO_PASSWORD" | sudo -S cp ./package*.json ./.git-commit "$NEW_RELEASE/"
        echo "$SUDO_PASSWORD" | sudo -S chown -R github-runner:github-runner "$NEW_RELEASE"
        echo "$SUDO_PASSWORD" | sudo -S chmod -R 755 "$NEW_RELEASE"
        
        # Install dependencies
        cd "$NEW_RELEASE"
        print_status "$BLUE" "Installing production dependencies..."
        npm ci --omit=dev
        if [ $? -ne 0 ]; then
            print_status "$RED" "npm install failed"
            exit 1
        fi
        
        # Handle the current directory symlink
        if [ -d "$current_dir" ] && [ ! -L "$current_dir" ]; then
            print_status "$BLUE" "Converting existing current directory to symlink..."
            # Move the content to a new release directory if it exists
            if [ -d "$current_dir/.next" ] || [ -d "$current_dir/public" ]; then
                INITIAL_RELEASE="/opt/thebarcodeapi/${ENVIRONMENT}/releases/initial-release"
                echo "$SUDO_PASSWORD" | sudo -S mv "$current_dir" "$INITIAL_RELEASE"
                echo "$SUDO_PASSWORD" | sudo -S ln -sfn "$INITIAL_RELEASE" "$previous_release_link"
            else
                # If it's empty or not a proper release, just remove it
                echo "$SUDO_PASSWORD" | sudo -S rm -rf "$current_dir"
            fi
        elif [ -L "$current_dir" ] && [ -e "$current_dir" ]; then
            # Store current as previous before switching
            CURRENT_RELEASE=$(readlink -f "$current_dir")
            echo "$SUDO_PASSWORD" | sudo -S ln -sfn "$CURRENT_RELEASE" "$previous_release_link"
        fi
        
        # Update symlinks and set final permissions
        echo "$SUDO_PASSWORD" | sudo -S chown -R www-data:www-data "$NEW_RELEASE"
        echo "$SUDO_PASSWORD" | sudo -S chmod -R 755 "$NEW_RELEASE"
        echo "$SUDO_PASSWORD" | sudo -S ln -sfn "$NEW_RELEASE" "$current_dir"
        
        # Cleanup old releases (keep last 3)
        cd "/opt/thebarcodeapi/${ENVIRONMENT}/releases"
        echo "$SUDO_PASSWORD" | sudo -S bash -c 'ls -1dt */ | tail -n +4 | xargs -r rm -rf'
    else
        print_status "$BLUE" "No changes detected, skipping file deployment"
    fi
    
    # PM2 process management using name-based commands
    print_status "$BLUE" "Managing PM2 process: $process_name"
    
    # First, try to reload the process by name
    if ! pm2_reload_by_name "$process_name"; then
        print_status "$YELLOW" "Reload failed, attempting restart as fallback..."
        if ! pm2_restart_by_name "$process_name"; then
            print_status "$RED" "Both reload and restart failed"
            exit 1
        fi
    fi
    
    # Health check and rollback if needed
    print_status "$BLUE" "Starting health checks..."
    if ! check_health; then
        print_status "$RED" "Health check failed, attempting rollback..."
        if [ -L "$previous_release_link" ] && [ -e "$previous_release_link" ]; then
            echo "$SUDO_PASSWORD" | sudo -S ln -sfn "$(readlink -f "$previous_release_link")" "$current_dir"
            
            print_status "$BLUE" "Restarting PM2 for rollback..."
            if ! pm2_restart_by_name "$process_name"; then
                print_status "$RED" "CRITICAL: Rollback PM2 restart failed! Manual intervention required!"
                exit 1
            fi
            
            if ! check_health; then
                print_status "$RED" "CRITICAL: Rollback failed! Site is down!"
                PM2_HOME="/home/github-runner/.pm2" pm2 list
                PM2_HOME="/home/github-runner/.pm2" pm2 logs "$process_name" --lines 100 --nostream || true
                exit 1
            fi
            print_status "$YELLOW" "Rollback successful, but original deployment failed"
            exit 1
        fi
        print_status "$RED" "No previous release available for rollback"
        exit 1
    fi
    
    print_status "$GREEN" "Frontend deployment completed successfully!"
}

# Execute main function with all arguments
main "$@"