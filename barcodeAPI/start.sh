#!/bin/bash

set -e

# Function to print colored and formatted text
print_colored() {
    local color=$1
    local text=$2
    echo -e "\e[${color}m${text}\e[0m"
}

# Function to print a header
print_header() {
    local text=$1
    local padding=$(printf '%0.1s' ={1..60})
    printf '%s %s %s\n' "$padding" "$text" "$padding"
}

# Function to check database connection
check_db_connection() {
    local retries=5
    local wait_time=5
    while [ $retries -gt 0 ]; do
        if pg_isready -h db -p 5432 -U postgres; then
            return 0
        fi
        retries=$((retries-1))
        print_colored "33" "Waiting for database to be ready... (${retries} attempts left)"
        sleep $wait_time
    done
    return 1
}

if [ ! -d "/app/data" ]; then
    mkdir -p /app/data
fi

if [ ! -d "/app/logs" ]; then
    mkdir -p /app/logs
    chown -R appuser:appuser /app/logs
    chmod -R 775 /app/logs
fi

# Wait for the database to be ready
print_header "Database Check"
if check_db_connection; then
    print_colored "32" "Database is ready!"
else
    print_colored "31" "Failed to connect to the database. Exiting."
    exit 1
fi

# Check and apply database migrations
print_header "Database Migrations"
if [ -z "$(alembic heads)" ]; then
    print_colored "33" "No existing revisions found. Creating initial migration..."
    alembic revision --autogenerate -m "Initial migration"
    alembic upgrade head
else
    print_colored "33" "Existing revisions found. Upgrading to latest..."
    alembic upgrade head
fi
print_colored "32" "Database migrations completed successfully!"

# Determine the optimal number of workers and system stats using Python
print_header "System Information"
SYSTEM_INFO=$(python3 -c "
import os
import psutil

def calculate_optimal_workers():
    cpu_cores = os.cpu_count()
    total_ram = psutil.virtual_memory().total / (1024 * 1024 * 1024)
    available_ram = psutil.virtual_memory().available / (1024 * 1024 * 1024)

    # Use 75% of available cores, rounded down
    workers_by_cpu = int((cpu_cores * 2) + 1)

    # Allocate 1 worker per 0.25GB of available RAM, with a minimum of 2 workers
    workers_by_ram = max(2, int(available_ram / 0.25))

    # Choose the lower of the two calculations
    workers = min(workers_by_cpu, workers_by_ram)

    # Cap at 5 workers
    workers = min(workers, 5)

    # 1 worker can support 42 requests a second. Return total supported requests
    supported_workers = workers * 42

    return cpu_cores, total_ram, available_ram, workers, supported_workers

cpu_cores, total_ram, available_ram, workers, supported_workers = calculate_optimal_workers()
print(f'{cpu_cores}|{total_ram:.2f}|{available_ram:.2f}|{workers}|{supported_workers}')
")

IFS='|' read -r CPU_CORES TOTAL_RAM AVAILABLE_RAM WORKERS SUPPORTED_WORKERS <<< "$SYSTEM_INFO"

# Display system information
print_colored "36" "CPU Cores:        $CPU_CORES"
print_colored "36" "Total RAM:        ${TOTAL_RAM} GB"
print_colored "36" "Available RAM:    ${AVAILABLE_RAM} GB"
print_colored "36" "Optimal Workers:  $WORKERS"
print_colored "36" "Supported RPS:    $SUPPORTED_WORKERS Requests/Second"

# Start the application
print_header "Starting Application"
print_colored "32" "Starting application with $WORKERS workers..."


if [ "$SERVER_TYPE" = "uvicorn" ] || [ -z "$SERVER_TYPE" ]; then
    echo "Using uvicorn server..."
    exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers 1 \
        --loop uvloop \
        --http httptools \
        --access-log \
        --no-server-header
        if [ "$PYTHON_ENV" = "development" ]; then
            --reload
        fi
fi

# Option 2: Gunicorn with uvicorn workers (for high traffic)
if [ "$SERVER_TYPE" = "gunicorn" ]; then
    echo "Using gunicorn with uvicorn workers..."
    # Calculate workers: (2 x CPU cores) + 1, but cap at 4 for WebSocket stability
    WORKERS=${WORKERS:-$(python3 -c "import os; print(min(4, (2 * os.cpu_count()) + 1))")}

    exec gunicorn app.main:app \
        -w $WORKERS \
        -k uvicorn.workers.UvicornWorker \
        --bind 0.0.0.0:8000 \
        --access-logfile - \
        --error-logfile - \
        --log-level info \
        --timeout 300 \
        --keep-alive 5 \
        --max-requests 1000 \
        --max-requests-jitter 100 \
        --preload
    if [ "$PYTHON_ENV" = "development" ]; then
        --reload
    fi
fi
