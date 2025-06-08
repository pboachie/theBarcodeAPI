# ---
# Purpose:
#   Configures Nginx as a reverse proxy for the frontend and backend services.
#   It creates an Nginx site configuration file (/etc/nginx/sites-available/thebarcodeapi)
#   with server blocks to listen on port 80 and proxy requests to:
#     - Frontend (Next.js app): http://localhost:3000
#     - Backend API: http://localhost:8000/api
#   It also includes common security headers and sets up access/error logs.
#   Finally, it enables the site by creating a symlink and tests the Nginx configuration.
#
# Environment Variables (expected from /tmp/env_vars):
#   - DOMAIN_NAME: The domain name to be used in the `server_name` directive.
#                  If not set, defaults to '_' (underscore), matching any hostname.
#   - SUDO_PASSWORD: (Implicitly used if this script is called with `sudo -S bash script.sh`)
#                    Required for writing to /etc/nginx/ and running `nginx -t`.
#
# Outputs:
#   - Creates/overwrites the Nginx site configuration file.
#   - Enables the new site configuration.
#   - Validates the Nginx configuration.
#   - Logs the configuration process.
# ---
#!/bin/bash
set -e

echo "Starting Nginx configuration..."

# Attempt to source environment variables
echo "Attempting to source environment variables for Nginx configuration..."
ENV_FILE_SOURCED=false
if [ -n "\${GLOBAL_ENV_VARS_FILE}" ] && [ -f "\${GLOBAL_ENV_VARS_FILE}" ]; then
  source "\${GLOBAL_ENV_VARS_FILE}"
  echo "Sourced environment variables from \${GLOBAL_ENV_VARS_FILE} (via GLOBAL_ENV_VARS_FILE env var)."
  ENV_FILE_SOURCED=true
elif [ -f /tmp/env_vars ]; then
  source /tmp/env_vars
  echo "Sourced environment variables from /tmp/env_vars (fallback)."
  ENV_FILE_SOURCED=true
else
  echo "Warning: Neither GLOBAL_ENV_VARS_FILE (env var: '\${GLOBAL_ENV_VARS_FILE}') nor /tmp/env_vars found. DOMAIN_NAME might not be set correctly for Nginx."
fi

# DOMAIN_NAME could also be passed directly as an environment variable to this script.
# If neither is available, it will default to '_' (hostname catch-all).

# Default to '_' if DOMAIN_NAME is not set (catches all hostnames)
NGINX_SERVER_NAME="${DOMAIN_NAME:-_}"
echo "Nginx server_name will be set to: ${NGINX_SERVER_NAME}"

# Nginx site configuration content
# This will be written to /etc/nginx/sites-available/thebarcodeapi
# Note: This script must be run with sudo privileges to write to this path.
NGINX_CONF_CONTENT="server {
    listen 80;
    listen [::]:80; # Listen on IPv6 as well

    server_name ${NGINX_SERVER_NAME};
    server_tokens off; # Disable emitting Nginx version on error pages and in Server header

    # Location block for the Frontend Next.js application
    location / {
        proxy_pass http://localhost:3000; # Assumes frontend runs on port 3000
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade; # Required for WebSocket connections
        proxy_set_header Connection 'upgrade';   # Required for WebSocket connections
        proxy_set_header Host \$host;             # Pass the original host header
        proxy_set_header X-Real-IP \$remote_addr; # Pass the original client IP
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade; # Do not cache WebSocket upgrades
    }

    # Specific location for MCP SSE to handle trailing slash and optimize for SSE
    location = /api/v1/mcp/sse/ {
        proxy_pass http://localhost:8000/api/v1/mcp/sse; # Note: No trailing slash here
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade; # For potential WebSocket upgrades if ever mixed
        proxy_set_header Connection 'upgrade';   # For potential WebSocket upgrades
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;

        # SSE specific settings
        proxy_buffering off; # Send data to client as soon as it's received from backend
        proxy_cache off;     # Do not cache SSE responses
        # Consider keepalive_timeout if long-lived connections are prematurely closed by Nginx
        # keepalive_timeout 300s; # Example: 5 minutes
    }

    # Location block for the Backend API
    # Requests to /api/ will be proxied to the backend service
    location /api {
        proxy_pass http://localhost:8000; # Assumes backend API runs on port 8000
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;

        # Example of rewriting path if needed:
        # rewrite ^/api/(.*)$ /\$1 break; # Removes /api prefix before passing to backend
                                       # Only use if backend expects paths without /api
    }

    # Common security headers to enhance application security
    add_header X-Frame-Options \"SAMEORIGIN\" always;
    add_header X-XSS-Protection \"1; mode=block\" always;
    add_header X-Content-Type-Options \"nosniff\" always;
    add_header Referrer-Policy \"no-referrer-when-downgrade\" always;
    # Content-Security-Policy can be restrictive; adjust as needed for your application's resources.
    # 'unsafe-inline' for styles/scripts might be needed but is less secure.
    add_header Content-Security-Policy \"default-src 'self' http: https: data: blob: 'unsafe-inline'\" always;

    # Logging paths for access and error logs
    access_log /var/log/nginx/thebarcodeapi.access.log;
    error_log /var/log/nginx/thebarcodeapi.error.log warn; # Log warnings and more severe errors
}"

# Write the Nginx configuration to the sites-available directory
# This command requires sudo. The calling GitHub Actions step should use `sudo -S bash ...`
echo "Writing Nginx configuration to /etc/nginx/sites-available/thebarcodeapi..."
echo "$NGINX_CONF_CONTENT" > /etc/nginx/sites-available/thebarcodeapi
# Alternative using tee with sudo:
# echo "$NGINX_CONF_CONTENT" | sudo tee /etc/nginx/sites-available/thebarcodeapi > /dev/null


# Enable the site by creating a symbolic link in sites-enabled
# Remove existing symlink first to prevent errors if it exists and points elsewhere
echo "Enabling Nginx site configuration..."
if [ -L /etc/nginx/sites-enabled/thebarcodeapi ]; then
  rm /etc/nginx/sites-enabled/thebarcodeapi
fi
ln -sf /etc/nginx/sites-available/thebarcodeapi /etc/nginx/sites-enabled/

# Test the Nginx configuration for syntax errors
echo "Testing Nginx configuration..."
nginx -t
if [ $? -ne 0 ]; then
  echo "Error: Nginx configuration test failed!"
  # Optionally, display the failing configuration or relevant error messages from Nginx
  exit 1
fi

echo "Nginx configuration applied and tested successfully."
echo "Remember to reload or restart Nginx service to apply changes (e.g., sudo systemctl reload nginx)."
