#!/bin/bash

# Test script for frontend deployment PM2 functionality
# This script validates that PM2 process management works correctly with process names

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test configuration
TEST_ENVIRONMENT="test"
TEST_PROCESS_NAME="thebarcodeapi-frontend-${TEST_ENVIRONMENT}"
TEST_DIR="/tmp/thebarcodeapi-frontend-test"

# Function to print test output
print_test() {
    local color=$1
    local message=$2
    echo -e "${color}[TEST] ${message}${NC}"
}

# Function to run a test and capture result
run_test() {
    local test_name=$1
    local test_command=$2
    
    print_test "$BLUE" "Running test: $test_name"
    
    if eval "$test_command"; then
        print_test "$GREEN" "✓ PASS: $test_name"
        return 0
    else
        print_test "$RED" "✗ FAIL: $test_name"
        return 1
    fi
}

# Function to check if PM2 process exists by name
pm2_process_exists() {
    local process_name=$1
    pm2 list 2>/dev/null | grep -q "$process_name" || return 1
}

# Function to check if PM2 process is running by name
pm2_process_running() {
    local process_name=$1
    pm2 list 2>/dev/null | grep "$process_name" | grep -q "online" || return 1
}

# Setup test environment
setup_test_env() {
    print_test "$BLUE" "Setting up test environment..."
    
    # Create test directory structure
    mkdir -p "$TEST_DIR"/{current,releases,logs}
    
    # Create a minimal package.json for testing
    cat > "$TEST_DIR/current/package.json" << EOF
{
  "name": "thebarcodeapi-frontend-test",
  "version": "1.0.0",
  "scripts": {
    "start": "node -e \"console.log('Test server started'); setInterval(() => {}, 1000)\""
  }
}
EOF
    
    # Create test ecosystem config
    cat > "$TEST_DIR/ecosystem.config.js" << EOF
module.exports = {
  apps: [
    {
      name: '${TEST_PROCESS_NAME}',
      script: 'npm',
      args: 'start',
      cwd: '${TEST_DIR}/current',
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      max_memory_restart: '100M',
      env: {
        NODE_ENV: 'test'
      }
    }
  ]
};
EOF
    
    print_test "$GREEN" "Test environment setup complete"
}

# Cleanup test environment
cleanup_test_env() {
    print_test "$BLUE" "Cleaning up test environment..."
    
    # Stop and delete any test PM2 processes
    if pm2_process_exists "$TEST_PROCESS_NAME"; then
        pm2 delete "$TEST_PROCESS_NAME" 2>/dev/null || true
    fi
    
    # Remove test directory
    rm -rf "$TEST_DIR"
    
    print_test "$GREEN" "Test environment cleaned up"
}

# Test PM2 process management by name
test_pm2_process_management() {
    local passed=0
    local total=0
    
    print_test "$BLUE" "Testing PM2 process management by name..."
    
    # Test 1: Start process by config file
    ((total++))
    if run_test "Start PM2 process from config" "cd '$TEST_DIR' && pm2 start ecosystem.config.js"; then
        ((passed++))
        sleep 2
    fi
    
    # Test 2: Check process exists by name
    ((total++))
    if run_test "Process exists by name" "pm2_process_exists '$TEST_PROCESS_NAME'"; then
        ((passed++))
    fi
    
    # Test 3: Check process is running by name
    ((total++))
    if run_test "Process is running by name" "pm2_process_running '$TEST_PROCESS_NAME'"; then
        ((passed++))
    fi
    
    # Test 4: Reload process by name
    ((total++))
    if run_test "Reload process by name" "pm2 reload '$TEST_PROCESS_NAME'"; then
        ((passed++))
        sleep 2
    fi
    
    # Test 5: Check process still running after reload
    ((total++))
    if run_test "Process running after reload" "pm2_process_running '$TEST_PROCESS_NAME'"; then
        ((passed++))
    fi
    
    # Test 6: Restart process by name
    ((total++))
    if run_test "Restart process by name" "pm2 restart '$TEST_PROCESS_NAME'"; then
        ((passed++))
        sleep 2
    fi
    
    # Test 7: Check process still running after restart
    ((total++))
    if run_test "Process running after restart" "pm2_process_running '$TEST_PROCESS_NAME'"; then
        ((passed++))
    fi
    
    # Test 8: Stop process by name
    ((total++))
    if run_test "Stop process by name" "pm2 stop '$TEST_PROCESS_NAME'"; then
        ((passed++))
    fi
    
    # Test 9: Check process is stopped
    ((total++))
    if run_test "Process is stopped" "! pm2_process_running '$TEST_PROCESS_NAME'"; then
        ((passed++))
    fi
    
    # Test 10: Delete process by name
    ((total++))
    if run_test "Delete process by name" "pm2 delete '$TEST_PROCESS_NAME'"; then
        ((passed++))
    fi
    
    print_test "$BLUE" "PM2 process management tests: $passed/$total passed"
    
    if [ $passed -eq $total ]; then
        print_test "$GREEN" "All PM2 process management tests passed!"
        return 0
    else
        print_test "$RED" "Some PM2 process management tests failed!"
        return 1
    fi
}

# Test deployment script functions
test_deployment_script_functions() {
    local passed=0
    local total=0
    
    print_test "$BLUE" "Testing deployment script functions..."
    
    # Source the deployment script functions
    source "$(dirname "$0")/deploy-frontend.sh" 2>/dev/null || {
        print_test "$RED" "Could not source deploy-frontend.sh"
        return 1
    }
    
    # Test 1: pm2_process_exists function with non-existent process
    ((total++))
    if run_test "pm2_process_exists with non-existent process" "! pm2_process_exists 'non-existent-process'"; then
        ((passed++))
    fi
    
    # Test 2: pm2_process_running function with non-existent process  
    ((total++))
    if run_test "pm2_process_running with non-existent process" "! pm2_process_running 'non-existent-process'"; then
        ((passed++))
    fi
    
    print_test "$BLUE" "Deployment script function tests: $passed/$total passed"
    
    if [ $passed -eq $total ]; then
        print_test "$GREEN" "All deployment script function tests passed!"
        return 0
    else
        print_test "$RED" "Some deployment script function tests failed!"
        return 1
    fi
}

# Test script validation
test_script_validation() {
    local passed=0
    local total=0
    
    print_test "$BLUE" "Testing script validation..."
    
    # Test 1: Check if deploy-frontend.sh exists and is executable
    ((total++))
    if run_test "deploy-frontend.sh exists and is executable" "[ -x '$(dirname "$0")/deploy-frontend.sh' ]"; then
        ((passed++))
    fi
    
    # Test 2: Check if ecosystem.config.js exists
    ((total++))
    if run_test "ecosystem.config.js exists" "[ -f '$(dirname "$0")/ecosystem.config.js' ]"; then
        ((passed++))
    fi
    
    # Test 3: Validate deploy-frontend.sh syntax
    ((total++))
    if run_test "deploy-frontend.sh syntax validation" "bash -n '$(dirname "$0")/deploy-frontend.sh'"; then
        ((passed++))
    fi
    
    # Test 4: Validate ecosystem.config.js syntax
    ((total++))
    if run_test "ecosystem.config.js syntax validation" "node -c '$(dirname "$0")/ecosystem.config.js'"; then
        ((passed++))
    fi
    
    print_test "$BLUE" "Script validation tests: $passed/$total passed"
    
    if [ $passed -eq $total ]; then
        print_test "$GREEN" "All script validation tests passed!"
        return 0
    else
        print_test "$RED" "Some script validation tests failed!"
        return 1
    fi
}

# Main test runner
main() {
    print_test "$BLUE" "Starting frontend deployment PM2 tests..."
    
    local test_results=0
    
    # Run script validation tests
    if ! test_script_validation; then
        ((test_results++))
    fi
    
    # Check if PM2 is available for process management tests
    if command -v pm2 >/dev/null 2>&1; then
        # Setup test environment
        setup_test_env
        
        # Ensure we cleanup on exit
        trap cleanup_test_env EXIT
        
        # Run PM2 process management tests
        if ! test_pm2_process_management; then
            ((test_results++))
        fi
        
        # Run deployment script function tests
        if ! test_deployment_script_functions; then
            ((test_results++))
        fi
        
    else
        print_test "$YELLOW" "PM2 not available, skipping process management tests"
        print_test "$YELLOW" "Install PM2 with: npm install -g pm2"
    fi
    
    if [ $test_results -eq 0 ]; then
        print_test "$GREEN" "🎉 All tests passed!"
        exit 0
    else
        print_test "$RED" "❌ Some tests failed!"
        exit 1
    fi
}

# Run tests
main "$@"