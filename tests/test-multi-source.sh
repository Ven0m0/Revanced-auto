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
  if "$test_cmd"; then
    echo "  ✓ PASS"
    pass_count=$((pass_count + 1))
  else
    echo "  ✗ FAIL"
    fail_count=$((fail_count + 1))
  fi
  echo
}

# Test 1: Multi-source config parsing
test_1() {
  toml_prep config-multi-source-test.toml
  main_table=$(toml_get_table_main)
  type=$(echo "$main_table" | jq -r ".\"patches-source\" | type")
  [[ "$type" == "array" ]]
}
run_test "Parse multi-source config" test_1

# Test 2: Multi-source array extraction
test_2() {
  toml_prep config-multi-source-test.toml
  main_table=$(toml_get_table_main)
  declare -a sources
  toml_get_array_or_string sources "$main_table" "patches-source" ""
  [[ ${#sources[@]} -eq 2 ]] && \
  [[ "${sources[0]}" == "anddea/revanced-patches" ]] && \
  [[ "${sources[1]}" == "jkennethcarino/privacy-revanced-patches" ]]
}
run_test "Extract multi-source array" test_2

# Test 3: Single-source backwards compatibility
test_3() {
  toml_prep config-single-source-test.toml
  main_table=$(toml_get_table_main)
  type=$(echo "$main_table" | jq -r ".\"patches-source\" | type")
  [[ "$type" == "string" ]]
}
run_test "Parse single-source config (backwards compat)" test_3

# Test 4: Single-source to array normalization
test_4() {
  toml_prep config-single-source-test.toml
  main_table=$(toml_get_table_main)
  declare -a sources
  toml_get_array_or_string sources "$main_table" "patches-source" ""
  [[ ${#sources[@]} -eq 1 ]] && \
  [[ "${sources[0]}" == "anddea/revanced-patches" ]]
}
run_test "Normalize single-source to array" test_4

# Test 5: Default value handling
test_5() {
  toml_prep config-single-source-test.toml
  main_table=$(toml_get_table_main)
  declare -a sources
  toml_get_array_or_string sources "$main_table" "nonexistent-key" "default/value"
  [[ ${#sources[@]} -eq 1 ]] && \
  [[ "${sources[0]}" == "default/value" ]]
}
run_test "Handle missing key with default" test_5

# Test 6: Per-app table parsing
test_6() {
  toml_prep config-multi-source-test.toml
  app_table=$(toml_get_table "YouTube-Extended")
  enabled=$(toml_get "$app_table" "enabled")
  version=$(toml_get "$app_table" "version")
  [[ "$enabled" == "true" ]] && \
  [[ "$version" == "auto" ]]
}
run_test "Parse per-app table" test_6

# Test 7: Function exists check
test_7() {
  type -t toml_get_array_or_string >/dev/null && \
  type -t get_rv_prebuilts_multi >/dev/null
}
run_test "Verify new functions exist" test_7

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
