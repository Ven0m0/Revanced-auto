#!/usr/bin/env bash
set -euo pipefail
# Network request functions with retry logic and exponential backoff
# Configuration
MAX_RETRIES=${MAX_RETRIES:-4}
INITIAL_RETRY_DELAY=${INITIAL_RETRY_DELAY:-2}
CONNECTION_TIMEOUT=${CONNECTION_TIMEOUT:-10}
# Internal request function with retry logic
# Args:
#   $1: URL
#   $2: Output file path or "-" for stdout
#   $@: Additional curl arguments
# Returns:
#   0 on success, 1 on failure
_req() {
  local ip="$1" op="$2"
  shift 2
  local retry_count=0
  local delay=$INITIAL_RETRY_DELAY
  local success=false
  # If output file exists, skip download
  if [[ "$op" != "-" && -f "$op" ]]; then
    log_debug "File already exists, skipping download: $op"
    return 0
  fi
  # Handle temporary file for downloads with proper locking
  local dlp="" lock_fd
  if [[ "$op" != "-" ]]; then
    # Deterministic hash-based temp path (not mktemp) so concurrent downloads
    # of the same destination share one temp file and correctly serialize on the lock
    mkdir -p "$TEMP_DIR"
    chmod 700 "$TEMP_DIR"
    dlp="${TEMP_DIR}/tmp.$(printf '%s' "$op" | sha256sum | cut -d' ' -f1)"
    local lock_file="${dlp}.lock"
    # Try to acquire exclusive lock (create lock file atomically)
    exec {lock_fd}>"$lock_file" || {
      epr "Failed to create lock file: $lock_file"
      return 1
    }
    if ! flock -n "$lock_fd"; then
      # Another process is downloading - wait for lock
      log_info "Waiting for concurrent download: $dlp"
      flock "$lock_fd" # Block until lock is available

      # Check if the other process actually succeeded
      if [[ -f "$op" ]]; then
        exec {lock_fd}>&- # Close lock file descriptor
        rm -f "$lock_file"
        log_debug "File was downloaded by other process: $op"
        return 0
      fi

      # If file doesn't exist, the other process failed
      # We now hold the lock and should proceed with download
      log_warn "Concurrent download failed, taking over: $dlp"
    fi
    # Lock acquired - we will download
  fi
  # Retry loop with exponential backoff
  while [[ "$retry_count" -le "$MAX_RETRIES" ]]; do
    if [[ "$op" = "-" ]]; then
      # Output to stdout
      if curl -L -c "$TEMP_DIR/cookie.txt" -b "$TEMP_DIR/cookie.txt" \
        --connect-timeout "$CONNECTION_TIMEOUT" --max-time 300 \
        --fail -s -S "$@" "$ip"; then
        success=true
        break
      fi
    else
      # Output to file
      if curl -L -c "$TEMP_DIR/cookie.txt" -b "$TEMP_DIR/cookie.txt" \
        --connect-timeout "$CONNECTION_TIMEOUT" --max-time 300 \
        --fail -s -S "$@" "$ip" -o "$dlp"; then
        mv -f "$dlp" "$op"
        success=true
        break
      fi
    fi
    retry_count=$((retry_count + 1))
    if [[ "$retry_count" -le "$MAX_RETRIES" ]]; then
      log_warn "Request failed (attempt $retry_count/$MAX_RETRIES): $ip - Retrying in ${delay}s..."
      sleep "$delay"
      delay=$((delay * 2))
    fi
  done
  # Clean up temporary file and lock on failure
  if [[ "$success" = false ]]; then
    rm -f "$dlp" 2>/dev/null
    if [[ -n "${lock_fd:-}" ]]; then
      exec {lock_fd}>&- # Close lock file descriptor
      rm -f "${lock_file:-}"
    fi
    epr "Request failed after $MAX_RETRIES retries: $ip"
    return 1
  fi
  # Release lock on success
  if [[ -n "${lock_fd:-}" ]]; then
    exec {lock_fd}>&- # Close lock file descriptor
    rm -f "${lock_file:-}"
  fi
  log_debug "Request successful: $ip"
  return 0
}
# Regular HTTP request
# Args:
#   $1: URL
#   $2: Output file path or "-" for stdout
req() {
  _req "$1" "$2" -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:142.0) Gecko/20100101 Firefox/142.0"
}
# GitHub API request
# Args:
#   $1: URL
#   $2: Output file path or "-" for stdout
gh_req() {
  _req "$1" "$2" -H "$GH_HEADER"
}
# GitHub asset download
# Args:
#   $1: Output file path
#   $2: Asset URL
#   $3: SHA256 hash (optional)
gh_dl() {
  local op="$1" url="$2" expected_sha="${3:-}"
  if [[ -f "$op" && -n "$expected_sha" ]]; then
    local actual_sha
    actual_sha=$(sha256sum "$op" | cut -d' ' -f1)
    if [[ "$actual_sha" != "$expected_sha" ]]; then
      log_warn "Checksum mismatch for $op; re-downloading"
      rm -f "$op"
    fi
  fi

  if [[ ! -f "$op" ]]; then
    pr "Getting '$op' from '$url'"
    if ! _req "$url" "$op" -H "$GH_HEADER" -H "Accept: application/octet-stream"; then
      return 1
    fi
    if [[ -n "$expected_sha" ]]; then
      local actual_sha
      actual_sha=$(sha256sum "$op" | cut -d' ' -f1)
      if [[ "$actual_sha" != "$expected_sha" ]]; then
        rm -f "$op"
        epr "Checksum mismatch for $op"
        return 1
      fi
    fi
  else
    log_debug "Asset already downloaded and verified: $op"
  fi
}
