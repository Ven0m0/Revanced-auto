#!/usr/bin/env bash
# =============================================================================
# Optimize Assets Script
# =============================================================================
# Optimizes PNG assets using optipng to reduce file sizes
# =============================================================================
set -euo pipefail

# Find number of processors
NPROC=$(nproc 2>/dev/null || echo 1)

# Find and optimize all PNG files
PNG_COUNT=$(find . -type f -iname '*.png' -print0 | grep -zc .)

if [ "$PNG_COUNT" -eq 0 ]; then
  echo "[INFO] No PNG files found to optimize"
  exit 0
fi

echo "[INFO] Found $PNG_COUNT PNG files to optimize"
# Use optimization level 2 (default) instead of 7 for better performance/speed ratio
# optipng manual: "Levels 6 and 7 are very slow and provide little extra compression."
find . -type f -iname '*.png' -print0 | xargs -0 -P "$NPROC" optipng -o2

echo "[INFO] PNG optimization complete"
