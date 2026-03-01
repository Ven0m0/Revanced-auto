#!/usr/bin/env bash
# Application processing logic
# Orchestrates configuration loading, prebuilt handling, and build job launching

# Helper to safely get config values from the loaded associative array
# Usage: _app_get_config_value <array_name> <key> <default_value>
_app_get_config_value() {
  local -n __agcv_cfg="$1"
  local key="$2"
  local default="${3:-}"

  if [[ -v __agcv_cfg["$key"] ]]; then
     local val="${__agcv_cfg["$key"]}"
     if [[ "$val" != "null" ]]; then
       echo "$val"
       return
     fi
  fi
  echo "$default"
}

# Process a single app configuration
# Args:
#   $1: table_name (App Name)
#   $2: t (TOML table as JSON string)
process_app_config() {
  local table_name="$1"
  local t="$2"

  log_info "Processing app: ${table_name}"

  # Load table into associative array (safe - no eval of user input)
  declare -A t_cfg
  toml_load_table_safe "t_cfg" "$t"

  # Check if enabled
  local enabled
  enabled=$(_app_get_config_value t_cfg "enabled" "true")
  vtf "$enabled" "enabled"
  if [[ "$enabled" == "false" ]]; then
    log_info "Skipping disabled app: ${table_name}"
    return
  fi

  # Wait for available job slot
  _app_manage_concurrency

  # Build app configuration
  declare -A app_args

  # Prepare prebuilts (CLI, patches)
  _app_setup_prebuilts "t_cfg" "app_args" "$table_name" "$t"

  # Detect riplib capability
  _app_configure_riplib "t_cfg" "app_args"

  # Parse remaining app configuration
  _app_build_arguments "t_cfg" "app_args" "$table_name" "$t"

  # Launch build jobs
  _app_execute_build "app_args" "$table_name"
}

_app_manage_concurrency() {
  # Access global idx and PARALLEL_JOBS
  if ((idx >= PARALLEL_JOBS)); then
    log_debug "Waiting for job slot..."
    wait -n
    idx=$((idx - 1))
  fi
}

_app_setup_prebuilts() {
  local -n __asp_cfg="$1"
  local -n __asp_args="$2"
  local table_name="$3"
  local t="$4"

  # Get source configuration
  local -a patches_srcs
  local cli_src patches_ver cli_ver

  # Get patches-source as array (supports both string and array formats for backwards compatibility)
  # Uses global DEF_* variables
  toml_get_array_or_string patches_srcs "$t" "patches-source" "$DEF_PATCHES_SRC"

  patches_ver=$(_app_get_config_value __asp_cfg "patches-version" "$DEF_PATCHES_VER")
  cli_src=$(_app_get_config_value __asp_cfg "cli-source" "$DEF_CLI_SRC")
  cli_ver=$(_app_get_config_value __asp_cfg "cli-version" "$DEF_CLI_VER")

  log_debug "Patches sources (${#patches_srcs[@]}): ${patches_srcs[*]}"

  # Download prebuilts
  local -a rv_prebuilts rv_patches_jars
  local rv_cli_jar

  # Override patches version for dev builds
  if [[ ${BUILD_MODE:-} == "dev" ]]; then
    patches_ver="dev"
    log_info "BUILD_MODE=dev: using dev patches version"
  fi

  # Export patches_ver for get_rv_prebuilts_multi
  export PATCHES_VER="$patches_ver"

  # Download CLI and all patch sources
  mapfile -t rv_prebuilts < <(get_rv_prebuilts_multi "$cli_src" "$cli_ver" "${patches_srcs[@]}")

  if [[ ${#rv_prebuilts[@]} -eq 0 ]]; then
    abort "Could not download ReVanced prebuilts for ${table_name}"
  fi

  # First element is CLI jar, rest are patches jars
  rv_cli_jar="${rv_prebuilts[0]}"
  rv_patches_jars=("${rv_prebuilts[@]:1}")

  __asp_args[cli]="${rv_cli_jar}"
  # Store patches jars as array (will be used in patching)
  __asp_args[ptjars]="${rv_patches_jars[*]}"

  log_debug "CLI: ${rv_cli_jar}"
  log_debug "Patches jars (${#rv_patches_jars[@]}): ${rv_patches_jars[*]}"

  # Export for use in patching functions
  export rv_cli_jar
}

_app_configure_riplib() {
  local -n __acr_cfg="$1"
  local -n __acr_args="$2"

  # Access global cliriplib associative array
  local cli_jar="${__acr_args[cli]}"

  if [[ -v cliriplib[${cli_jar}] ]]; then
    __acr_args[riplib]=${cliriplib[${cli_jar}]}
  else
    if [[ $(java -jar "${cli_jar}" patch 2>&1) == *rip-lib* ]]; then
      cliriplib["${cli_jar}"]=true
      __acr_args[riplib]=true
      log_debug "CLI supports riplib"
    else
      cliriplib["${cli_jar}"]=false
      __acr_args[riplib]=false
      log_debug "CLI does not support riplib"
    fi
  fi

  # Override riplib based on config (app-specific takes precedence over global)
  local app_riplib
  app_riplib=$(_app_get_config_value __acr_cfg "riplib" "$DEF_RIPLIB")

  if [[ "$app_riplib" == "false" ]]; then
    __acr_args[riplib]=false
    log_debug "Riplib disabled by config"
  elif [[ "$app_riplib" == "true" && "${__acr_args[riplib]}" == "false" ]]; then
    log_warn "Config enables riplib but CLI doesn't support it"
  fi
}

_app_build_arguments() {
  local -n __aba_cfg="$1"
  local -n __aba_args="$2"
  local table_name="$3"
  local t="$4"

  # Parse app-specific configuration
  __aba_args[rv_brand]=$(_app_get_config_value __aba_cfg "rv-brand" "$DEF_RV_BRAND")
  __aba_args[excluded_patches]=$(_app_get_config_value __aba_cfg "excluded-patches" "")
  __aba_args[included_patches]=$(_app_get_config_value __aba_cfg "included-patches" "")
  __aba_args[exclusive_patches]=$(_app_get_config_value __aba_cfg "exclusive-patches" "false")
  __aba_args[version]=$(_app_get_config_value __aba_cfg "version" "auto")
  __aba_args[app_name]=$(_app_get_config_value __aba_cfg "app-name" "$table_name")

  # Load patcher-args as an array if present
  local -a patcher_args_array=()
  if toml_get_array "patcher_args_array" "$t" "patcher-args" 2> /dev/null; then
    # Convert array to space-separated string for passing to build_rv
    # The actual array will be reconstructed in patching.sh
    __aba_args[patcher_args]="${patcher_args_array[*]}"
  else
    __aba_args[patcher_args]=""
  fi

  __aba_args[table]="${table_name}"

  # Validate patch quotes
  if [[ "${__aba_args[excluded_patches]}" != "" && "${__aba_args[excluded_patches]}" != *'"'* ]]; then
    abort "Patch names inside excluded-patches must be quoted"
  fi
  if [[ "${__aba_args[included_patches]}" != "" && "${__aba_args[included_patches]}" != *'"'* ]]; then
    abort "Patch names inside included-patches must be quoted"
  fi

  # Validate exclusive patches
  if [[ "${__aba_args[exclusive_patches]}" != "false" ]]; then
    vtf "${__aba_args[exclusive_patches]}" "exclusive-patches"
  fi

  # Parse download URLs
  __aba_args[uptodown_dlurl]=$(_app_get_config_value __aba_cfg "uptodown-dlurl" "")
  if [[ "${__aba_args[uptodown_dlurl]}" != "" ]]; then
    __aba_args[uptodown_dlurl]=${__aba_args[uptodown_dlurl]%/}
    __aba_args[uptodown_dlurl]=${__aba_args[uptodown_dlurl]%download}
    __aba_args[uptodown_dlurl]=${__aba_args[uptodown_dlurl]%/}
    __aba_args[dl_from]=uptodown
  fi

  __aba_args[apkmirror_dlurl]=$(_app_get_config_value __aba_cfg "apkmirror-dlurl" "")
  if [[ "${__aba_args[apkmirror_dlurl]}" != "" ]]; then
    __aba_args[apkmirror_dlurl]=${__aba_args[apkmirror_dlurl]%/}
    __aba_args[dl_from]=apkmirror
  fi

  __aba_args[archive_dlurl]=$(_app_get_config_value __aba_cfg "archive-dlurl" "")
  if [[ "${__aba_args[archive_dlurl]}" != "" ]]; then
    __aba_args[archive_dlurl]=${__aba_args[archive_dlurl]%/}
    __aba_args[dl_from]=archive
  fi

  __aba_args[apkpure_dlurl]=$(_app_get_config_value __aba_cfg "apkpure-dlurl" "")
  if [[ "${__aba_args[apkpure_dlurl]}" != "" ]]; then
    __aba_args[apkpure_dlurl]=${__aba_args[apkpure_dlurl]%/}
    __aba_args[dl_from]=apkpure
  fi

  __aba_args[aptoide_dlurl]=$(_app_get_config_value __aba_cfg "aptoide-dlurl" "")
  if [[ "${__aba_args[aptoide_dlurl]}" != "" ]]; then
    __aba_args[aptoide_dlurl]=${__aba_args[aptoide_dlurl]%/}
    __aba_args[dl_from]=aptoide
  fi

  # Validate at least one download source
  if [[ ${__aba_args[dl_from]-} == "" ]]; then
    abort "ERROR: no download URL option was set for '${table_name}'. Set at least one of: apkmirror-dlurl, uptodown-dlurl, archive-dlurl, apkpure-dlurl, aptoide-dlurl"
  fi

  # Parse architecture
  __aba_args[arch]=$(_app_get_config_value __aba_cfg "arch" "$DEF_ARCH")
  if [[ "${__aba_args[arch]}" != "both" && "${__aba_args[arch]}" != "all" &&
    "${__aba_args[arch]}" != "arm64-v8a"* && "${__aba_args[arch]}" != "arm-v7a"* ]]; then
    abort "Wrong arch '${__aba_args[arch]}' for '${table_name}'"
  fi

  __aba_args[dpi]=$(_app_get_config_value __aba_cfg "apkmirror-dpi" "nodpi")
}

_app_execute_build() {
  local -n __aeb_args="$1"
  local table_name="$2"

  # Handle dual architecture builds
  if [[ "${__aeb_args[arch]}" == both ]]; then
    # Build arm64-v8a
    __aeb_args[table]="${table_name} (arm64-v8a)"
    __aeb_args[arch]="arm64-v8a"

    idx=$((idx + 1))

    # Serialize args to temp file
    local args_file
    args_file=$(mktemp)
    for key in "${!__aeb_args[@]}"; do
      printf '%s=%s\n' "$key" "${__aeb_args[${key}]}" >> "$args_file"
    done

    (
      export BUILD_LOG_FILE="build/${table_name}-arm64-v8a.md"
      build_rv "$args_file"
    ) &
    local pid=$!
    JOB_PIDS+=("$pid")
    JOB_NAMES[$pid]="${table_name} (arm64-v8a)"
    BUILD_STATUS["${table_name} (arm64-v8a)"]="building"

    # Build arm-v7a
    __aeb_args[table]="${table_name} (arm-v7a)"
    __aeb_args[arch]="arm-v7a"

    if ((idx >= PARALLEL_JOBS)); then
      wait -n
      idx=$((idx - 1))
    fi

    idx=$((idx + 1))

    # Serialize args to temp file
    args_file=$(mktemp)
    for key in "${!__aeb_args[@]}"; do
      printf '%s=%s\n' "$key" "${__aeb_args[${key}]}" >> "$args_file"
    done

    (
      export BUILD_LOG_FILE="build/${table_name}-arm-v7a.md"
      build_rv "$args_file"
    ) &
    local pid=$!
    JOB_PIDS+=("$pid")
    JOB_NAMES[$pid]="${table_name} (arm-v7a)"
    BUILD_STATUS["${table_name} (arm-v7a)"]="building"

  else
    # Single architecture build
    idx=$((idx + 1))

    # Serialize args to temp file
    local args_file
    args_file=$(mktemp)
    for key in "${!__aeb_args[@]}"; do
      printf '%s=%s\n' "$key" "${__aeb_args[${key}]}" >> "$args_file"
    done

    (
      export BUILD_LOG_FILE="build/${table_name}.md"
      build_rv "$args_file"
    ) &
    local pid=$!
    JOB_PIDS+=("$pid")
    JOB_NAMES[$pid]="${table_name}"
    BUILD_STATUS["${table_name}"]="building"
  fi
}
