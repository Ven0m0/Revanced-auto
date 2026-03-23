#!/usr/bin/env bash
# Bootstrap script for building ReVanced APKs on Android/Termux.
# Inspired by peternmuller/revanced-morphe-builder build-termux.sh.
#
# Usage (run directly from Termux):
#   bash <(curl -sSf https://raw.githubusercontent.com/Ven0m0/Revanced-auto/master/build-termux.sh)

set -e

REPO_URL="https://github.com/Ven0m0/Revanced-auto"
REPO_DIR="Revanced-auto"
OUTPUT_DIR="/sdcard/Download/revanced-auto"

pr() { echo -e "\033[0;32m[+] ${1}\033[0m"; }
epr() { echo >&2 -e "\033[0;31m[-] ${1}\033[0m"; }

# Request storage permission and wait until /sdcard is accessible
pr "Requesting storage permission..."
until termux-setup-storage >/dev/null 2>&1 && ls /sdcard >/dev/null 2>&1; do
  sleep 1
done

# Install/upgrade required packages once per calendar month
marker=~/.revanced_auto_"$(date '+%Y%m')"
if [[ ! -f "$marker" ]]; then
  pr "Installing/upgrading packages (this runs once per month)..."
  yes "" | pkg update -y
  pkg upgrade -y \
    -o Dpkg::Options::="--force-confdef" \
    -o Dpkg::Options::="--force-confold"
  pkg install -y git curl jq openjdk-21 zip python
  pip install uv --quiet
  : >"$marker"
fi

mkdir -p "$OUTPUT_DIR"

# Clone or update repository
if [[ -d "$REPO_DIR" ]] || [[ -f config.toml ]]; then
  [[ -d "$REPO_DIR" ]] && cd "$REPO_DIR"
  pr "Checking for updates..."
  git fetch
  if git status | grep -q 'is behind\|fatal'; then
    pr "Updating repository (config.toml will be preserved)..."
    cd ..
    cp -f "$REPO_DIR/config.toml" . 2>/dev/null || :
    rm -rf "$REPO_DIR"
    git clone "$REPO_URL" --depth 1 "$REPO_DIR"
    mv -f config.toml "$REPO_DIR/config.toml" 2>/dev/null || :
    cd "$REPO_DIR"
  fi
else
  pr "Cloning repository..."
  git clone "$REPO_URL" --depth 1 "$REPO_DIR"
  cd "$REPO_DIR"
  # Disable all apps by default so users opt-in explicitly on first run
  sed -i '/^enabled.*/d; /^\[.*\]/a enabled = false' config.toml
  git config --global --add safe.directory ~/Revanced-auto 2>/dev/null || :
fi

# Sync config from shared storage (if present)
if [[ -f "${OUTPUT_DIR}/config.toml" ]]; then
  pr "Syncing config from ${OUTPUT_DIR}/config.toml..."
  cp -f "${OUTPUT_DIR}/config.toml" config.toml
else
  cp -f config.toml "${OUTPUT_DIR}/config.toml"
  pr "Copied default config to ${OUTPUT_DIR}/config.toml — edit it to enable apps."
fi

# Install Python dependencies
pr "Installing Python dependencies..."
uv sync --locked --quiet

# Build
pr "Starting build..."
./build.sh config.toml

# Copy output APKs to shared storage
pr "Copying APKs to ${OUTPUT_DIR}..."
copied=0
for apk in build/*.apk; do
  [[ -f "$apk" ]] || continue
  cp "$apk" "$OUTPUT_DIR/"
  pr "  Saved: $(basename "$apk")"
  copied=$((copied + 1))
done

if ((copied == 0)); then
  epr "No APKs were built. Check logs above for errors."
  exit 1
fi

pr "Done! ${copied} APK(s) saved to ${OUTPUT_DIR}"
