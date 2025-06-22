# Frontend Deployment Scripts

This directory contains scripts for deploying the theBarcodeAPI frontend with robust PM2 process management.

## Problem Solved

The original deployment workflow failed with `[PM2][ERROR] Process 0 not found` because it was trying to reload PM2 processes by numeric ID instead of process name. PM2 process IDs are not stable and may not survive process restarts.

## Solution

The deployment scripts now use process names for all PM2 operations, making the deployment more robust and reliable.

## Files

### `deploy-frontend.sh`

Main deployment script that handles:
- Process management by name instead of ID
- Graceful handling of PM2 reload failures with fallback to restart
- Proper error handling and rollback capabilities
- Health checks with detailed logging
- Release management and cleanup

**Usage:**
```bash
export ENVIRONMENT="production"
export SUDO_PASSWORD="your_password"
./deploy-frontend.sh [changes_detected]
```

**Key Features:**
- Uses `pm2 reload "thebarcodeapi-frontend-${ENVIRONMENT}"` instead of `pm2 reload 0`
- Fallback to `pm2 restart` if reload fails
- Comprehensive health checks
- Automatic rollback on failure
- Colored logging for better visibility

### `ecosystem.config.js`

PM2 ecosystem configuration that defines:
- Process name using environment variable: `thebarcodeapi-frontend-${ENVIRONMENT}`
- Cluster mode with 2 instances
- Proper logging configuration
- Health monitoring and restart policies
- Graceful shutdown handling

### `test-deploy-frontend.sh`

Test script that validates:
- Script syntax and executable permissions
- PM2 process management by name
- Process lifecycle operations (start, reload, restart, stop, delete)
- Function behavior in the deployment script

**Usage:**
```bash
./test-deploy-frontend.sh
```

## Integration with GitHub Workflow

The GitHub workflow (`.github/workflows/application-cd.yml`) has been updated to:
1. Copy the ecosystem configuration to the deployment directory
2. Use the deployment script instead of inline commands
3. Pass the changes detection flag to the script

## Benefits

1. **Reliability**: Process management by name is more stable than by ID
2. **Error Handling**: Comprehensive error handling with fallback strategies
3. **Debugging**: Better logging and status reporting
4. **Testing**: Dedicated test suite for validation
5. **Maintainability**: Modular script design for easier updates

## Testing

Run the test suite to validate the deployment functionality:

```bash
# Run basic validation tests (works without PM2)
./test-deploy-frontend.sh

# For full PM2 tests, install PM2 first:
npm install -g pm2
./test-deploy-frontend.sh
```

The test suite includes:
- Script validation (syntax, permissions, existence)
- PM2 process management tests (if PM2 is available)
- Function behavior validation

## Troubleshooting

### Common Issues

1. **Process not found**: The script will automatically start a new process if none exists
2. **Reload failure**: The script falls back to restart if reload fails
3. **Health check failure**: Automatic rollback to previous release if available

### Debug Information

The script provides detailed logging including:
- Timestamped status messages with colors
- PM2 process status during health checks
- Recent log output on failures
- Step-by-step deployment progress

### Manual Process Management

If needed, you can manually manage PM2 processes:

```bash
# List all processes
PM2_HOME="/home/github-runner/.pm2" pm2 list

# Reload by name
PM2_HOME="/home/github-runner/.pm2" pm2 reload "thebarcodeapi-frontend-production"

# Restart by name
PM2_HOME="/home/github-runner/.pm2" pm2 restart "thebarcodeapi-frontend-production"

# View logs
PM2_HOME="/home/github-runner/.pm2" pm2 logs "thebarcodeapi-frontend-production"
```

## Configuration

The deployment can be configured through environment variables:

- `ENVIRONMENT`: Deployment environment (production, staging, etc.)
- `SUDO_PASSWORD`: Password for sudo operations
- `PM2_HOME`: PM2 home directory (defaults to `/home/github-runner/.pm2`)

## Security Considerations

- The deployment script requires sudo access for file operations
- PM2 processes run under the configured user account
- Log files are created with appropriate permissions
- Sensitive information is not logged or exposed