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
  echo "No frontend changes detected."
  echo "changes=false" >> $GITHUB_OUTPUT
fi
