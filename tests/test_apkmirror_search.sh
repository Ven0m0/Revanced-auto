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
    output=$(python3 "$SCRIPT" --apk-bundle "$bundle" --dpi "$dpi" --arch "$arch" < "$FIXTURE" || true)

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

run_test_exit_code() {
    local name=$1
    local bundle=$2
    local dpi=$3
    local arch=$4
    local expected_code=$5
    local html_input="${6:-$FIXTURE}"

    echo -n "Test: $name ... "

    local actual_code=0
    if [[ "$html_input" == "EMPTY" ]]; then
        python3 "$SCRIPT" --apk-bundle "$bundle" --dpi "$dpi" --arch "$arch" < /dev/null > /dev/null 2>&1 || actual_code=$?
    else
        python3 "$SCRIPT" --apk-bundle "$bundle" --dpi "$dpi" --arch "$arch" < "$html_input" > /dev/null 2>&1 || actual_code=$?
    fi

    if [[ "$actual_code" -eq "$expected_code" ]]; then
        echo "PASS (exit code: $actual_code)"
    else
        echo "FAIL (Expected exit code $expected_code, got: $actual_code)"
        fail_count=$((fail_count + 1))
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

# Test 6: "all" architecture - should match universal
run_test "All Architecture (matches universal)" "APK" "nodpi" "all" "https://www.apkmirror.com/success-universal"

echo ""
echo "=== Exit Code Tests ==="

# Test exit code 0 (found)
run_test_exit_code "Exit Code 0 (match found)" "APK" "nodpi" "arm64-v8a" 0

# Test exit code 1 (table found but no match - no matching criteria)
run_test_exit_code "Exit Code 1 (no match - wrong DPI)" "APK" "xxxdpi" "arm64-v8a" 1

# Test exit code 2 (no table found - empty HTML)
run_test_exit_code "Exit Code 2 (empty HTML)" "APK" "nodpi" "arm64-v8a" 2 "EMPTY"

# Test with edge case fixture
echo ""
echo "=== Edge Case Tests ==="

# Create a temporary fixture for edge cases
EDGE_FIXTURE=$(mktemp)
trap 'rm -f "$EDGE_FIXTURE"' EXIT

# Test: Row with fewer than 6 text nodes (should be skipped)
cat > "$EDGE_FIXTURE" << 'EOF'
<html>
<body>
    <!-- Row with fewer than 6 text nodes - should be skipped -->
    <div class="table-row headerFont">
        <div class="table-cell">
            <a href="/incomplete">v1</a>
        </div>
        <div class="table-cell">
            <span>214MB</span>
            <span class="apkm-badge">APK</span>
        </div>
    </div>
    <!-- Valid row that should match -->
    <div class="table-row headerFont">
        <div class="table-cell">
            <a href="/valid">v2</a>
        </div>
        <div class="table-cell">
            <span>214MB</span>
            <span class="apkm-badge">APK</span>
        </div>
        <div class="table-cell">
            arm64-v8a
        </div>
        <div class="table-cell">
            Android 8.0+
        </div>
        <div class="table-cell">
            nodpi
        </div>
    </div>
</body>
</html>
EOF

echo -n "Test: Skip rows with fewer than 6 text nodes ... "
output=$(python3 "$SCRIPT" --apk-bundle "APK" --dpi "nodpi" --arch "arm64-v8a" < "$EDGE_FIXTURE" || true)
if [[ "$output" == *"/valid"* ]]; then
    echo "PASS"
else
    echo "FAIL (Expected '/valid', got: '$output')"
    fail_count=$((fail_count + 1))
fi

# Test: Row with missing href (should be skipped)
cat > "$EDGE_FIXTURE" << 'EOF'
<html>
<body>
    <!-- Row with missing href - should be skipped -->
    <div class="table-row headerFont">
        <div class="table-cell">
            <a>v1</a>
        </div>
        <div class="table-cell">
            <span>214MB</span>
            <span class="apkm-badge">APK</span>
        </div>
        <div class="table-cell">
            arm64-v8a
        </div>
        <div class="table-cell">
            Android 8.0+
        </div>
        <div class="table-cell">
            nodpi
        </div>
    </div>
    <!-- Valid row that should match -->
    <div class="table-row headerFont">
        <div class="table-cell">
            <a href="/with-href">v2</a>
        </div>
        <div class="table-cell">
            <span>214MB</span>
            <span class="apkm-badge">APK</span>
        </div>
        <div class="table-cell">
            arm64-v8a
        </div>
        <div class="table-cell">
            Android 8.0+
        </div>
        <div class="table-cell">
            nodpi
        </div>
    </div>
</body>
</html>
EOF

echo -n "Test: Skip rows with missing href ... "
output=$(python3 "$SCRIPT" --apk-bundle "APK" --dpi "nodpi" --arch "arm64-v8a" < "$EDGE_FIXTURE" || true)
if [[ "$output" == *"/with-href"* ]]; then
    echo "PASS"
else
    echo "FAIL (Expected '/with-href', got: '$output')"
    fail_count=$((fail_count + 1))
fi

# Test: No table rows at all (exit code 2)
cat > "$EDGE_FIXTURE" << 'EOF'
<html>
<body>
    <div class="some-other-class">Not a table row</div>
</body>
</html>
EOF

run_test_exit_code "Exit Code 2 (no table rows)" "APK" "nodpi" "arm64-v8a" 2 "$EDGE_FIXTURE"

# Test: Row with absolute URL in href
cat > "$EDGE_FIXTURE" << 'EOF'
<html>
<body>
    <div class="table-row headerFont">
        <div class="table-cell">
            <a href="https://example.com/absolute">v1</a>
        </div>
        <div class="table-cell">
            <span>214MB</span>
            <span class="apkm-badge">APK</span>
        </div>
        <div class="table-cell">
            arm64-v8a
        </div>
        <div class="table-cell">
            Android 8.0+
        </div>
        <div class="table-cell">
            nodpi
        </div>
    </div>
</body>
</html>
EOF

echo -n "Test: Absolute URL in href ... "
output=$(python3 "$SCRIPT" --apk-bundle "APK" --dpi "nodpi" --arch "arm64-v8a" < "$EDGE_FIXTURE" || true)
if [[ "$output" == "https://example.com/absolute" ]]; then
    echo "PASS"
else
    echo "FAIL (Expected 'https://example.com/absolute', got: '$output')"
    fail_count=$((fail_count + 1))
fi

echo ""
if [[ $fail_count -eq 0 ]]; then
    echo "All tests passed!"
    exit 0
else
    echo "$fail_count tests failed."
    exit 1
fi
