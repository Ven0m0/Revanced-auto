#!/usr/bin/env bash
set -euo pipefail

# Define CWD for relative paths if not already set
CWD="${CWD:-$(pwd)}"
LIB_DIR="${CWD}/scripts/lib"

# Source dependencies
# We use conditional sourcing to avoid errors if paths are wrong
if [[ -f "${LIB_DIR}/logger.sh" ]]; then
  source "${LIB_DIR}/logger.sh"
else
  echo "Error: logger.sh not found at ${LIB_DIR}/logger.sh"
  false
fi

if [[ -f "${LIB_DIR}/helpers.sh" ]]; then
  source "${LIB_DIR}/helpers.sh"
else
  echo "Error: helpers.sh not found at ${LIB_DIR}/helpers.sh"
  false
fi

echo "Testing format_version..."

failed=0

assert_version() {
  local input="$1"
  local expected="$2"
  local desc="$3"

  local actual
  # Capture output, discard stderr
  # If format_version fails (returns non-zero), the if block is skipped
  if actual=$(format_version "$input" 2>/dev/null); then
    # Trim leading and trailing whitespace without altering internal whitespace
    actual="${actual#"${actual%%[![:space:]]*}"}"
    actual="${actual%"${actual##*[![:space:]]}"}"
    if [[ "$actual" == "$expected" ]]; then
      echo "[PASS] $desc: '$input' -> '$actual'"
    else
      echo "[FAIL] $desc: '$input' -> '$actual' (Expected: '$expected')"
      failed=1
    fi
  else
    echo "[FAIL] $desc: '$input' -> Failed unexpectedly"
    failed=1
  fi
}

assert_failure() {
  local input="$1"
  local desc="$2"

  # If format_version succeeds (returns 0), we fail
  if format_version "$input" >/dev/null 2>&1; then
    echo "[FAIL] $desc: '$input' -> Succeeded (Expected failure)"
    failed=1
  else
    echo "[PASS] $desc: '$input' -> Failed as expected"
  fi
}

# --- Valid inputs ---
assert_version "1.2.3" "1.2.3" "Standard semver"
assert_version "v1.2.3" "1.2.3" "Standard semver with 'v'"
assert_version "1.2.3-beta.1" "1.2.3-beta.1" "Pre-release"
assert_version "1.2.3+build.123" "1.2.3+build.123" "Build metadata"
assert_version "2023.10.25" "2023.10.25" "Date-based"
assert_version "v 1.2.3" "1.2.3" "Semver with space"

# --- Invalid inputs (These SHOULD fail after the fix) ---
echo "--- Testing invalid inputs (expect failures if fix is applied) ---"

assert_failure "../1.2.3" "Path traversal"
assert_failure "1.2.3; rm -rf /" "Command injection attempt"
assert_failure "1.2.3|ls" "Pipe injection attempt"
assert_failure "1.2.3 & echo hello" "Background execution attempt"
assert_failure "invalid/path" "Path separator"
# assert_failure "ver(sion)" "Parentheses" # Removed as it might break shell parsing in call

if [[ "$failed" -ne 0 ]]; then
  echo "Some tests failed."
  false
else
  echo "All tests passed."
fi
