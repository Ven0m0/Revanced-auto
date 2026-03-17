#!/usr/bin/env bash
set -euo pipefail

# Define CWD for relative paths if not already set
CWD="${CWD:-$(pwd)}"
LIB_DIR="${CWD}/scripts/lib"

# Source the actual library
if [[ -f "${LIB_DIR}/logger.sh" ]]; then
  source "${LIB_DIR}/logger.sh"
else
  echo "Error: logger.sh not found at ${LIB_DIR}/logger.sh"
  false
fi

# Mock abort to prevent exit
abort() {
  echo "ABORT: $*"
}

if [[ -f "${LIB_DIR}/gmscore.sh" ]]; then
  source "${LIB_DIR}/gmscore.sh"
else
  echo "Error: gmscore.sh not found at ${LIB_DIR}/gmscore.sh"
  false
fi

echo "Testing _get_gmscore_repo mapping..."

failed=0

assert_repo() {
  local provider=$1
  local expected=$2
  local actual
  actual=$(_get_gmscore_repo "$provider")

  if [[ "$actual" == "$expected" ]]; then
    echo "[PASS] Provider '$provider' maps to '$expected'"
  else
    echo "[FAIL] Provider '$provider' maps to '$actual' (Expected '$expected')"
    failed=1
  fi
}

assert_repo "revanced" "ReVanced/GmsCore"
assert_repo "morphe" "MorpheApp/MicroG-RE"
assert_repo "rex" "YT-Advanced/GmsCore"

echo "Testing error case..."
if _get_gmscore_repo "invalid" | grep -q "ABORT: Unknown GmsCore provider: invalid"; then
  echo "[PASS] Invalid provider correctly aborts"
else
  echo "[FAIL] Invalid provider did not abort correctly"
  failed=1
fi

if [[ "$failed" -ne 0 ]]; then
  echo "Some tests failed."
  exit 1
else
  echo "All tests passed."
  exit 0
fi
