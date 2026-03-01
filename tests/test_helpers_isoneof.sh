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

echo "Testing isoneof..."

failed=0

assert_success() {
  local target="$1"
  local desc="$2"
  shift 2

  if isoneof "$target" "$@"; then
    echo "[PASS] $desc"
  else
    echo "[FAIL] $desc (Expected success)"
    failed=1
  fi
}

assert_failure() {
  local target="$1"
  local desc="$2"
  shift 2

  if isoneof "$target" "$@" >/dev/null 2>&1; then
    echo "[FAIL] $desc (Expected failure)"
    failed=1
  else
    echo "[PASS] $desc"
  fi
}

# --- Valid inputs (Expect Success) ---
assert_success "apk" "Target is the first element" "apk" "module" "both"
assert_success "module" "Target is the middle element" "apk" "module" "both"
assert_success "both" "Target is the last element" "apk" "module" "both"
assert_success "1" "Target is numeric" "2" "1" "3"
assert_success "hello world" "Target has spaces" "foo" "hello world" "bar"
assert_success "!@#$" "Target is special characters" "%^&*" "!@#$" "()"

# --- Invalid inputs (Expect Failure) ---
assert_failure "jar" "Target is not in the list" "apk" "module" "both"
assert_failure "ap" "Target is a substring of an element" "apk" "module" "both"
assert_failure "apk" "List is empty"
assert_failure "" "Target is empty string" "apk" "module" "both"
assert_failure "apk" "List has empty string, target doesn't match" "" "module" "both"

if [[ "$failed" -ne 0 ]]; then
  echo "Some tests failed."
  false
else
  echo "All tests passed."
fi
