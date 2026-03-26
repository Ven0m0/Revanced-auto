#!/usr/bin/env bash
set -euo pipefail
# Integration test for workflow improvements
# Tests parallel builds, job tracking, app-specific logs, and build status tracking
# Source utilities
source utils.sh
# Test configuration
TEST_CONFIG="tests/fixtures/test_integration.toml"
TEST_BUILD_DIR="test-build"
TEST_TEMP_DIR="test-temp"
# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'
# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
# Helper functions
test_start() {
  local test_name=$1
  ((TESTS_RUN++))
  echo "Running test: $test_name"
}
test_pass() {
  echo -e "${GREEN}✓ PASSED${NC}"
  ((TESTS_PASSED++))
}
test_fail() {
  local msg=$1
  echo -e "${RED}✗ FAILED: $msg${NC}"
  ((TESTS_FAILED++))
}
test_skip() {
  local msg=$1
  echo -e "${YELLOW}⊘ SKIPPED: $msg${NC}"
}
setup() {
  echo "Setting up test environment..."
  rm -rf "$TEST_BUILD_DIR" "$TEST_TEMP_DIR"
  mkdir -p "$TEST_BUILD_DIR" "$TEST_TEMP_DIR"
  # Create test config with 2+ apps enabled
  cat > "$TEST_CONFIG" << 'EOF'
parallel-jobs = 2
patches-version = "dev"
cli-version = "dev"
[App1]
enabled = true
app-name = "TestApp1"
apkmirror-dlurl = "https://apkmirror.com/apk/test1"
version = "auto"
[App2]
enabled = true
app-name = "TestApp2"
apkmirror-dlurl = "https://apkmirror.com/apk/test2"
version = "auto"
EOF
  echo "Test setup complete"
}
teardown() {
  echo "Cleaning up test environment..."
  rm -rf "$TEST_BUILD_DIR" "$TEST_TEMP_DIR" "$TEST_CONFIG"
}
test_parallel_builds() {
  test_start "Parallel builds with 2+ apps enabled"
  # This is a basic test that verifies build.sh can parse and process multiple apps
  # Full build test would require network access and prebuilts
  local tables
  tables=$(./build.sh "$TEST_CONFIG" --config-update 2>/dev/null || echo "")
  if [[ -n "$tables" ]]; then
    test_pass
  else
    test_fail "Could not process config"
  fi
}
test_app_specific_logs() {
  test_start "App-specific log files creation"
  # Test that BUILD_LOG_FILE is used correctly
  export BUILD_LOG_FILE="${TEST_BUILD_DIR}/test-app.md"
  log "Test log entry"
  if [[ -f "${TEST_BUILD_DIR}/test-app.md" ]] && grep -q "Test log entry" "${TEST_BUILD_DIR}/test-app.md"; then
    test_pass
  else
    test_fail "Log file not created or content missing"
  fi
  rm -f "${TEST_BUILD_DIR}/test-app.md"
}
test_job_tracking_arrays() {
  test_start "Job tracking arrays initialization"
  # Check that build.sh declares job tracking arrays
  if grep -q "declare -A JOB_NAMES=" build.sh && grep -q "declare -a JOB_PIDS=" build.sh; then
    test_pass
  else
    test_fail "Job tracking arrays not found"
  fi
}
test_build_status_tracking() {
  test_start "Build status tracking initialization"
  # Check that build.sh declares BUILD_STATUS array
  if grep -q "declare -A BUILD_STATUS=" build.sh; then
    test_pass
  else
    test_fail "Build status tracking array not found"
  fi
}
test_concurrency_config() {
  test_start "Concurrency configuration in workflows"
  # Check that build.yml has cancel-in-progress: true
  if grep -q "cancel-in-progress: true" .github/workflows/build.yml; then
    test_pass
  else
    test_fail "Concurrency not configured correctly"
  fi
}
test_cache_config() {
  test_start "CI caching configuration in workflows"
  # Check that build.yml has cache step for temp/ directory
  if grep -q "path: ./temp" .github/workflows/build.yml && grep -q "revanced-prebuilts" .github/workflows/build.yml; then
    test_pass
  else
    test_fail "Cache not configured correctly"
  fi
}
test_parallel_jobs_config() {
  test_start "Parallel-jobs auto-detection in config.toml"
  # Check that config.toml has parallel-jobs = 0
  if grep -q "parallel-jobs = 0" config.toml; then
    test_pass
  else
    test_fail "Parallel-jobs not set to auto-detect"
  fi
}
test_from_ci_removed() {
  test_start "from_ci parameter removed from workflows"
  # Check that build.yml and build-daily.yml don't have from_ci parameter
  if ! grep -q "from_ci:" .github/workflows/build.yml && ! grep -q "from_ci:" .github/workflows/build-daily.yml; then
    test_pass
  else
    test_fail "from_ci parameter still exists"
  fi
}
test_artifact_upload_warn() {
  test_start "Artifact upload uses warn instead of error"
  # Check that build-manual.yml uses if-no-files-found: warn
  if grep -q "if-no-files-found: warn" .github/workflows/build-manual.yml; then
    test_pass
  else
    test_fail "Artifact upload not configured to warn"
  fi
}
test_release_condition() {
  test_start "Release job condition simplified"
  # Check that build.yml has simplified release condition
  if grep -q "github.repository == github.event.repository.full_name" .github/workflows/build.yml; then
    test_pass
  else
    test_fail "Release condition not simplified"
  fi
}
print_summary() {
  echo ""
  echo "===================="
  echo "Test Summary"
  echo "===================="
  echo "Tests run:    $TESTS_RUN"
  echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
  echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
  echo "===================="
  if [[ $TESTS_FAILED -eq 0 ]]; then
    echo -e "${GREEN}All tests passed!${NC}"
    return 0
  else
    echo -e "${RED}Some tests failed!${NC}"
    return 1
  fi
}
# Run tests
echo "Starting workflow integration tests..."
echo ""
setup
echo ""
test_parallel_builds
test_app_specific_logs
test_job_tracking_arrays
test_build_status_tracking
test_concurrency_config
test_cache_config
test_parallel_jobs_config
test_from_ci_removed
test_artifact_upload_warn
test_release_condition
teardown
print_summary
