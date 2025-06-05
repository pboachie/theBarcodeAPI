# ---
# Purpose:
#   Creates the .env file for the backend Dockerized application.
#   This file contains environment-specific configurations and secrets
#   that are read by the backend services (e.g., FastAPI application, database connections).
#
# Environment Variables (expected as input from the calling workflow):
#   - SUDO_PASSWORD: Password for sudo execution, as the .env file is written to a privileged directory.
#   - API_VERSION: Version of the API (e.g., v1).
#   - DB_PASSWORD: Password for the application's database user.
#   - POSTGRES_PASSWORD: Password for the PostgreSQL superuser (used by Docker Compose setup).
#   - API_SECRET_KEY: Secret key for JWT token generation and other security functions.
#   - API_MASTER_KEY: Master API key for administrative access.
#   - ENVIRONMENT: The deployment environment (e.g., staging, production).
#   - (Implicitly uses ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REDIS_URL, etc., which are hardcoded
#      in the template but could be parameterized if needed.)
#
# Outputs:
#   - Creates /opt/thebarcodeapi/barcodeApi/.env with the specified content.
#   - Sets ownership to www-data:www-data and permissions to 644.
#   - Verifies file creation and prints its details; exits with error if creation fails.
# ---
#!/bin/bash
set -e

# Ensure all required variables are present
REQUIRED_VARS=("SUDO_PASSWORD" "API_VERSION" "DB_PASSWORD" "POSTGRES_PASSWORD" "API_SECRET_KEY" "API_MASTER_KEY" "ENVIRONMENT" "DOMAIN_NAME")
for var_name in "${REQUIRED_VARS[@]}"; do
  if [ -z "${!var_name}" ]; then
    echo "Error: Environment variable ${var_name} is not set."
    exit 1
  fi
done

echo "Creating backend .env file at /opt/thebarcodeapi/barcodeApi/.env..."

# Using sudo to write the .env file to a privileged location.
# The heredoc content is expanded with shell variables passed from the GitHub Actions workflow.
echo "${SUDO_PASSWORD}" | sudo -S bash -c 'cat > /opt/thebarcodeapi/barcodeApi/.env << EOF
API_VERSION=\${API_VERSION}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REDIS_URL=redis://redis:6379/1
SYNC_DATABASE_URL=postgresql+asyncpg://barcodeboachiefamily:\${DB_PASSWORD}@db/barcode_api
LOG_DIRECTORY=logs
ROOT_PATH=/api/v1
DB_PASSWORD=\${DB_PASSWORD}
POSTGRES_PASSWORD=\${POSTGRES_PASSWORD} # Used by docker-compose.yml for initial DB setup
SECRET_KEY=\${API_SECRET_KEY} # Primary secret key for the application
MASTER_API_KEY=\${API_MASTER_KEY} # For privileged API access
DATABASE_URL=postgresql+asyncpg://barcodeboachiefamily:\${DB_PASSWORD}@db/barcode_api # Main database connection string
ENVIRONMENT=\${ENVIRONMENT} # Deployment environment
SERVER_URL=https://\${DOMAIN_NAME}
EOF'

# Set ownership and permissions for the .env file.
# www-data is often the user running web servers like Nginx/Apache, or PHP-FPM.
# For Dockerized apps, the container user needs to read this. If the app inside Docker
# doesn't run as www-data, these permissions might need adjustment or the .env file
# might be read by root and passed to the container differently.
# The original workflow set www-data, so retaining for now.
echo "Setting permissions for .env file..."
echo "${SUDO_PASSWORD}" | sudo -S chown www-data:www-data /opt/thebarcodeapi/barcodeApi/.env
echo "${SUDO_PASSWORD}" | sudo -S chmod 644 /opt/thebarcodeapi/barcodeApi/.env # Read for owner/group, readonly for others. Consider 600 if only owner needs access.

# Verify .env file was created and has content
echo "Verifying .env file creation..."
if [ -f "/opt/thebarcodeapi/barcodeApi/.env" ]; then
  echo "File /opt/thebarcodeapi/barcodeApi/.env created successfully."
  echo "File permissions:"
  sudo ls -l /opt/thebarcodeapi/barcodeApi/.env
  echo "File contents (first few lines):" # Avoid printing full .env with secrets
  sudo head -n 5 /opt/thebarcodeapi/barcodeApi/.env
else
  echo "ERROR: .env file /opt/thebarcodeapi/barcodeApi/.env not created!"
  exit 1
fi

echo ".env file creation process complete."
