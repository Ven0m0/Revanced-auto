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
    dlp="$(dirname "$op")/tmp.$(basename "$op")"
    local lock_file="${dlp}.lock"
    # Try to acquire exclusive lock (create lock file atomically)
    exec {lock_fd}> "$lock_file" || {
      epr "Failed to create lock file: $lock_file"
      return 1
    }
    if ! flock -n "$lock_fd"; then
      # Another process is downloading - wait for lock
      log_info "Waiting for concurrent download: $dlp"
      flock "$lock_fd"  # Block until lock is available
      exec {lock_fd}>&- # Close lock file descriptor
      rm -f "$lock_file"
      # File was downloaded by other process
      return 0
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
    rm -f "$dlp" 2> /dev/null
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
gh_dl() {
  if [[ ! -f "$1" ]]; then
    pr "Getting '$1' from '$2'"
    _req "$2" "$1" -H "$GH_HEADER" -H "Accept: application/octet-stream"
  else
    log_debug "Asset already downloaded: $1"
  fi
}
