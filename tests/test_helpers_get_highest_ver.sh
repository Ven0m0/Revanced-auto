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

echo "Testing get_highest_ver..."

failed=0

assert_highest() {
  local input="$1"
  local expected="$2"
  local desc="$3"

  local actual
  # Capture output, discard stderr
  if actual=$(echo -ne "$input" | get_highest_ver 2>/dev/null); then
    # Trim leading and trailing whitespace without altering internal whitespace
    actual="${actual#"${actual%%[![:space:]]*}"}"
    actual="${actual%"${actual##*[![:space:]]}"}"
    if [[ "$actual" == "$expected" ]]; then
      echo "[PASS] $desc: '$expected'"
    else
      echo "[FAIL] $desc: Expected '$expected', got '$actual'"
      failed=1
    fi
  else
    echo "[FAIL] $desc: Failed unexpectedly"
    failed=1
  fi
}

assert_failure() {
  local input="$1"
  local desc="$2"

  if echo -ne "$input" | get_highest_ver >/dev/null 2>&1; then
    echo "[FAIL] $desc: Succeeded (Expected failure)"
    failed=1
  else
    echo "[PASS] $desc: Failed as expected"
  fi
}

# --- Valid inputs ---
assert_highest "1.0.0\n2.0.0\n1.5.0" "2.0.0" "Standard semver versions"
assert_highest "1.0.0" "1.0.0" "Single version"
assert_highest "10.0.0\n2.0.0\n9.9.9" "10.0.0" "Multi-digit semver versions"
assert_highest "1.2.3-beta.1\n1.2.3-alpha.1\n1.2.3" "1.2.3-beta.1" "Pre-release vs release versions"
assert_highest "1.2.3-alpha.1\n1.2.3-beta.1" "1.2.3-beta.1" "Pre-release sorting"

# Non-semver input (returns first element as-is)
assert_highest "2023.10.25\n2022.01.01" "2023.10.25" "Date-based non-semver (returns first)"
assert_highest "custom-version-1\ncustom-version-2" "custom-version-1" "Custom non-semver string (returns first)"

# --- Invalid inputs ---
echo "--- Testing error conditions ---"

assert_failure "" "Empty input"

if [[ "$failed" -ne 0 ]]; then
  echo "Some tests failed."
  false
else
  echo "All tests passed."
fi
