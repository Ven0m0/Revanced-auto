#!/usr/bin/env bash
set -euo pipefail
# Logging and messaging functions
# Log levels
declare -r LOG_LEVEL_DEBUG=0
declare -r LOG_LEVEL_INFO=1
declare -r LOG_LEVEL_WARN=2
declare -r LOG_LEVEL_ERROR=3
# Current log level (default: INFO)
LOG_LEVEL=${LOG_LEVEL:-$LOG_LEVEL_INFO}
# Build log file (can be overridden per-app)
BUILD_LOG_FILE=${BUILD_LOG_FILE:-build.md}
# Print success message in green
pr() {
  echo -e "\033[0;32m[+] ${1}\033[0m"
}
# Print info message
log_info() {
  if [[ "$LOG_LEVEL" -le "$LOG_LEVEL_INFO" ]]; then
    echo -e "\033[0;36m[INFO] ${1}\033[0m" >&2
  fi
}
# Print debug message
log_debug() {
  if [[ "$LOG_LEVEL" -le "$LOG_LEVEL_DEBUG" ]]; then
    echo -e "\033[0;37m[DEBUG] ${1}\033[0m" >&2
  fi
}
# Print warning message in yellow
log_warn() {
  if [[ "$LOG_LEVEL" -le "$LOG_LEVEL_WARN" ]]; then
    echo -e "\033[0;33m[WARN] ${1}\033[0m" >&2
  fi
}
# Print error message in red
epr() {
  echo >&2 -e "\033[0;31m[-] ${1}\033[0m"
  if [[ "${GITHUB_REPOSITORY-}" ]]; then
    echo -e "::error::${1}\n"
  fi
}
# Print error and exit
abort() {
  epr "ABORT: ${1-}"
  exit 1
}
# Log to build log file
log() {
  local log_file="${BUILD_LOG_FILE:-build.md}"
  mkdir -p "$(dirname "$log_file")"
  echo -e "$1  " >> "$log_file"
}
