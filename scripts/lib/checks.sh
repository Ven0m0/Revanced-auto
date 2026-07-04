#!/usr/bin/env bash
set -euo pipefail
# Environment Check Functions
# Centralizes logic for checking tools, versions, and assets
# Check for required system tools
# Returns 1 if any tool is missing
check_system_tools() {
  local missing=()
  for tool in jq java zip uv curl sha256sum; do
    if ! command -v "$tool" &> /dev/null; then
      missing+=("$tool")
    fi
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    epr "Missing required system tools: ${missing[*]}"
    return 1
  fi
  log_debug "All system tools found"
  return 0
}
# Check Java version >= 21
check_java_version() {
  local java_version
  java_version=$(java -version 2>&1 | head -n 1)
  local major_version="0"
  if [[ $java_version =~ ([0-9]+)\.([0-9]+) ]]; then
    if [[ ${BASH_REMATCH[1]} == "1" ]]; then
      major_version="${BASH_REMATCH[2]}"
    else
      major_version="${BASH_REMATCH[1]}"
    fi
  elif [[ $java_version =~ ([0-9]+) ]]; then
    major_version="${BASH_REMATCH[1]}"
  fi
  if [[ $major_version -lt 21 ]]; then
    epr "Java version must be 21 or higher (found: Java ${major_version})"
    return 1
  fi
  log_debug "Java version ok: ${major_version}"
  return 0
}
# Check project assets
check_assets() {
  if [[ ! -f "assets/ks.keystore" ]]; then
    # Only warn as it can be created
    log_warn "assets/ks.keystore not found (will be created during build)"
  fi
  if [[ ! -f "assets/sig.txt" ]]; then
    log_warn "assets/sig.txt not found (signature verification disabled)"
  fi
  return 0
}
# Check optional tools
check_optional_tools() {
  local warnings=()
  if ! command -v zipalign &> /dev/null; then
    warnings+=("zipalign (for APK optimization)")
  fi
  if ! command -v optipng &> /dev/null; then
    warnings+=("optipng (for asset optimization)")
  fi
  if [[ ${#warnings[@]} -gt 0 ]]; then
    for w in "${warnings[@]}"; do
      log_warn "Missing optional tool: $w"
    done
  else
    log_debug "All optional tools found"
  fi
}
# Check uv and Python version (>= 3.11 for tomllib)
check_python_version() {
  if ! command -v uv &> /dev/null; then
    epr "uv not found (see https://astral.sh/uv for installation instructions)"
    return 1
  fi
  if uv run python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2> /dev/null; then
    log_debug "uv python >= 3.11"
    return 0
  else
    epr "uv python < 3.11 (requires >= 3.11)"
    return 1
  fi
}

BINARIES_SOURCE_REF="${BINARIES_SOURCE_REF:-c62a54d5a04617400cd19ef33cba2dfdb5b0947f}"
readonly BINARIES_SOURCE_REF
# SHA-256 values for the pinned upstream binaries at BINARIES_SOURCE_REF.
readonly APKSIGNER_SHA256="eefdd6aed9db9fb849e4c98a50d8741e19d1b674ba6547220bcb9c3ed152123a"
readonly DEXLIB2_SHA256="bbd18fb81e521c362fb37fa89d93974debb2107a9d2e1057cdd8329b92479466"
readonly PACCER_SHA256="cbc9d084b2117a203a1818fba3c73b06cd8817b147a185c00975980e86d5dead"

_sha256_file() {
  sha256sum "$1" | awk '{print $1}'
}

_ensure_binary() {
  local name=$1 expected_sha=$2
  local file_path="${BIN_DIR}/${name}"
  local base_url="https://raw.githubusercontent.com/j-hc/revanced-magisk-module/${BINARIES_SOURCE_REF}/bin"
  local actual_sha=""

  mkdir -p "$BIN_DIR"

  if [[ -f "$file_path" ]]; then
    actual_sha=$(_sha256_file "$file_path") || {
      epr "Failed to verify checksum for $file_path"
      return 1
    }
    if [[ "$actual_sha" == "$expected_sha" ]]; then
      log_debug "Binary ready: $file_path"
      return 0
    fi
    log_warn "Checksum mismatch for $file_path; re-downloading"
    rm -f "$file_path"
  fi

  req "${base_url}/${name}" "$file_path" || {
    epr "Failed to download $file_path from ${base_url}/${name}"
    return 1
  }

  actual_sha=$(_sha256_file "$file_path") || {
    epr "Failed to verify checksum for $file_path"
    return 1
  }
  if [[ "$actual_sha" != "$expected_sha" ]]; then
    rm -f "$file_path"
    epr "Checksum mismatch for $file_path"
    return 1
  fi

  log_info "Downloaded ${file_path}"
  return 0
}

# Check binary files
check_binaries() {
  _ensure_binary apksigner.jar "$APKSIGNER_SHA256" || return 1
  _ensure_binary dexlib2.jar "$DEXLIB2_SHA256" || return 1
  _ensure_binary paccer.jar "$PACCER_SHA256" || return 1
  return 0
}
# Check config file syntax
check_config_file() {
  if [[ ! -f "config.toml" ]]; then
    log_warn "config.toml not found"
    return 0
  fi
  if command -v uv &> /dev/null; then
    if uv run scripts/toml_get.py --file config.toml > /dev/null 2>&1; then
      log_debug "config.toml syntax valid"
    else
      epr "config.toml syntax invalid"
      return 1
    fi
  fi
  return 0
}
# Main prerequisite check (used by build.sh)
check_prerequisites() {
  log_info "Checking prerequisites..."
  if ! check_system_tools; then
    exit 1
  fi
  if ! check_java_version; then
    exit 1
  fi
  if ! check_binaries; then
    exit 1
  fi
  check_assets
  log_info "Prerequisites check passed"
}
# Full environment check (used by check-env.sh)
check_full_environment() {
  log_info "Performing full environment check..."
  local failed=0
  check_system_tools || failed=1
  check_python_version || failed=1
  check_java_version || failed=1
  check_optional_tools
  check_binaries || failed=1
  check_assets
  check_config_file || failed=1
  if [[ $failed -eq 0 ]]; then
    pr "Environment check passed"
    return 0
  else
    epr "Environment check failed"
    return 1
  fi
}
