#!/bin/bash

# Don't use set -e since we want to test failure cases

# Ensure cleanup happens on script exit
trap 'cleanup_mocks; exit $?' EXIT
trap 'cleanup_mocks; exit 130' INT
trap 'cleanup_mocks; exit 143' TERM

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_SCRIPTS_DIR="$(cd "${TEST_DIR}/.." && pwd)"
if [ -z "${GITHUB_WORKSPACE}" ]; then
    GITHUB_WORKSPACE="$(cd "${TEST_DIR}/../../.." && pwd)"
fi
MANAGE_INFRA_SCRIPT="${GITHUB_WORKSPACE}/scripts/infra/manage-infra.sh"
OVERALL_TEST_RESULT=0 # 0 for success, 1 for failure

# Global setup for mocks
MOCK_BIN_DIR=""
MOCK_SCRIPTS_DIR=""
ORIGINAL_PATH=""

# Function to set up all mocks
setup_mocks() {
    ORIGINAL_PATH="${PATH}"
    echo "Setting up mocks..." >&2
    MOCK_BIN_DIR="$(mktemp -d)"
    export PATH="${MOCK_BIN_DIR}:${PATH}"

    # Create comprehensive sudo mock that handles all scenarios
    cat << 'EOF' > "${MOCK_BIN_DIR}/sudo"
#!/bin/bash
echo "MOCK sudo: $@" >&2

# Handle marker file test - simulate not found for first-time setup
if [ "$1" == "-S" ] && [ "$2" == "test" ] && [ "$3" == "-f" ] && [[ "$4" == *".infra_initialized" ]]; then
    exit 1
fi

# Handle general -S commands (reading password from stdin)
if [ "$1" == "-S" ]; then
    # Read password from stdin (but we don't need to validate it in the mock)
    read -r password_input
    shift  # Remove -S flag

    # Handle specific commands that exec_sudo uses
    case "$1" in
        "test")
            if [ "$2" == "-f" ] && [[ "$3" == *".infra_initialized" ]]; then
                exit 1  # Marker file not found
            fi
            exit 0
            ;;
        "bash")
            # For bash script execution, just succeed
            exit 0
            ;;
        "mkdir"|"chown"|"chmod"|"systemctl"|"rm")
            # For basic system commands, succeed
            exit 0
            ;;
        *)
            # For any other commands, succeed
            exit 0
            ;;
    esac
fi

# For all other commands, succeed
exit 0
EOF
    chmod +x "${MOCK_BIN_DIR}/sudo"

    # Create mock scripts for infrastructure components
    local scripts_to_mock=(
        "update-system.sh"
        "install-dependencies.sh"
        "setup-docker-env.sh"
        "fix-permissions.sh"
        "configure-backup-coordination.sh"
        "add-cleanup-routine.sh"
        "configure-nginx.sh"
        "configure-pm2.sh"
        "verify-setup.sh"
    )

    # Create a temporary scripts directory structure
    MOCK_SCRIPTS_DIR="$(mktemp -d)"
    mkdir -p "${MOCK_SCRIPTS_DIR}/scripts/infra"

    # Copy the real manage-infra.sh to the mock directory
    cp "${MANAGE_INFRA_SCRIPT}" "${MOCK_SCRIPTS_DIR}/scripts/infra/"

    for script in "${scripts_to_mock[@]}"; do
        cat << 'MOCK_SCRIPT_EOF' > "${MOCK_SCRIPTS_DIR}/scripts/infra/${script}"
#!/bin/bash
echo "MOCK ${script}: $@" >&2
exit 0
MOCK_SCRIPT_EOF
        chmod +x "${MOCK_SCRIPTS_DIR}/scripts/infra/${script}"
    done

    # Update the MANAGE_INFRA_SCRIPT to point to our mock copy
    MANAGE_INFRA_SCRIPT="${MOCK_SCRIPTS_DIR}/scripts/infra/manage-infra.sh"

    echo "Mocks set up successfully" >&2
}

cleanup_mocks() {
    if [ -n "${ORIGINAL_PATH}" ]; then
        PATH="${ORIGINAL_PATH}"
    fi
    echo "Cleaning up mocks..." >&2
    if [ -n "${MOCK_BIN_DIR}" ]; then
        rm -rf "${MOCK_BIN_DIR}"
    fi
    if [ -n "${MOCK_SCRIPTS_DIR}" ]; then
        rm -rf "${MOCK_SCRIPTS_DIR}"
    fi
    MOCK_BIN_DIR=""
    MOCK_SCRIPTS_DIR=""
    ORIGINAL_PATH=""
}

run_manage_infra_scenario() {
    local test_description="$1"
    echo "--- Running Test Scenario: ${test_description} ---" >&2

    local local_github_workspace="$(mktemp -d)"
    export GITHUB_WORKSPACE="${local_github_workspace}"
    cd "${local_github_workspace}"

    local exit_code=0
    timeout 30 bash "${MANAGE_INFRA_SCRIPT}" >/dev/null 2>&1
    exit_code=$?

    cd "${TEST_DIR}"
    rm -rf "${local_github_workspace}"
    unset GITHUB_WORKSPACE
    return $exit_code
}

set_default_critical_vars() {
    export SUDO_PASSWORD="testpassword"
    export ENVIRONMENT="testenv"
    export DOMAIN_NAME="test.example.com"
    export DB_PASSWORD="testdbpassword"
    export POSTGRES_PASSWORD="testpostgrespassword"
    export API_SECRET_KEY="testapikey"
    export API_MASTER_KEY="testmasterkey"
    export API_VERSION="0.0.1"
    export ALGORITHM="HS256"
    export ACCESS_TOKEN_EXPIRE_MINUTES="30"
    export REDIS_URL="redis://redis:6379/1"
    export LOG_DIRECTORY="/app/logs"
}

# --- Main Test Execution ---
setup_mocks

# === Happy Path Test ===
echo "--- Starting Happy Path Test ---" >&2
set_default_critical_vars
run_manage_infra_scenario "Happy Path - All variables set"
MANAGE_INFRA_EXIT_CODE=$?

if [ $MANAGE_INFRA_EXIT_CODE -ne 0 ]; then
    echo "FAIL (Happy Path): manage-infra.sh exited with code $MANAGE_INFRA_EXIT_CODE. Expected 0." >&2
    OVERALL_TEST_RESULT=1
else
    echo "PASS (Happy Path): manage-infra.sh exited with code 0." >&2
fi

# === Negative Tests for Missing Critical Variables ===
echo "--- Starting Negative Tests for Missing Critical Variables ---" >&2
CRITICAL_VARS=(
    "SUDO_PASSWORD" "ENVIRONMENT" "DOMAIN_NAME" "DB_PASSWORD"
    "POSTGRES_PASSWORD" "API_SECRET_KEY" "API_MASTER_KEY" "API_VERSION"
)

for var_to_unset in "${CRITICAL_VARS[@]}"; do
    echo "--- Testing with ${var_to_unset} unset ---" >&2
    set_default_critical_vars
    unset "${var_to_unset}"
    run_manage_infra_scenario "Missing ${var_to_unset}"
    exit_code=$?
    if [ $exit_code -ne 1 ]; then
        echo "FAIL (${var_to_unset} unset): manage-infra.sh exited with ${exit_code}, expected 1." >&2
        OVERALL_TEST_RESULT=1
    else
        echo "PASS (${var_to_unset} unset): Script failed as expected." >&2
    fi
done

# === Negative Tests for Invalid (Empty) Variable Values ===
echo "--- Starting Negative Tests for Invalid (Empty) Variable Values ---" >&2
INVALID_VALUE_TEST_VARS=("ENVIRONMENT" "DOMAIN_NAME" "API_VERSION")

for var_to_test_empty in "${INVALID_VALUE_TEST_VARS[@]}"; do
    echo "--- Testing with ${var_to_test_empty} set to an empty string ---" >&2
    set_default_critical_vars
    export "${var_to_test_empty}"="" # Set variable to empty string

    run_manage_infra_scenario "Invalid value: ${var_to_test_empty} empty"
    exit_code=$?

    if [ $exit_code -ne 1 ]; then
        echo "FAIL (${var_to_test_empty} empty): manage-infra.sh exited with ${exit_code}, expected 1." >&2
        OVERALL_TEST_RESULT=1
    else
        echo "PASS (${var_to_test_empty} empty): Script failed as expected." >&2
    fi
done

# --- Final Results ---
cleanup_mocks
if [ $OVERALL_TEST_RESULT -eq 0 ]; then
    echo "All tests passed successfully!" >&2
else
    echo "One or more tests FAILED. Please review output above." >&2
fi
exit $OVERALL_TEST_RESULT
