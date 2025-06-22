# ---
# Purpose:
#   Checks for changes in the frontend codebase to determine if a new deployment is necessary.
#   Compares the current HEAD commit with the commit hash stored from the previous successful deployment
#   (found in /opt/thebarcodeapi/${ENVIRONMENT}/current/.git-commit).
#   For first-time deployments or if the deployed commit hash is not found/invalid, it forces an update.
#
# Environment Variables:
#   - ENVIRONMENT: The deployment environment (e.g., staging, production). Used to locate deployment paths.
#   - GITHUB_OUTPUT: Path to the GitHub Actions output file. Used to set 'changes=true' or 'changes=false'.
#     (Note: The script itself uses $GITHUB_OUTPUT directly as per Actions runner environment)
#
# Outputs:
#   - Sets 'changes=true' to GITHUB_OUTPUT if changes are detected in specified frontend paths or if it's a forced update.
#   - Sets 'changes=false' to GITHUB_OUTPUT if no changes are detected.
# ---
#!/bin/bash
set -e

# Check if this is a first deployment (no 'current' directory for the environment exists yet)
if [ ! -d "/opt/thebarcodeapi/${ENVIRONMENT}/current" ]; then
  echo "First deployment detected for environment ${ENVIRONMENT} ('current' directory missing)."
  echo "changes=true" >> $GITHUB_OUTPUT
  exit 0
fi

CURRENT_DIR="/opt/thebarcodeapi/${ENVIRONMENT}/current"
GIT_COMMIT_FILE="${CURRENT_DIR}/.git-commit"

# Check if the .git-commit file exists in the current deployment directory
if [ -f "${GIT_COMMIT_FILE}" ]; then
  DEPLOYED_COMMIT=$(cat "${GIT_COMMIT_FILE}")
  echo "Found deployed commit: ${DEPLOYED_COMMIT} in ${GIT_COMMIT_FILE}"

  # Verify the commit hash is a valid commit in the repository's history
  if git rev-parse --verify "${DEPLOYED_COMMIT}^{commit}" >/dev/null 2>&1; then
    echo "Comparing changes between deployed commit ${DEPLOYED_COMMIT} and current HEAD."
    # Define the specific frontend paths to check for changes
    FRONTEND_PATHS=(
      'src/'
      'public/'
      'package.json'
      'package-lock.json'
      'next.config.js'
      'tailwind.config.js'
      # Add other relevant frontend files or directories here
    )
    CHANGES=$(git diff --name-only "${DEPLOYED_COMMIT}" HEAD -- "${FRONTEND_PATHS[@]}" || true)
    # `|| true` ensures the command doesn't fail if no changes are found (git diff returns 1)
  else
    # If the deployed commit hash is not found in history, it's an invalid or very old commit. Force update.
    echo "Deployed commit ${DEPLOYED_COMMIT} not found in Git history. Forcing update."
    CHANGES="force_update"
  fi
else
  # If .git-commit file is missing, it's likely a first deployment or an incomplete previous deployment. Force update.
  echo "No .git-commit file found in ${CURRENT_DIR}. Forcing update."
  CHANGES="force_update"
fi

# Output results based on whether changes were detected
if [ ! -z "$CHANGES" ]; then
  echo "Frontend changes detected (or forced update):"
  echo "$CHANGES"
  echo "changes=true" >> $GITHUB_OUTPUT
else
  # Define PM2_APP_NAME and PM2_HOME_DIR
  PM2_APP_NAME="thebarcodeapi-frontend-${ENVIRONMENT}" # Ensure ENVIRONMENT is available
  if [ -z "$ENVIRONMENT" ]; then
    echo "Error: ENVIRONMENT variable is not set. Cannot proceed with PM2 check."
    # Optionally, set changes=true to force a full deployment pass which might re-init PM2
    # echo "changes=true" >> $GITHUB_OUTPUT
    # exit 1 # Or handle error as appropriate
  else
    echo "No frontend changes detected. Checking PM2 status for ${PM2_APP_NAME}..."

    if [ "$USER" = "root" ]; then
        PM2_HOME_DIR="/root/.pm2"
    else
        PM2_HOME_DIR="${HOME:-/home/$USER}/.pm2"
    fi

    # Check if PM2 process is running
    if PM2_HOME="${PM2_HOME_DIR}" pm2 describe "${PM2_APP_NAME}" > /dev/null 2>&1; then
      echo "PM2 process ${PM2_APP_NAME} is running."
    else
      echo "PM2 process ${PM2_APP_NAME} is not running or in a failed state. Attempting to restart/recreate..."
      # Attempt to restart
      if PM2_HOME="${PM2_HOME_DIR}" pm2 restart "${PM2_APP_NAME}"; then
        echo "Successfully restarted PM2 process ${PM2_APP_NAME}."
      else
        echo "Failed to restart PM2 process ${PM2_APP_NAME}. Attempting to start it using ecosystem file..."
        APP_DIR="/opt/thebarcodeapi/${ENVIRONMENT}/current"
        ECOSYSTEM_FILE="/opt/thebarcodeapi/${ENVIRONMENT}/ecosystem.config.js"

        if [ -f "${ECOSYSTEM_FILE}" ]; then
          # No need to cd, pm2 start command can take a full path to ecosystem file
          # and the ecosystem file itself contains the cwd for the app.
          if PM2_HOME="${PM2_HOME_DIR}" pm2 startOrRestart "${ECOSYSTEM_FILE}"; then
            echo "Successfully started/restarted PM2 process using ${ECOSYSTEM_FILE}."
          else
            echo "Error: Failed to start/restart PM2 process using ${ECOSYSTEM_FILE}."
            # Optionally, set changes=true to trigger a full deployment which includes PM2 setup
            # echo "changes=true" >> $GITHUB_OUTPUT
          fi
        else
          echo "Error: Ecosystem file ${ECOSYSTEM_FILE} not found. Cannot start PM2 process."
          # Optionally, set changes=true
          # echo "changes=true" >> $GITHUB_OUTPUT
        fi
      fi
      # Save the PM2 process list and corresponding environments
      echo "Saving PM2 state..."
      PM2_HOME="${PM2_HOME_DIR}" pm2 save --force
    fi
  fi
  # Original line for no changes
  echo "changes=false" >> $GITHUB_OUTPUT
fi
