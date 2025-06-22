#!/bin/bash

# Ensure logs directory exists
mkdir -p /app/logs 2>/dev/null || true

# Create log file if it doesn't exist
touch /app/logs/app.log 2>/dev/null || true

# If we can't write to logs, use a temp directory
if [ ! -w /app/logs ]; then
    export LOG_DIRECTORY=/tmp/logs
    mkdir -p $LOG_DIRECTORY
    echo "Warning: Using temporary log directory at $LOG_DIRECTORY"
fi

# Execute the main command
exec "$@"
