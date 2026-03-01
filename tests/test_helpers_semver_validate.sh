#!/usr/bin/env bash
set -euo pipefail

# Define CWD for relative paths if not already set
CWD="${CWD:-$(pwd)}"
LIB_DIR="${CWD}/scripts/lib"

# Source dependencies
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

echo "Testing semver_validate..."

failed=0

assert_valid() {
  local input="$1"
  local desc="$2"

  if semver_validate "$input"; then
    echo "[PASS] $desc: '$input' -> Valid"
  else
    echo "[FAIL] $desc: '$input' -> Invalid (Expected valid)"
    failed=1
  fi
}

assert_invalid() {
  local input="$1"
  local desc="$2"

  if semver_validate "$input"; then
    echo "[FAIL] $desc: '$input' -> Valid (Expected invalid)"
    failed=1
  else
    echo "[PASS] $desc: '$input' -> Invalid as expected"
  fi
}

# Run tests
assert_valid "1.2.3" "Standard semver"
assert_valid "v1.2.3" "Standard semver with 'v'"
assert_valid "1.2.3-beta.1" "Pre-release"
assert_valid "1.2.3+build.123" "Build metadata"
assert_valid "1.2.3-beta.1+build.123" "Pre-release and build metadata"
assert_valid "v2.0.0-rc.1" "RC with 'v'"
assert_valid "0.0.1" "Zero semver"
assert_valid "10.20.30" "Multi-digit semver"

assert_invalid "v1.2a.3" "Letters in version core"
assert_invalid "" "Empty string"
assert_invalid "v" "Just 'v'"
assert_invalid "1.2.3.4" "Four-part version"
assert_invalid "1.2" "Two-part version"
assert_invalid "beta-1.2.3" "Prefix instead of suffix"
assert_invalid "1.02.3" "Leading zeros"
assert_invalid "1.2.3-01" "Leading zeros in pre-release"

if [[ "$failed" -ne 0 ]]; then
  echo "Some tests failed."
  false
else
  echo "All tests passed."
  true
fi
