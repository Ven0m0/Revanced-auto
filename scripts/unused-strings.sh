#!/bin/bash -e
# SPDX-FileCopyrightText: Copyright 2025 Eden Emulator Project
# SPDX-License-Identifier: GPL-3.0-or-later

# Remove unused string resources from Android XML files
echo "[INFO] Scanning for unused string resources..."

# For decompiled APKs, the structure is different - resources are in res/ directory
if [ ! -d "res" ]; then
  echo "[WARNING] res directory not found, skipping unused strings cleanup"
  exit 0
fi

# Check if strings.xml exists
STRINGS_FILE=$(find res/values* -name 'strings.xml' -type f | head -n 1)
if [ "$STRINGS_FILE" = "" ]; then
  echo "[WARNING] strings.xml not found, skipping unused strings cleanup"
  exit 0
fi

TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
USED="$TMP_DIR"/used
UNUSED="$TMP_DIR"/unused
FILTERED="$TMP_DIR"/filtered
ALL_STRINGS="$TMP_DIR"/all

# First we find what files to search and what strings are defined
echo "[INFO] Finding XML and smali files..."
find . -type f \( -iname '*.xml' -a -not -iname '*strings.xml' \) -o -iname '*.smali' -print0 | grep -z -v drawable > "$TMP_DIR"/files

# Get all defined strings
echo "[INFO] Extracting defined strings..."
find res/values* -name 'strings.xml' -type f -print0 | xargs -0 grep -h '<string name' | sed -n 's/.*<string name="\([^"]*\)".*/\1/p' | sort -u > "$ALL_STRINGS"

TOTAL_STRINGS=$(wc -l < "$ALL_STRINGS")
echo "[INFO] Found $TOTAL_STRINGS total string resources"

# Get a list of all strings that are actually used
set +e
while IFS= read -r -d '' file; do
  # For smali files, look for string references
  grep -o 'string/[a-zA-Z0-9_]*' "$file" 2> /dev/null >> "$USED"
  # For XML files, look for @string/ references
  grep -o '@string/[a-zA-Z0-9_]*' "$file" 2> /dev/null >> "$USED"
done < "$TMP_DIR"/files
set -e

# Filter out "@string/" and "string/" prefixes to get the raw names
sed 's/string\///' "$USED" | sed 's/@string\///' | sort -u > "$FILTERED"

USED_COUNT=$(wc -l < "$FILTERED")
echo "[INFO] Found $USED_COUNT used string resources"

# Get unused strings (strings in strings.xml but not in used list)
comm -13 "$FILTERED" "$ALL_STRINGS" > "$UNUSED"

UNUSED_COUNT=$(wc -l < "$UNUSED")
if [ "$UNUSED_COUNT" -eq 0 ]; then
  echo "[INFO] No unused strings found"
  rm -rf "$TMP_DIR"
  exit 0
fi

echo "[INFO] Found $UNUSED_COUNT potentially unused strings, removing..."

# Remove unused strings from all strings.xml files
sed_script="${TMP_DIR}/deletions.sed"
while IFS= read -r string; do
  # Escape special characters in string name for sed
  escaped_string=$(printf '%s\n' "$string" | sed 's/[[\.*^$/]/\\&/g')
  echo "/<string name=\"${escaped_string}\"/d" >> "$sed_script"
done < "$UNUSED"

find res -iname '*strings.xml' -type f -print0 | while IFS= read -r -d '' file; do
  sed -f "$sed_script" "$file" > "${file}.new" && mv "${file}.new" "$file"
done

echo "[INFO] Removed $UNUSED_COUNT unused string resources"
rm -rf "$TMP_DIR"
