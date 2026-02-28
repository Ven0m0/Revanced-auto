#!/usr/bin/env bash
# Test script for multi-source patch support implementation
set -euo pipefail
echo "=== Multi-Source Patch Support Test Suite ==="
echo
# Source utilities
source utils.sh
test_count=0
pass_count=0
fail_count=0
run_test() {
  local test_name=$1
  local test_cmd=$2
  test_count=$((test_count + 1))
  echo "Test $test_count: $test_name"
  if eval "$test_cmd"; then
    echo "  ✓ PASS"
    pass_count=$((pass_count + 1))
  else
    echo "  ✗ FAIL"
    fail_count=$((fail_count + 1))
  fi
  echo
}
# Test 1: Multi-source config parsing
run_test "Parse multi-source config" '
toml_prep config-multi-source-test.toml
main_table=$(toml_get_table_main)
type=$(echo "$main_table" | jq -r ".\"patches-source\" | type")
[[ "$type" == "array" ]]
'
# Test 2: Multi-source array extraction
run_test "Extract multi-source array" '
toml_prep config-multi-source-test.toml
main_table=$(toml_get_table_main)
declare -a sources
toml_get_array_or_string sources "$main_table" "patches-source" ""
[[ ${#sources[@]} -eq 2 ]] && \
[[ "${sources[0]}" == "anddea/revanced-patches" ]] && \
[[ "${sources[1]}" == "jkennethcarino/privacy-revanced-patches" ]]
'
# Test 3: Single-source backwards compatibility
run_test "Parse single-source config (backwards compat)" '
toml_prep config-single-source-test.toml
main_table=$(toml_get_table_main)
type=$(echo "$main_table" | jq -r ".\"patches-source\" | type")
[[ "$type" == "string" ]]
'
# Test 4: Single-source to array normalization
run_test "Normalize single-source to array" '
toml_prep config-single-source-test.toml
main_table=$(toml_get_table_main)
declare -a sources
toml_get_array_or_string sources "$main_table" "patches-source" ""
[[ ${#sources[@]} -eq 1 ]] && \
[[ "${sources[0]}" == "anddea/revanced-patches" ]]
'
# Test 5: Default value handling
run_test "Handle missing key with default" '
toml_prep config-single-source-test.toml
main_table=$(toml_get_table_main)
declare -a sources
toml_get_array_or_string sources "$main_table" "nonexistent-key" "default/value"
[[ ${#sources[@]} -eq 1 ]] && \
[[ "${sources[0]}" == "default/value" ]]
'
# Test 6: Per-app table parsing
run_test "Parse per-app table" '
toml_prep config-multi-source-test.toml
app_table=$(toml_get_table "YouTube-Extended")
enabled=$(toml_get "$app_table" "enabled")
version=$(toml_get "$app_table" "version")
[[ "$enabled" == "true" ]] && \
[[ "$version" == "auto" ]]
'
# Test 7: Function exists check
run_test "Verify new functions exist" '
type -t toml_get_array_or_string >/dev/null && \
type -t get_rv_prebuilts_multi >/dev/null
'
# Summary
echo "==================================="
echo "Test Results Summary"
echo "==================================="
echo "Total tests: $test_count"
echo "Passed: $pass_count"
echo "Failed: $fail_count"
echo
if [[ $fail_count -eq 0 ]]; then
  echo "✓ All tests passed!"
  exit 0
else
  echo "✗ Some tests failed"
  exit 1
fi
