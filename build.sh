#!/usr/bin/env bash
set -euo pipefail
# ReVanced Builder - Main build orchestration script
# Refactored for better maintainability and performance
# Set locale
export LC_ALL=C
# Trap interrupts and clean up
trap "rm -rf temp/*tmp.* temp/*/*tmp.* temp/*-temporary-files; exit 130" INT
# Handle cache management commands
if [[ ${1-} == "cache" ]]; then
  # Source utilities to get cache functions
  source utils.sh
  cache_command=${2:-stats}
  case "$cache_command" in
    stats)
      cache_stats
      ;;
    cleanup)
      cache_cleanup "${3:-false}"
      ;;
    clean)
      cache_clean_pattern "${3:-.*}"
      ;;
    init)
      cache_init
      echo "Cache initialized"
      ;;
    *)
      echo "Usage: $0 cache {stats|cleanup|clean|init} [options]"
      echo ""
      echo "Commands:"
      echo "  stats             - Show cache statistics"
      echo "  cleanup [force]   - Remove expired cache entries (force: also remove orphaned entries)"
      echo "  clean [pattern]   - Remove cache entries matching pattern (default: all)"
      echo "  init              - Initialize cache system"
      echo ""
      echo "Examples:"
      echo "  $0 cache stats"
      echo "  $0 cache cleanup"
      echo "  $0 cache cleanup force"
      echo "  $0 cache clean '.*\\.apk'"
      exit 1
      ;;
  esac
  exit 0
fi
# Handle clean command
if [[ ${1-} == "clean" ]]; then
  echo "Cleaning build artifacts..."
  rm -rf temp build logs build.md
  echo "Clean complete"
  exit 0
fi
# Source utilities
source utils.sh
# ==================== Prerequisites Check ====================
check_prerequisites
# Set prebuilt tools
set_prebuilts
# ==================== Configuration Loading ====================
load_configuration() {
  local config_file="${1:-config.toml}"
  log_info "Loading configuration from: ${config_file}"
  if ! toml_prep "$config_file"; then
    abort "Could not find config file '${config_file}'\n\tUsage: $0 <config.toml>"
  fi
  # Load main configuration
  main_config_t=$(toml_get_table_main)
  # Parse configuration values with defaults
  if ! PARALLEL_JOBS=$(toml_get "$main_config_t" parallel-jobs); then
    if [[ $OS == Android ]]; then
      PARALLEL_JOBS=1
      log_info "Android detected: setting parallel-jobs=1"
    else
      PARALLEL_JOBS=$(nproc)
      log_info "Auto-detected parallel-jobs=${PARALLEL_JOBS}"
    fi
  else
    log_info "Using configured parallel-jobs=${PARALLEL_JOBS}"
  fi
  export REMOVE_RV_INTEGRATIONS_CHECKS
  REMOVE_RV_INTEGRATIONS_CHECKS=$(toml_get "$main_config_t" remove-rv-integrations-checks) || REMOVE_RV_INTEGRATIONS_CHECKS="true"
  DEF_PATCHES_VER=$(toml_get "$main_config_t" patches-version) || DEF_PATCHES_VER="latest"
  DEF_CLI_VER=$(toml_get "$main_config_t" cli-version) || DEF_CLI_VER="latest"
  DEF_PATCHES_SRC=$(toml_get "$main_config_t" patches-source) || DEF_PATCHES_SRC="ReVanced/revanced-patches"
  DEF_CLI_SRC=$(toml_get "$main_config_t" cli-source) || DEF_CLI_SRC="j-hc/revanced-cli"
  DEF_RV_BRAND=$(toml_get "$main_config_t" rv-brand) || DEF_RV_BRAND="ReVanced"
  DEF_ARCH=$(toml_get "$main_config_t" arch) || DEF_ARCH="arm64-v8a"
  DEF_RIPLIB=$(toml_get "$main_config_t" riplib) || DEF_RIPLIB="true"
  ENABLE_AAPT2_OPTIMIZE=$(toml_get "$main_config_t" enable-aapt2-optimize) || ENABLE_AAPT2_OPTIMIZE=false
  export ENABLE_AAPT2_OPTIMIZE
  AAPT2_SOURCE=$(toml_get "$main_config_t" aapt2-source) || AAPT2_SOURCE="Graywizard888/Custom-Enhancify-aapt2-binary"
  export AAPT2_SOURCE
  USE_CUSTOM_AAPT2=$(toml_get "$main_config_t" use-custom-aapt2) || USE_CUSTOM_AAPT2=true
  export USE_CUSTOM_AAPT2
  log_info "Configuration loaded successfully"
  log_debug "Patches: ${DEF_PATCHES_SRC} @ ${DEF_PATCHES_VER}"
  log_debug "CLI: ${DEF_CLI_SRC} @ ${DEF_CLI_VER}"
  log_debug "Brand: ${DEF_RV_BRAND}"
}
# Load configuration
load_configuration "$1"
# Create necessary directories
mkdir -p "$TEMP_DIR" "$BUILD_DIR"
# Handle config update mode
if [[ ${2-} == "--config-update" ]]; then
  log_info "Running config update check..."
  config_update
  exit 0
fi
# Clear changelogs (if any exist)
for changelog in "$TEMP_DIR"/*-rv/changelog.md; do
  [[ -f $changelog ]] && : > "$changelog"
done 2> /dev/null || :
# ==================== Build Processing ====================
# Cache for CLI riplib capability
declare -A cliriplib
# Track parallel jobs
declare -A JOB_NAMES=()
declare -a JOB_PIDS=()
declare -A BUILD_STATUS=()
idx=0
# Process all app configurations
log_info "Starting build process..."
while read -r table_name; do
  if [[ $table_name == "" ]]; then continue; fi
  t=$(toml_get_table "$table_name")
  process_app_config "$table_name" "$t"
done < <(toml_get_table_names)
# Wait for all builds to complete and track failures
log_info "Waiting for all builds to complete..."
declare -a failed_apps=()
declare -a succeeded_apps=()
for pid in "${JOB_PIDS[@]}"; do
  if ! wait "$pid"; then
    app_name="${JOB_NAMES[$pid]:-$pid}"
    failed_apps+=("$app_name")
    BUILD_STATUS["${app_name}"]="failed"
  else
    app_name="${JOB_NAMES[$pid]:-$pid}"
    succeeded_apps+=("$app_name")
    BUILD_STATUS["${app_name}"]="success"
  fi
done
# Report on failed jobs
if [[ ${#failed_apps[@]} -gt 0 ]]; then
  log_warn "${#failed_apps[@]} build job(s) failed: ${failed_apps[*]}"
fi
# Print build status summary
log_info "Build status summary:"
for app in "${!BUILD_STATUS[@]}"; do
  status="${BUILD_STATUS[$app]}"
  emoji=""
  case "$status" in
    success) emoji="✅" ;;
    failed) emoji="❌" ;;
    building) emoji="🔄" ;;
  esac
  log_info "  ${emoji} ${app}: ${status}"
done
# Clean up temporary files
rm -rf temp/tmp.* 2> /dev/null || :
# ==================== Post-Build ====================
# Check if any builds succeeded
if [[ "$(ls -A1 "$BUILD_DIR" 2> /dev/null)" == "" ]]; then
  abort "All builds failed."
fi
# Combine all app-specific logs into build.md
: > build.md
shopt -s nullglob
for log_file in build/*.md; do
  [[ -f "$log_file" ]] && cat "$log_file" >> build.md && echo "" >> build.md
done
shopt -u nullglob
# Add build notes
echo "" >> build.md
echo "Install [Microg](https://github.com/ReVanced/GmsCore/releases) for non-root YouTube and YT Music APKs  " >> build.md
cat "$TEMP_DIR"/*-rv/changelog.md 2> /dev/null || : >> build.md
# Add skipped builds info
SKIPPED=$(cat "$TEMP_DIR"/skipped 2> /dev/null || :)
if [[ $SKIPPED != "" ]]; then
  echo "" >> build.md
  echo "Skipped:" >> build.md
  echo "$SKIPPED  " >> build.md
fi
pr "Build complete! Output in: ${BUILD_DIR}/"
pr "Done"
