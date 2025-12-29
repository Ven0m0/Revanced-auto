#!/bin/bash -e
# AAPT2 Optimization Script
# Optimizes APK to keep only en, xxhdpi, arm64-v8a resources

INPUT_APK=$1
OUTPUT_APK=$2
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESOURCES_CFG="${SCRIPT_DIR}/aapt2-resources.cfg"

if [ -z "$INPUT_APK" ] || [ -z "$OUTPUT_APK" ]; then
	echo "Usage: $0 <input.apk> <output.apk>"
	exit 1
fi

if [ ! -f "$INPUT_APK" ]; then
	echo "Error: Input APK not found: $INPUT_APK"
	exit 1
fi

echo "[INFO] Starting aapt2 optimization..."
echo "[INFO] Input: $INPUT_APK"
echo "[INFO] Output: $OUTPUT_APK"
echo "[INFO] Keeping: en, xxhdpi, arm64-v8a only"

# Check if aapt2 is available
if ! command -v aapt2 &>/dev/null; then
	# Try to use AAPT2 from Android SDK if available
	if [ -n "${ANDROID_HOME:-}" ] && [ -f "${ANDROID_HOME}/build-tools/"*"/aapt2" ]; then
		AAPT2_BIN=$(find "${ANDROID_HOME}/build-tools/" -name "aapt2" | sort -V | tail -1)
		alias aapt2="$AAPT2_BIN"
	else
		echo "[WARNING] aapt2 not found, skipping optimization"
		cp "$INPUT_APK" "$OUTPUT_APK"
		exit 0
	fi
fi

# Create temporary config with proper format
TMP_CONFIG=$(mktemp)
cat >"$TMP_CONFIG" <<EOF
en
xxhdpi
arm64-v8a
EOF

# Run aapt2 optimize
# --enable-sparse-encoding: Reduces APK size by using sparse encoding
# --collapse-resource-names: Shortens resource names to reduce size
# --resources-config-path: Specifies which resources to keep
if aapt2 optimize \
	--enable-sparse-encoding \
	--collapse-resource-names \
	--resources-config-path "$TMP_CONFIG" \
	-o "$OUTPUT_APK" \
	"$INPUT_APK"; then
	echo "[INFO] aapt2 optimization completed successfully"

	# Show size reduction
	ORIGINAL_SIZE=$(stat -f%z "$INPUT_APK" 2>/dev/null || stat -c%s "$INPUT_APK")
	OPTIMIZED_SIZE=$(stat -f%z "$OUTPUT_APK" 2>/dev/null || stat -c%s "$OUTPUT_APK")
	REDUCTION=$((ORIGINAL_SIZE - OPTIMIZED_SIZE))
	PERCENT=$((REDUCTION * 100 / ORIGINAL_SIZE))

	echo "[INFO] Original size: $((ORIGINAL_SIZE / 1024 / 1024)) MB"
	echo "[INFO] Optimized size: $((OPTIMIZED_SIZE / 1024 / 1024)) MB"
	echo "[INFO] Size reduction: $((REDUCTION / 1024 / 1024)) MB ($PERCENT%)"
else
	echo "[WARNING] aapt2 optimization failed, using original APK"
	cp "$INPUT_APK" "$OUTPUT_APK"
fi

# Clean up
rm -f "$TMP_CONFIG"
