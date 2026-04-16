#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C

check_python() {
  if command -v python3 &> /dev/null; then
    if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)' 2> /dev/null; then
      echo "python"
      return 0
    fi
  fi
  return 1
}

print_deprecation_warning() {
  echo ""
  echo "============================================"
  echo "  WARNING: Bash-based build is deprecated"
  echo "  Please use the new Python CLI instead:"
  echo "    python -m scripts.cli build"
  echo ""
  echo "  The Python CLI provides better performance"
  echo "  and will be the only option in the future."
  echo "============================================"
  echo ""
}

if [[ ${1-} == "cache" ]]; then
  cache_command=${2:-stats}
  if check_python; then
    print_deprecation_warning
    if [[ $# -ge 2 ]]; then
      exec python -m scripts.cli cache "${@:2}"
    fi
    exec python -m scripts.cli cache stats
  fi

  source utils.sh
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

if [[ ${1-} == "clean" ]]; then
  if check_python; then
    exec python -m scripts.cli build --config "${2:-config.toml}" --clean
  fi
  print_deprecation_warning
  echo "Cleaning build artifacts..."
  rm -rf temp build logs build.md
  echo "Clean complete"
  exit 0
fi

if check_python; then
  print_deprecation_warning
  exec python -m scripts.cli build "$@"
fi

trap "rm -rf temp/*tmp.* temp/*/*tmp.* temp/*-temporary-files; exit 130" INT

print_deprecation_warning
source utils.sh

check_prerequisites
set_prebuilts

load_configuration() {
  local config_file="${1:-config.toml}"
  log_info "Loading configuration from: ${config_file}"
  if ! toml_prep "$config_file"; then
    abort "Could not find config file '${config_file}'\n\tUsage: $0 <config.toml>"
  fi
  main_config_t=$(toml_get_table_main)
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

load_configuration "${1:-config.toml}"
mkdir -p "$TEMP_DIR" "$BUILD_DIR"

if [[ ${2-} == "--config-update" ]]; then
  log_info "Running config update check..."
  config_update
  exit 0
fi

for changelog in "$TEMP_DIR"/*-rv/changelog.md; do
  [[ -f $changelog ]] && : > "$changelog"
done 2> /dev/null || :

declare -A cliriplib
declare -A JOB_NAMES=()
declare -a JOB_PIDS=()
declare -A BUILD_STATUS=()
idx=0

log_info "Starting build process..."
while read -r table_name; do
  if [[ $table_name == "" ]]; then continue; fi
  t=$(toml_get_table "$table_name")
  process_app_config "$table_name" "$t"
done < <(toml_get_table_names)

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

if [[ ${#failed_apps[@]} -gt 0 ]]; then
  log_warn "${#failed_apps[@]} build job(s) failed: ${failed_apps[*]}"
fi

log_info "Build status summary:"
for app in "${!BUILD_STATUS[@]}"; do
  status="${BUILD_STATUS[$app]}"
  emoji=""
  case "$status" in
    success) emoji="✅" ;;
    failed) emoji="❌" ;;
    building) emoji="🔄" ;;
    *) emoji="❓" ;;
  esac
  log_info "  ${emoji} ${app}: ${status}"
done

rm -rf temp/tmp.* 2> /dev/null || :

if [[ "$(ls -A1 "$BUILD_DIR" 2> /dev/null)" == "" ]]; then
  abort "All builds failed."
fi

: > build.md
shopt -s nullglob
for log_file in build/*.md; do
  if [[ -f "$log_file" ]]; then
    {
      cat "$log_file"
      echo ""
    } >> build.md
  fi
done
shopt -u nullglob

{
  echo ""
  echo "### MicroG / GmsCore (Required for YouTube & YT Music)"
  echo "Download and install one of the following GmsCore providers:"
  echo "- [ReVanced GmsCore](https://github.com/ReVanced/GmsCore/releases/latest)"
  echo "- [Wst_Xda GmsCore (Morphe)](https://github.com/MorpheApp/MicroG-RE/releases/latest)"
  echo "- [YT-Advanced GmsCore (Rex)](https://github.com/YT-Advanced/GmsCore/releases/latest)"
  echo ""
} >> build.md
cat "$TEMP_DIR"/*-rv/changelog.md >> build.md 2> /dev/null || :

SKIPPED=$(cat "$TEMP_DIR"/skipped 2> /dev/null || :)
if [[ $SKIPPED != "" ]]; then
  {
    echo ""
    echo "Skipped:"
    echo "$SKIPPED  "
  } >> build.md
fi

pr "Build complete! Output in: ${BUILD_DIR}/"
pr "Done"
