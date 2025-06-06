#!/bin/bash

set -e # Exit immediately on error
# set -x # For debugging test script itself

# Ensure cleanup happens on script exit, including on error from set -e or signals
trap cleanup_mocks EXIT INT TERM

TEST_DIR="$(cd "$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
INFRA_SCRIPTS_DIR="$(cd "${TEST_DIR}/.." && pwd)"
MANAGE_INFRA_SCRIPT="${GITHUB_WORKSPACE}/scripts/infra/manage-infra.sh"
LOG_FILE_TEMPLATE="$(mktemp -u)" # Template for log file names, mktemp will make unique ones
OVERALL_TEST_RESULT=0 # 0 for success, 1 for failure

# Global setup for mocks, paths will be assigned here and used by functions
MOCK_SCRIPTS_DIR_INTERNAL=""
MOCK_TOP_DIR=""
MOCK_INFRA_DIR=""
MOCK_SCRIPTS_PARENT_DIR=""
TEST_MANAGE_INFRA_SCRIPT_PATH=""
MOCK_BIN_DIR=""

# Function to set up all mocks
setup_mocks() {
    echo "Setting up mocks..." >&2
    MOCK_SCRIPTS_DIR_INTERNAL="$(mktemp -d)"
    # echo "Mock scripts temporary directory: ${MOCK_SCRIPTS_DIR_INTERNAL}" >&2

    # Mock configure-nginx.sh
    cat << EOF > "${MOCK_SCRIPTS_DIR_INTERNAL}/configure-nginx.sh"
#!/bin/bash
echo "MOCK configure-nginx.sh CALLED" >> "${CURRENT_LOG_FILE}"
echo "GLOBAL_ENV_VARS_FILE=${GLOBAL_ENV_VARS_FILE}" >> "${CURRENT_LOG_FILE}"
if [ -n "${GLOBAL_ENV_VARS_FILE}" ] && [ -f "${GLOBAL_ENV_VARS_FILE}" ]; then
  echo "configure-nginx.sh would source ${GLOBAL_ENV_VARS_FILE}" >> "${CURRENT_LOG_FILE}"
else
  echo "configure-nginx.sh ERROR: GLOBAL_ENV_VARS_FILE (${GLOBAL_ENV_VARS_FILE}) not found or not set" >> "${CURRENT_LOG_FILE}"
fi
exit 0
EOF
    chmod +x "${MOCK_SCRIPTS_DIR_INTERNAL}/configure-nginx.sh"

    # Mock configure-pm2.sh
    cat << EOF > "${MOCK_SCRIPTS_DIR_INTERNAL}/configure-pm2.sh"
#!/bin/bash
echo "MOCK configure-pm2.sh CALLED" >> "${CURRENT_LOG_FILE}"
echo "GLOBAL_ENV_VARS_FILE=${GLOBAL_ENV_VARS_FILE}" >> "${CURRENT_LOG_FILE}"
if [ -n "${GLOBAL_ENV_VARS_FILE}" ] && [ -f "${GLOBAL_ENV_VARS_FILE}" ]; then
  echo "configure-pm2.sh would source ${GLOBAL_ENV_VARS_FILE}" >> "${CURRENT_LOG_FILE}"
else
  echo "configure-pm2.sh ERROR: GLOBAL_ENV_VARS_FILE (${GLOBAL_ENV_VARS_FILE}) not found or not set" >> "${CURRENT_LOG_FILE}"
fi
exit 0
EOF
    chmod +x "${MOCK_SCRIPTS_DIR_INTERNAL}/configure-pm2.sh"

    MOCK_SCRIPT_NAMES=(
      "update-system.sh" "install-dependencies.sh" "setup-docker-env.sh" "fix-permissions.sh"
      "configure-backup-coordination.sh" "add-cleanup-routine.sh" "deploy-backend-docker.sh"
      "run-migrations.sh" "verify-setup.sh"
    )
    for script_name in "${MOCK_SCRIPT_NAMES[@]}"; do
      mock_path="${MOCK_SCRIPTS_DIR_INTERNAL}/$(basename "${script_name}")"
      cat << EOF > "${mock_path}"
#!/bin/bash
echo "MOCK $(basename "${script_name}") CALLED. Args: \$@" >> "${CURRENT_LOG_FILE}"
exit 0
EOF
      chmod +x "${mock_path}"
    done

    MOCK_TOP_DIR="$(mktemp -d)"
    # echo "Mock top directory: ${MOCK_TOP_DIR}" >&2
    MOCK_INFRA_DIR="${MOCK_TOP_DIR}/scripts/infra"
    MOCK_SCRIPTS_PARENT_DIR="${MOCK_TOP_DIR}/scripts"

    mkdir -p "${MOCK_INFRA_DIR}"
    mkdir -p "${MOCK_SCRIPTS_PARENT_DIR}"

    cp "${MOCK_SCRIPTS_DIR_INTERNAL}/configure-nginx.sh" "${MOCK_INFRA_DIR}/"
    cp "${MOCK_SCRIPTS_DIR_INTERNAL}/configure-pm2.sh" "${MOCK_INFRA_DIR}/"

    for script_name in "${MOCK_SCRIPT_NAMES[@]}"; do
      if [[ "${script_name}" == "deploy-backend-docker.sh" || "${script_name}" == "run-migrations.sh" ]]; then
        cp "${MOCK_SCRIPTS_DIR_INTERNAL}/$(basename "${script_name}")" "${MOCK_SCRIPTS_PARENT_DIR}/"
      else
        cp "${MOCK_SCRIPTS_DIR_INTERNAL}/$(basename "${script_name}")" "${MOCK_INFRA_DIR}/"
      fi
    done

    cp "${MANAGE_INFRA_SCRIPT}" "${MOCK_INFRA_DIR}/"
    TEST_MANAGE_INFRA_SCRIPT_PATH="${MOCK_INFRA_DIR}/manage-infra.sh"

    MOCK_BIN_DIR="$(mktemp -d)"
    export PATH="${MOCK_BIN_DIR}:${PATH}" # Prepend mock bin dir
    # echo "Mock bin directory: ${MOCK_BIN_DIR}" >&2

    COMMANDS_TO_MOCK=("sudo" "systemctl" "docker" "nginx" "pm2" "chown" "chmod" "mkdir" "cp" "ln" "rm" "touch" "sed" "cat" "test" "groupadd" "usermod" "apt-get" "id")
    for cmd_to_mock in "${COMMANDS_TO_MOCK[@]}"; do
      cat << EOF > "${MOCK_BIN_DIR}/${cmd_to_mock}"
#!/bin/bash
echo "MOCK CMD: ${cmd_to_mock} \$@" >> "${CURRENT_LOG_FILE}"
MARKER_FILE_PATH="/opt/thebarcodeapi/${ENVIRONMENT}/.infra_initialized"
if [ "${cmd_to_mock}" == "test" ] && [ "\${1}" == "-f" ] && [ "\${2}" == "${MARKER_FILE_PATH}" ]; then
  exit 1 # Simulate marker file not found for first-time setup
fi
if [ "${cmd_to_mock}" == "id" ] && [ "\${1}" == "-u" ]; then echo "1000"; exit 0; fi
if [ "${cmd_to_mock}" == "nginx" ] && [ "\${1}" == "-t" ]; then
    echo "nginx: the configuration file /etc/nginx/nginx.conf syntax is ok" >> "${CURRENT_LOG_FILE}"
    echo "nginx: configuration file /etc/nginx/nginx.conf test is successful" >> "${CURRENT_LOG_FILE}"
    exit 0
fi
if [ "${cmd_to_mock}" == "docker" ] && [ "\${1}" == "ps" ]; then
    echo "CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES" >> "${CURRENT_LOG_FILE}"
    exit 0
fi
if [ "${cmd_to_mock}" == "docker" ] && [ "\${1}" == "compose" ] && [ "\${2}" == "version" ]; then
    echo "Docker Compose version v2.17.2" >> "${CURRENT_LOG_FILE}"
    exit 0
fi
if [ "${cmd_to_mock}" == "cp" ]; then
    if [[ "\${1}" == *"/tmp/env_vars_infra_setup"* && "\${2}" == "/tmp/env_vars" ]] && [ -f "\$1" ]; then
        /bin/cp -f "\$1" "\$2"
        echo "Copied (actually) \${1} to \${2} for sourcing test" >> "${CURRENT_LOG_FILE}"
        exit 0
    fi
fi
exit 0
EOF
      chmod +x "${MOCK_BIN_DIR}/${cmd_to_mock}"
    done
}

cleanup_mocks() {
    echo "Cleaning up mocks..." >&2
    rm -rf "${MOCK_SCRIPTS_DIR_INTERNAL}"
    rm -rf "${MOCK_TOP_DIR}"
    if [ -n "${MOCK_BIN_DIR}" ]; then
      export PATH="$(echo "${PATH}" | sed -e "s|${MOCK_BIN_DIR}:||")"
    fi
    rm -rf "${MOCK_BIN_DIR}"
    MOCK_SCRIPTS_DIR_INTERNAL="" MOCK_TOP_DIR="" MOCK_INFRA_DIR="" MOCK_SCRIPTS_PARENT_DIR="" TEST_MANAGE_INFRA_SCRIPT_PATH="" MOCK_BIN_DIR=""
}

run_manage_infra_scenario() {
    local test_description="\$1"
    echo "--- Running Test Scenario: ${test_description} ---" >&2
    CURRENT_LOG_FILE="$(mktemp "${LOG_FILE_TEMPLATE}.XXXXXX")"
    echo "Test log for '${test_description}': ${CURRENT_LOG_FILE}" >&2
    local local_github_workspace="$(mktemp -d)"
    export GITHUB_WORKSPACE="${local_github_workspace}"
    cd "${local_github_workspace}"
    bash "${TEST_MANAGE_INFRA_SCRIPT_PATH}" >> "${CURRENT_LOG_FILE}" 2>&1
    local exit_code=\$?
    cd "${TEST_DIR}"
    rm -rf "${local_github_workspace}"
    unset GITHUB_WORKSPACE
    return \$exit_code
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
MANAGE_INFRA_EXIT_CODE=\$?

if [ \$MANAGE_INFRA_EXIT_CODE -ne 0 ]; then
    echo "FAIL (Happy Path): manage-infra.sh exited with code \$MANAGE_INFRA_EXIT_CODE. Expected 0." >&2
    cat "${CURRENT_LOG_FILE}" >&2
    OVERALL_TEST_RESULT=1
else
    echo "PASS (Happy Path): manage-infra.sh exited with code 0." >&2
    if ! grep "MOCK CMD: sudo -S bash -c cat > '/tmp/env_vars_infra_setup.*EOF" "${CURRENT_LOG_FILE}"; then
        echo "FAIL (Happy Path): GLOBAL_ENV_VARS_FILE was not created." >&2; cat "${CURRENT_LOG_FILE}" >&2; OVERALL_TEST_RESULT=1; fi
    if ! grep "MOCK configure-nginx.sh CALLED" "${CURRENT_LOG_FILE}"; then
        echo "FAIL (Happy Path): configure-nginx.sh was not called." >&2; cat "${CURRENT_LOG_FILE}" >&2; OVERALL_TEST_RESULT=1; fi
    if ! grep "configure-nginx.sh would source /tmp/env_vars_infra_setup" "${CURRENT_LOG_FILE}"; then
        echo "FAIL (Happy Path): configure-nginx.sh did not indicate sourcing GLOBAL_ENV_VARS_FILE." >&2; cat "${CURRENT_LOG_FILE}" >&2; OVERALL_TEST_RESULT=1; fi
    if ! grep "MOCK configure-pm2.sh CALLED" "${CURRENT_LOG_FILE}"; then
        echo "FAIL (Happy Path): configure-pm2.sh was not called." >&2; cat "${CURRENT_LOG_FILE}" >&2; OVERALL_TEST_RESULT=1; fi
    if ! grep "configure-pm2.sh would source /tmp/env_vars_infra_setup" "${CURRENT_LOG_FILE}"; then
        echo "FAIL (Happy Path): configure-pm2.sh did not indicate sourcing GLOBAL_ENV_VARS_FILE." >&2; cat "${CURRENT_LOG_FILE}" >&2; OVERALL_TEST_RESULT=1; fi
    if [ \$OVERALL_TEST_RESULT -eq 0 ]; then echo "--- Happy Path Test Fully Passed ---" >&2; fi
fi
rm -f "${CURRENT_LOG_FILE}"


# === Negative Tests for Missing Critical Variables ===
echo "--- Starting Negative Tests for Missing Critical Variables ---" >&2
CRITICAL_VARS=(
    "SUDO_PASSWORD" "ENVIRONMENT" "DOMAIN_NAME" "DB_PASSWORD"
    "POSTGRES_PASSWORD" "API_SECRET_KEY" "API_MASTER_KEY" "API_VERSION"
)
for var_to_unset in "${CRITICAL_VARS[@]}"; do
    current_test_failed=0
    echo "--- Testing with ${var_to_unset} unset ---" >&2
    set_default_critical_vars
    unset "${var_to_unset}"
    run_manage_infra_scenario "Missing ${var_to_unset}"
    exit_code=\$?
    if [ \$exit_code -ne 1 ]; then
        echo "FAIL (${var_to_unset} unset): manage-infra.sh exited with \${exit_code}, expected 1." >&2
        cat "${CURRENT_LOG_FILE}" >&2; current_test_failed=1; OVERALL_TEST_RESULT=1
    fi
    expected_error_msg="Error: Essential environment variable ${var_to_unset} is not set for first-time infrastructure setup."
    if ! grep -qF "${expected_error_msg}" "${CURRENT_LOG_FILE}"; then
        echo "FAIL (${var_to_unset} unset): Did not find expected error message '${expected_error_msg}'." >&2
        cat "${CURRENT_LOG_FILE}" >&2; current_test_failed=1; OVERALL_TEST_RESULT=1
    fi
    if [ \$current_test_failed -eq 0 ]; then echo "PASS (${var_to_unset} unset): Script failed as expected." >&2; fi
    rm -f "${CURRENT_LOG_FILE}"
done
if [ \$OVERALL_TEST_RESULT -eq 0 ]; then echo "--- All Negative Tests for Missing Critical Variables Passed ---" >&2; fi


# === Negative Tests for Invalid (Empty) Variable Values ===
echo "--- Starting Negative Tests for Invalid (Empty) Variable Values ---" >&2
INVALID_VALUE_TEST_VARS=("ENVIRONMENT" "DOMAIN_NAME" "API_VERSION")

for var_to_test_empty in "${INVALID_VALUE_TEST_VARS[@]}"; do
    current_test_failed=0
    echo "--- Testing with ${var_to_test_empty} set to an empty string ---" >&2
    set_default_critical_vars
    export "${var_to_test_empty}"="" # Set variable to empty string

    run_manage_infra_scenario "Invalid value: ${var_to_test_empty} empty"
    exit_code=\$?

    if [ \$exit_code -ne 1 ]; then
        echo "FAIL (${var_to_test_empty} empty): manage-infra.sh exited with \${exit_code}, expected 1." >&2
        cat "${CURRENT_LOG_FILE}" >&2; current_test_failed=1; OVERALL_TEST_RESULT=1
    fi

    expected_error_msg="Error: Essential environment variable ${var_to_test_empty} is not set for first-time infrastructure setup."
    if ! grep -qF "${expected_error_msg}" "${CURRENT_LOG_FILE}"; then
        echo "FAIL (${var_to_test_empty} empty): Did not find expected error message '${expected_error_msg}'." >&2
        cat "${CURRENT_LOG_FILE}" >&2; current_test_failed=1; OVERALL_TEST_RESULT=1
    fi

    if [ \$current_test_failed -eq 0 ]; then echo "PASS (${var_to_test_empty} empty): Script failed as expected." >&2; fi
    rm -f "${CURRENT_LOG_FILE}"
done
if [ \$OVERALL_TEST_RESULT -eq 0 ]; then echo "--- All Negative Tests for Invalid (Empty) Variable Values Passed ---" >&2; fi


# --- Final Cleanup and Exit ---
cleanup_mocks
if [ \$OVERALL_TEST_RESULT -eq 0 ]; then
    echo "All tests passed successfully!" >&2
else
    echo "One or more tests FAILED. Please review logs." >&2
fi
exit \$OVERALL_TEST_RESULT
