#!/usr/bin/env bash
set -euo pipefail
# SPDX-FileCopyrightText: Copyright 2025 Eden Emulator Project
# SPDX-License-Identifier: GPL-3.0-or-later

# Optimize PNG assets using optipng
echo "[INFO] Optimizing PNG assets..."

# Check if optipng is installed
if ! command -v optipng &> /dev/null; then
  echo "[WARNING] optipng not found, skipping PNG optimization"
  exit 0
fi

# Detect number of processors
NPROC=$(nproc 2> /dev/null || getconf _NPROCESSORS_ONLN 2> /dev/null || sysctl -n hw.ncpu 2> /dev/null || echo 4)
echo "[INFO] Using $NPROC parallel processes for optimization"

# Find and optimize all PNG files
PNG_COUNT=$(find . -type f -iname '*.png' | wc -l)
if [ "$PNG_COUNT" -eq 0 ]; then
  echo "[INFO] No PNG files found to optimize"
  exit 0
fi

echo "[INFO] Found $PNG_COUNT PNG files to optimize"
find . -type f -iname '*.png' -print0 | xargs -0 -P "$NPROC" optipng -o7
echo "[INFO] PNG optimization complete"
