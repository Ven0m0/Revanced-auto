#!/usr/bin/env bash
set -euo pipefail
# Test script for scripts/apkmirror_search.py
SCRIPT="scripts/apkmirror_search.py"
FIXTURE="tests/fixtures/apkmirror_mock.html"
echo "=== Testing APKMirror Search Parser ==="
if [[ ! -f "$FIXTURE" ]]; then
  echo "Error: Fixture not found: $FIXTURE"
  exit 1
fi
fail_count=0
run_test() {
  local name=$1
  local bundle=$2
  local dpi=$3
  local arch=$4
  local expected=$5
  echo -n "Test: $name ... "
  local output
  output=$(uv run "$SCRIPT" --apk-bundle "$bundle" --dpi "$dpi" --arch "$arch" < "$FIXTURE" || true)
  if [[ "$expected" == "NONE" ]]; then
    if [[ -z "$output" ]]; then
      echo "PASS"
    else
      echo "FAIL (Expected no output, got: $output)"
      fail_count=$((fail_count + 1))
    fi
  else
    if [[ "$output" == *"$expected"* ]]; then
      echo "PASS"
    else
      echo "FAIL (Expected '$expected', got: '$output')"
      fail_count=$((fail_count + 1))
    fi
  fi
}
# Test 1: Exact Match
run_test "Exact Match (APK, nodpi, arm64-v8a)" "APK" "nodpi" "arm64-v8a" "https://www.apkmirror.com/apk/google-inc/youtube/youtube-19-09-37-release/youtube-19-09-37-android-apk-download/"
# Test 2: Mismatch Bundle
run_test "Mismatch Bundle (BUNDLE vs APK)" "BUNDLE" "nodpi" "arm64-v8a" "https://www.apkmirror.com/fail-bundle"
# Test 3: Mismatch DPI
run_test "Mismatch DPI" "APK" "480dpi" "arm64-v8a" "https://www.apkmirror.com/fail-dpi"
# Test 4: Mismatch Arch
run_test "Mismatch Arch (x86 request)" "APK" "nodpi" "x86" "https://www.apkmirror.com/fail-arch"
# Test 5: Universal Fallback (Request arm64-v8a, match universal)
# Note: The fixture has two matches for arm64-v8a (Row 1 and Row 5).
# Row 1 is exact match. The script returns the FIRST match.
# To test fallback, we need to request something that ONLY matches universal in our fixture,
# or ensure the universal row comes first.
# In current fixture, Row 1 (arm64-v8a) comes before Row 5 (universal).
# So querying arm64-v8a should return Row 1.
run_test "Arch Fallback Preference (arm64-v8a prefers explicit)" "APK" "nodpi" "arm64-v8a" "https://www.apkmirror.com/apk/google-inc/youtube/youtube-19-09-37-release/youtube-19-09-37-android-apk-download/"
# To test universal fallback properly, let's pretend to search for an arch not in Row 1 but compatible with Row 5.
# But Row 5 is 'universal'. 'universal' is compatible with everything.
# If I search for 'armeabi-v7a', Row 1 (arm64-v8a) should NOT match. Row 5 (universal) SHOULD match.
run_test "Universal Fallback (armeabi-v7a matches universal)" "APK" "nodpi" "armeabi-v7a" "https://www.apkmirror.com/success-universal"
if [[ $fail_count -eq 0 ]]; then
  echo "All tests passed!"
  exit 0
else
  echo "$fail_count tests failed."
  exit 1
fi
