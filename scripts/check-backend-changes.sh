# ---
# Purpose:
#   Checks for changes in the backend codebase to determine if a new deployment is necessary.
#   Compares the current HEAD commit with the commit hash stored from the previous successful deployment.
#   For first-time deployments or if the deployed commit hash is not found, it forces an update.
#
# Environment Variables:
#   - ENVIRONMENT: The deployment environment (e.g., staging, production). Used to locate deployment paths.
#   - GITHUB_EVENT_NAME: The name of the GitHub event that triggered the workflow (e.g., push, workflow_dispatch).
#                        Used to determine the diff strategy.
#   - GITHUB_OUTPUT: Path to the GitHub Actions output file. Used to set 'changes=true' or 'changes=false'.
#
# Outputs:
#   - Sets 'changes=true' to GITHUB_OUTPUT if changes are detected or if it's a forced update.
#   - Sets 'changes=false' to GITHUB_OUTPUT if no changes are detected.
# ---
#!/bin/bash
set -e

# Debug information
echo "Current directory: $(pwd)"
echo "Event type: ${GITHUB_EVENT_NAME}"
echo "Git branch: $(git rev-parse --abbrev-ref HEAD)"

# Check if this is a first deployment (no data directory for the environment exists yet)
if [ ! -d "/opt/thebarcodeapi/${ENVIRONMENT}/releases/data" ]; then
  echo "First deployment detected for environment ${ENVIRONMENT} (data directory missing)."
  echo "changes=true" >> $GITHUB_OUTPUT
  exit 0
fi

# Determine diff strategy based on the event type
if [ "${GITHUB_EVENT_NAME}" = "workflow_dispatch" ]; then
  # For manual triggers (workflow_dispatch), compare HEAD with the .git-commit file of the currently deployed version.
  echo "Workflow event is 'workflow_dispatch'. Comparing with deployed .git-commit."
  if [ -f "/opt/thebarcodeapi/barcodeApi/.git-commit" ]; then
    DEPLOYED_COMMIT=$(cat "/opt/thebarcodeapi/barcodeApi/.git-commit")
    echo "Found deployed commit: ${DEPLOYED_COMMIT}"

    # Verify the commit exists in git history. If not, it might be an old or invalid commit hash.
    if git rev-parse --verify "${DEPLOYED_COMMIT}^{commit}" >/dev/null 2>&1; then
      echo "Comparing changes between deployed commit ${DEPLOYED_COMMIT} and current HEAD."
      # List of paths to check for backend changes
      CHANGES=$(git diff --name-only "${DEPLOYED_COMMIT}" HEAD -- \
        'api/' \
        'alembic/' \
        'requirements.txt' \
        'Dockerfile' \
        '*.yml' \
        '*.ini' \
        'scripts/' \
        '*.sh' \
        '.github/workflows/' \
        || true) # `|| true` ensures the command doesn't fail if no changes are found (git diff returns 1)
    else
      echo "Deployed commit ${DEPLOYED_COMMIT} not found in history. Forcing update."
      CHANGES="force_update" # Mark as changed if deployed commit is invalid
    fi
  else
    echo "No .git-commit file found in current backend deployment at /opt/thebarcodeapi/barcodeApi/.git-commit. Forcing update."
    CHANGES="force_update" # Mark as changed if .git-commit is missing
  fi
else
  # For automated triggers (e.g., push), compare HEAD with its previous commit (HEAD^).
  # This assumes deployments happen on every push to the monitored branch.
  echo "Workflow event is not 'workflow_dispatch' (e.g., push). Comparing HEAD with HEAD^."
  CHANGES=$(git diff --name-only HEAD^ HEAD -- \
    'api/' \
    'alembic/' \
    'requirements.txt' \
    'Dockerfile' \
    '*.yml' \
    '*.ini' \
    'scripts/' \
    '*.sh' \
    || true) # `|| true` ensures the command doesn't fail if no changes are found
fi

# Output results
if [ ! -z "$CHANGES" ]; then
  echo "Backend changes detected:"
  echo "$CHANGES"
  echo "changes=true" >> $GITHUB_OUTPUT
else
  echo "No backend changes detected."
  echo "changes=false" >> $GITHUB_OUTPUT
fi

# Debug output: show the git diff output (if any) for automated triggers again for clarity
if [ "${GITHUB_EVENT_NAME}" != "workflow_dispatch" ]; then
  echo "Git diff output (HEAD vs HEAD^):"
  git diff --name-only HEAD^ HEAD || true
fi
