#!/usr/bin/env bash
# Environment Check Script
# Verifies that all required tools and binaries are available

set -euo pipefail

# Color output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[0;33m'
readonly BLUE='\033[0;36m'
readonly NC='\033[0m' # No Color

# Counters
PASS=0
FAIL=0
WARN=0

# Helper functions
pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    PASS=$((PASS + 1))
}

fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    FAIL=$((FAIL + 1))
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    WARN=$((WARN + 1))
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

echo "======================================================================="
echo "ReVanced Builder - Environment Check"
echo "======================================================================="
echo ""

# Check required commands
echo "Checking required commands..."
command -v bash &>/dev/null && pass "bash ($(bash --version | head -1))" || fail "bash not found"
command -v jq &>/dev/null && pass "jq ($(jq --version))" || fail "jq not found"
command -v java &>/dev/null && pass "java ($(java -version 2>&1 | head -1))" || fail "java not found"
command -v zip &>/dev/null && pass "zip" || fail "zip not found"
echo ""

# Check optional commands
echo "Checking optional commands..."
if command -v curl &>/dev/null; then
    pass "curl ($(curl --version | head -1))"
elif command -v wget &>/dev/null; then
    pass "wget"
else
    warn "Neither curl nor wget found (network requests may fail)"
fi

if command -v zipalign &>/dev/null; then
    pass "zipalign (APK optimization)"
else
    warn "zipalign not found (APK optimization will be skipped)"
fi

if command -v optipng &>/dev/null; then
    pass "optipng (asset optimization)"
else
    warn "optipng not found (asset optimization not available)"
fi
echo ""

# Check Java version
echo "Checking Java version..."
java_version=$(java -version 2>&1 | head -1)
if [[ $java_version =~ \"([0-9]+)\.([0-9]+) ]]; then
    major="${BASH_REMATCH[1]}"
    if [ "${BASH_REMATCH[1]}" = "1" ]; then
        major="${BASH_REMATCH[2]}"
    fi

    if [ "$major" -ge 21 ]; then
        pass "Java version $major (>= 21 required)"
    else
        fail "Java version $major (< 21, required)"
    fi
else
    fail "Could not parse Java version: $java_version"
fi
echo ""

# Check binary tools
echo "Checking binary tools..."

# Detect architecture
arch=$(uname -m)
if [ "$arch" = aarch64 ]; then
    arch=arm64
elif [ "${arch:0:5}" = "armv7" ]; then
    arch=arm
fi
info "Detected architecture: $arch"

# Check apksigner
if [ -f "bin/apksigner.jar" ]; then
    pass "bin/apksigner.jar found"
else
    fail "bin/apksigner.jar not found"
fi

# Check dexlib2
if [ -f "bin/dexlib2.jar" ]; then
    pass "bin/dexlib2.jar found"
else
    fail "bin/dexlib2.jar not found"
fi

# Check paccer
if [ -f "bin/paccer.jar" ]; then
    pass "bin/paccer.jar found"
else
    fail "bin/paccer.jar not found"
fi

# Check aapt2
if [ -x "bin/aapt2/aapt2-${arch}" ]; then
    pass "bin/aapt2/aapt2-${arch} found and executable"
else
    # x86_64 is mapped to arm64 in helpers.sh
    if [ "$(uname -m)" = "x86_64" ] && [ -x "bin/aapt2/aapt2-arm64" ]; then
        pass "bin/aapt2/aapt2-arm64 found (x86_64 will use arm64 via emulation)"
    else
        fail "bin/aapt2/aapt2-${arch} not found or not executable"
        if [ -d "bin/aapt2" ]; then
            info "Available aapt2 binaries: $(ls bin/aapt2/ 2>/dev/null || echo 'none')"
        fi
    fi
fi

# Check htmlq
if [ -x "bin/htmlq/htmlq-${arch}" ]; then
    pass "bin/htmlq/htmlq-${arch} found and executable"
else
    # x86_64 is mapped to arm64 in helpers.sh
    if [ "$(uname -m)" = "x86_64" ] && [ -x "bin/htmlq/htmlq-arm64" ]; then
        pass "bin/htmlq/htmlq-arm64 found (x86_64 will use arm64 via emulation)"
    else
        fail "bin/htmlq/htmlq-${arch} not found or not executable"
        if [ -d "bin/htmlq" ]; then
            info "Available htmlq binaries: $(ls bin/htmlq/ 2>/dev/null || echo 'none')"
        fi
    fi
fi

# Check toml parser
if [ -x "bin/toml/tq-${arch}" ]; then
    pass "bin/toml/tq-${arch} found and executable"
else
    fail "bin/toml/tq-${arch} not found or not executable"
    if [ -d "bin/toml" ]; then
        info "Available toml binaries: $(ls bin/toml/ 2>/dev/null || echo 'none')"
    fi
fi
echo ""

# Check library modules
echo "Checking library modules..."
for lib in lib/logger.sh lib/helpers.sh lib/config.sh lib/network.sh lib/prebuilts.sh lib/download.sh lib/patching.sh; do
    if [ -f "$lib" ]; then
        if bash -n "$lib" 2>/dev/null; then
            pass "$lib - syntax OK"
        else
            fail "$lib - syntax ERROR"
        fi
    else
        fail "$lib not found"
    fi
done
echo ""

# Check configuration file
echo "Checking configuration..."
if [ -f "config.toml" ]; then
    pass "config.toml found"
    # Check if we can parse it (needs toml binary)
    if [ -x "bin/toml/tq-${arch}" ]; then
        if bin/toml/tq-"$arch" --output json --file config.toml . &>/dev/null; then
            pass "config.toml - valid TOML"
        else
            fail "config.toml - invalid TOML syntax"
        fi
    fi
else
    warn "config.toml not found (will use default configuration)"
fi
echo ""

# Check keystore
echo "Checking signing assets..."
if [ -f "ks.keystore" ]; then
    pass "ks.keystore found"
else
    warn "ks.keystore not found (will create during build)"
fi

if [ -f "sig.txt" ]; then
    pass "sig.txt found"
else
    warn "sig.txt not found (signature verification disabled)"
fi
echo ""

# Check directories
echo "Checking directories..."
[ -d "bin" ] && pass "bin/ directory exists" || fail "bin/ directory missing"
[ -d "lib" ] && pass "lib/ directory exists" || fail "lib/ directory missing"
[ -d "scripts" ] && pass "scripts/ directory exists" || fail "scripts/ directory missing"
echo ""

# Summary
echo "======================================================================="
echo "Check Summary"
echo "======================================================================="
echo -e "${GREEN}Passed:${NC} $PASS"
echo -e "${YELLOW}Warnings:${NC} $WARN"
echo -e "${RED}Failed:${NC} $FAIL"
echo ""

if [ "$FAIL" -eq 0 ]; then
    echo -e "${GREEN}All required checks passed!${NC}"
    echo "You can run ./build.sh to start building."
    exit 0
else
    echo -e "${RED}Some checks failed. Please fix the issues above.${NC}"
    exit 1
fi
