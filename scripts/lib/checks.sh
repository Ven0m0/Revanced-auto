#!/usr/bin/env bash
set -euo pipefail
# Environment Check Functions
# Centralizes logic for checking tools, versions, and assets
# Check for required system tools
# Returns 1 if any tool is missing
check_system_tools() {
  local missing=()
  for tool in jq java zip uv; do
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
  if ! command -v curl &> /dev/null && ! command -v wget &> /dev/null; then
    warnings+=("curl or wget (for downloads)")
  fi
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
    epr "uv not found (install: curl -LsSf https://astral.sh/uv/install.sh | sh)"
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
# Check binary files
check_binaries() {
  local missing=()
  for bin in apksigner.jar dexlib2.jar paccer.jar; do
    if [[ ! -f "bin/$bin" ]]; then
      missing+=("bin/$bin")
    fi
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    epr "Missing binaries: ${missing[*]}"
    return 1
  fi
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
