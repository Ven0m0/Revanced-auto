#!/bin/bash
set -euo pipefail

# Source logger mock
source lib/logger.sh

# Mock command to always succeed for testing logic
function command() {
    return 0
}
export -f command

# Mock java to return version 21
function java() {
    echo 'openjdk version "21.0.1" 2023-10-17' >&2
}
export -f java

# Source checks
source lib/checks.sh

# Override check_java_version to use our mocked java (since capturing stdout/stderr is tricky with mocks in subshells sometimes)
# actually, the original script does: java_version=$(java -version 2>&1 | head -n 1)
# So we need our mock java to output to stderr or stdout. java -version usually outputs to stderr.

echo "Testing check_system_tools..."
if check_system_tools; then
    echo "PASS: check_system_tools passed"
else
    echo "FAIL: check_system_tools failed"
    exit 1
fi

echo "Testing check_java_version..."
if check_java_version; then
    echo "PASS: check_java_version passed"
else
    echo "FAIL: check_java_version failed"
    exit 1
fi

echo "Testing check_assets..."
if check_assets; then
    echo "PASS: check_assets passed"
else
    echo "FAIL: check_assets failed"
    exit 1
fi

echo "Testing check_prerequisites..."
check_prerequisites
echo "PASS: check_prerequisites ran"