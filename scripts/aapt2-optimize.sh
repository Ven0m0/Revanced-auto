#!/usr/bin/env bash
# =============================================================================
# AAPT2 Optimization Script
# =============================================================================
# Optimizes APK resources to reduce file size
# Keeps only: English language, xxhdpi density, arm64-v8a architecture
# Typical size reduction: 10-30%
# =============================================================================

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
SCRIPT_DIR="$(cd "$SCRIPT_DIR" && pwd)"
readonly SCRIPT_DIR
readonly INPUT_APK="${1:-}"
readonly OUTPUT_APK="${2:-}"

# Color output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[0;33m'
readonly BLUE='\033[0;36m'
readonly NC='\033[0m' # No Color

# Helper functions
log_info() {
	echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
	echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
	echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
	echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Validate input arguments
if [[ -z "$INPUT_APK" ]] || [[ -z "$OUTPUT_APK" ]]; then
	log_error "Missing required arguments"
	echo "Usage: $0 <input.apk> <output.apk>"
	exit 1
fi

if [[ ! -f "$INPUT_APK" ]]; then
	log_error "Input APK not found: $INPUT_APK"
	exit 1
fi

log_info "Starting aapt2 optimization..."
log_info "Input:  $INPUT_APK"
log_info "Output: $OUTPUT_APK"
log_info "Optimization: Keep only en, xxhdpi, arm64-v8a"

# Detect and configure aapt2
find_aapt2() {
	# Check if aapt2 is in PATH
	if command -v aapt2 &>/dev/null; then
		echo "aapt2"
		return 0
	fi

	# Check if AAPT2 environment variable is set
	if [[ -n "${AAPT2:-}" ]] && [[ -x "$AAPT2" ]]; then
		echo "$AAPT2"
		return 0
	fi

	# Try to find aapt2 in Android SDK
	if [[ -n "${ANDROID_HOME:-}" ]]; then
		local aapt2_path
		aapt2_path=$(find "${ANDROID_HOME}/build-tools/" -name "aapt2" -type f 2>/dev/null | sort -V | tail -1)
		if [[ -n "$aapt2_path" ]] && [[ -x "$aapt2_path" ]]; then
			echo "$aapt2_path"
			return 0
		fi
	fi

	# Try to find in common locations
	for path in /usr/bin/aapt2 /usr/local/bin/aapt2; do
		if [[ -x "$path" ]]; then
			echo "$path"
			return 0
		fi
	done

	return 1
}

if ! AAPT2_CMD=$(find_aapt2); then
	log_warn "aapt2 not found in PATH or ANDROID_HOME"
	log_warn "Skipping optimization - copying original APK"
	cp "$INPUT_APK" "$OUTPUT_APK"
	exit 0
fi

log_info "Using aapt2: $AAPT2_CMD"

# Create temporary configuration file
TMP_CONFIG=$(mktemp -t aapt2-config.XXXXXX)
trap 'rm -f "$TMP_CONFIG"' EXIT

cat >"$TMP_CONFIG" <<'EOF'
en
xxhdpi
arm64-v8a
EOF

# Get file size in bytes (cross-platform)
get_file_size() {
	local file=$1
	if [[ -f "$file" ]]; then
		# Try stat with different formats for different platforms
		stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || wc -c <"$file"
	else
		echo "0"
	fi
}

# Format bytes to human-readable size
format_size() {
	local bytes=$1
	if ((bytes >= 1073741824)); then
		echo "$(((bytes + 536870912) / 1073741824)) GB"
	elif ((bytes >= 1048576)); then
		echo "$(((bytes + 524288) / 1048576)) MB"
	elif ((bytes >= 1024)); then
		echo "$(((bytes + 512) / 1024)) KB"
	else
		echo "$bytes bytes"
	fi
}

# Run aapt2 optimization
# --enable-sparse-encoding: Reduces APK size by using sparse encoding
# --collapse-resource-names: Shortens resource names to reduce size
# --resources-config-path: Specifies which resources to keep
log_info "Running aapt2 optimization..."

if "$AAPT2_CMD" optimize \
	--enable-sparse-encoding \
	--collapse-resource-names \
	--resources-config-path "$TMP_CONFIG" \
	-o "$OUTPUT_APK" \
	"$INPUT_APK" 2>&1; then

	log_success "Optimization completed successfully"

	# Calculate and display size reduction
	ORIGINAL_SIZE=$(get_file_size "$INPUT_APK")
	OPTIMIZED_SIZE=$(get_file_size "$OUTPUT_APK")

	if ((ORIGINAL_SIZE > 0)); then
		REDUCTION=$((ORIGINAL_SIZE - OPTIMIZED_SIZE))
		PERCENT=$((REDUCTION * 100 / ORIGINAL_SIZE))

		log_info "Original size:  $(format_size "$ORIGINAL_SIZE")"
		log_info "Optimized size: $(format_size "$OPTIMIZED_SIZE")"

		if ((REDUCTION > 0)); then
			log_success "Size reduction: $(format_size "$REDUCTION") (${PERCENT}%)"
		elif ((REDUCTION < 0)); then
			log_warn "Size increased by $(format_size $((OPTIMIZED_SIZE - ORIGINAL_SIZE)))"
		else
			log_info "No size change"
		fi
	fi
else
	log_warn "aapt2 optimization failed"
	log_warn "Falling back to original APK"
	cp "$INPUT_APK" "$OUTPUT_APK"
	exit 0
fi

exit 0
