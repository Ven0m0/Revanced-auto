#!/usr/bin/env bash
# ReVanced Builder - Main build orchestration script
# Refactored for better maintainability and performance

# Set locale
export LC_ALL=C

# Trap interrupts and clean up
trap "rm -rf temp/*tmp.* temp/*/*tmp.* temp/*-temporary-files; exit 130" INT

# Handle clean command
if [ "${1-}" = "clean" ]; then
    echo "Cleaning build artifacts..."
    rm -rf temp build logs build.md
    echo "Clean complete"
    exit 0
fi

# Source utilities
source utils.sh

# ==================== Prerequisites Check ====================

check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing=()
    local warnings=()

    # Check required commands
    if ! command -v jq &>/dev/null; then
        missing+=("jq")
    fi

    if ! command -v java &>/dev/null; then
        missing+=("java (openjdk-temurin-21)")
    fi

    if ! command -v zip &>/dev/null; then
        missing+=("zip")
    fi

    # Report missing dependencies
    if [ ${#missing[@]} -gt 0 ]; then
        epr "Missing required dependencies: ${missing[*]}"
        epr "Install them with: apt install ${missing[*]} (or equivalent package manager)"
        exit 1
    fi

    # Verify Java version (support both old and new version formats)
    local java_version
    java_version=$(java -version 2>&1 | head -n 1)

    # Extract version number (handles both "1.8" and "17" formats)
    local java_major_version
    if [[ $java_version =~ \"([0-9]+)\.([0-9]+) ]]; then
        # Old format: 1.8.x -> version 8
        if [ "${BASH_REMATCH[1]}" = "1" ]; then
            java_major_version="${BASH_REMATCH[2]}"
        else
            java_major_version="${BASH_REMATCH[1]}"
        fi
    elif [[ $java_version =~ \"([0-9]+) ]]; then
        # New format: 17.x -> version 17
        java_major_version="${BASH_REMATCH[1]}"
    else
        log_warn "Could not parse Java version: $java_version"
        java_major_version="0"
    fi

    if [ "$java_major_version" -lt 21 ]; then
        epr "Java version must be 21 or higher (found: Java $java_major_version)"
        epr "Please install OpenJDK Temurin 21 or later"
        exit 1
    fi

    # Check optional but useful tools
    if ! command -v curl &>/dev/null && ! command -v wget &>/dev/null; then
        warnings+=("neither curl nor wget found (may affect downloads)")
    fi

    # Report warnings
    if [ ${#warnings[@]} -gt 0 ]; then
        for warning in "${warnings[@]}"; do
            log_warn "$warning"
        done
    fi

    log_info "Prerequisites check passed (Java $java_major_version - Temurin 21 required)"
}

check_prerequisites

# Set prebuilt tools
set_prebuilts

# ==================== Configuration Loading ====================

validate_config_value() {
    local value=$1 field=$2 min=${3:-} max=${4:-}

    if [ -n "$min" ] && [ -n "$max" ]; then
        if ((value < min)) || ((value > max)); then
            abort "$field must be within $min-$max (got: $value)"
        fi
    fi
}

load_configuration() {
    local config_file="${1:-config.toml}"

    log_info "Loading configuration from: $config_file"

    if ! toml_prep "$config_file"; then
        abort "Could not find config file '${config_file}'\n\tUsage: $0 <config.toml>"
    fi

    # Load main configuration
    main_config_t=$(toml_get_table_main)

    # Parse configuration values with defaults
    COMPRESSION_LEVEL=$(toml_get "$main_config_t" compression-level) || COMPRESSION_LEVEL="9"
    validate_config_value "$COMPRESSION_LEVEL" "compression-level" 0 9

    if ! PARALLEL_JOBS=$(toml_get "$main_config_t" parallel-jobs); then
        if [ "$OS" = Android ]; then
            PARALLEL_JOBS=1
            log_info "Android detected: setting parallel-jobs=1"
        else
            PARALLEL_JOBS=$(nproc)
            log_info "Auto-detected parallel-jobs=$PARALLEL_JOBS"
        fi
    else
        log_info "Using configured parallel-jobs=$PARALLEL_JOBS"
    fi

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

    log_info "Configuration loaded successfully"
    log_debug "Patches: $DEF_PATCHES_SRC @ $DEF_PATCHES_VER"
    log_debug "CLI: $DEF_CLI_SRC @ $DEF_CLI_VER"
    log_debug "Brand: $DEF_RV_BRAND"
}

# Load configuration
load_configuration "$1"

# Create necessary directories
mkdir -p "$TEMP_DIR" "$BUILD_DIR"

# Handle config update mode
if [ "${2-}" = "--config-update" ]; then
    log_info "Running config update check..."
    config_update
    exit 0
fi

# Initialize build.md
: >build.md

# Clear changelogs (if any exist)
for changelog in "$TEMP_DIR"/*-rv/changelog.md; do
    [ -f "$changelog" ] && : >"$changelog"
done 2>/dev/null || :

# ==================== Build Processing ====================

# Cache for CLI riplib capability
declare -A cliriplib

# Track parallel jobs
idx=0

process_app_config() {
    local table_name=$1
    local t=$2

    log_info "Processing app: $table_name"

    # Check if enabled
    local enabled
    enabled=$(toml_get "$t" enabled) || enabled=true
    vtf "$enabled" "enabled"

    if [ "$enabled" = false ]; then
        log_info "Skipping disabled app: $table_name"
        return
    fi

    # Wait for available job slot
    if ((idx >= PARALLEL_JOBS)); then
        log_debug "Waiting for job slot..."
        wait -n
        idx=$((idx - 1))
    fi

    # Build app configuration
    declare -A app_args

    # Get source configuration
    local patches_src cli_src patches_ver cli_ver
    patches_src=$(toml_get "$t" patches-source) || patches_src=$DEF_PATCHES_SRC
    patches_ver=$(toml_get "$t" patches-version) || patches_ver=$DEF_PATCHES_VER
    cli_src=$(toml_get "$t" cli-source) || cli_src=$DEF_CLI_SRC
    cli_ver=$(toml_get "$t" cli-version) || cli_ver=$DEF_CLI_VER

    # Download prebuilts
    local RVP rv_cli_jar rv_patches_jar

    # Override patches version for dev builds
    if [ "${BUILD_MODE:-}" = "dev" ]; then
        patches_ver="dev"
        log_info "BUILD_MODE=dev: using dev patches version"
    fi

    if ! RVP="$(get_rv_prebuilts "$cli_src" "$cli_ver" "$patches_src" "$patches_ver")"; then
        abort "Could not download ReVanced prebuilts for $table_name"
    fi

    read -r rv_cli_jar rv_patches_jar <<<"$RVP"
    app_args[cli]=$rv_cli_jar
    app_args[ptjar]=$rv_patches_jar

    # Export for use in patching functions
    export rv_cli_jar rv_patches_jar

    # Detect riplib capability
    if [[ -v cliriplib[${app_args[cli]}] ]]; then
        app_args[riplib]=${cliriplib[${app_args[cli]}]}
    else
        if [[ $(java -jar "${app_args[cli]}" patch 2>&1) == *rip-lib* ]]; then
            cliriplib[${app_args[cli]}]=true
            app_args[riplib]=true
            log_debug "CLI supports riplib"
        else
            cliriplib[${app_args[cli]}]=false
            app_args[riplib]=false
            log_debug "CLI does not support riplib"
        fi
    fi

    # Override riplib based on config (app-specific takes precedence over global)
    local app_riplib
    app_riplib=$(toml_get "$t" riplib) || app_riplib=$DEF_RIPLIB

    if [ "$app_riplib" = "false" ]; then
        app_args[riplib]=false
        log_debug "Riplib disabled by config"
    elif [ "$app_riplib" = "true" ] && [ "${app_args[riplib]}" = "false" ]; then
        log_warn "Config enables riplib but CLI doesn't support it"
    fi

    # Parse app-specific configuration
    app_args[rv_brand]=$(toml_get "$t" rv-brand) || app_args[rv_brand]=$DEF_RV_BRAND
    app_args[excluded_patches]=$(toml_get "$t" excluded-patches) || app_args[excluded_patches]=""
    app_args[included_patches]=$(toml_get "$t" included-patches) || app_args[included_patches]=""
    app_args[exclusive_patches]=$(toml_get "$t" exclusive-patches) || app_args[exclusive_patches]=false
    app_args[version]=$(toml_get "$t" version) || app_args[version]="auto"
    app_args[app_name]=$(toml_get "$t" app-name) || app_args[app_name]=$table_name
    app_args[patcher_args]=$(toml_get "$t" patcher-args) || app_args[patcher_args]=""
    app_args[table]=$table_name

    # Validate patch quotes
    if [ -n "${app_args[excluded_patches]}" ] && [[ ${app_args[excluded_patches]} != *'"'* ]]; then
        abort "Patch names inside excluded-patches must be quoted"
    fi
    if [ -n "${app_args[included_patches]}" ] && [[ ${app_args[included_patches]} != *'"'* ]]; then
        abort "Patch names inside included-patches must be quoted"
    fi

    # Validate exclusive patches
    if [ "${app_args[exclusive_patches]}" != "false" ]; then
        vtf "${app_args[exclusive_patches]}" "exclusive-patches"
    fi

    # Parse build mode (only 'apk' supported, Magisk module support removed)
    app_args[build_mode]=$(toml_get "$t" build-mode) || app_args[build_mode]=apk

    # Override with BUILD_MODE environment variable if set
    if [ "${BUILD_MODE:-}" = "dev" ] || [ "${BUILD_MODE:-}" = "stable" ]; then
        # For dev/stable builds, force apk mode only
        app_args[build_mode]=apk
        log_info "BUILD_MODE=$BUILD_MODE: forcing build-mode=apk for $table_name"
    fi

    if [ "${app_args[build_mode]}" != "apk" ]; then
        abort "ERROR: build-mode '${app_args[build_mode]}' is not valid for '${table_name}': only 'apk' is allowed (Magisk module support removed)"
    fi

    # Parse download URLs
    app_args[uptodown_dlurl]=$(toml_get "$t" uptodown-dlurl) || app_args[uptodown_dlurl]=""
    if [ -n "${app_args[uptodown_dlurl]}" ]; then
        app_args[uptodown_dlurl]=${app_args[uptodown_dlurl]%/}
        app_args[uptodown_dlurl]=${app_args[uptodown_dlurl]%download}
        app_args[uptodown_dlurl]=${app_args[uptodown_dlurl]%/}
        app_args[dl_from]=uptodown
    fi

    app_args[apkmirror_dlurl]=$(toml_get "$t" apkmirror-dlurl) || app_args[apkmirror_dlurl]=""
    if [ -n "${app_args[apkmirror_dlurl]}" ]; then
        app_args[apkmirror_dlurl]=${app_args[apkmirror_dlurl]%/}
        app_args[dl_from]=apkmirror
    fi

    app_args[archive_dlurl]=$(toml_get "$t" archive-dlurl) || app_args[archive_dlurl]=""
    if [ -n "${app_args[archive_dlurl]}" ]; then
        app_args[archive_dlurl]=${app_args[archive_dlurl]%/}
        app_args[dl_from]=archive
    fi

    # Validate at least one download source
    if [ -z "${app_args[dl_from]-}" ]; then
        abort "ERROR: no 'apkmirror_dlurl', 'uptodown_dlurl' or 'archive_dlurl' option was set for '$table_name'."
    fi

    # Parse architecture
    app_args[arch]=$(toml_get "$t" arch) || app_args[arch]=$DEF_ARCH
    if [ "${app_args[arch]}" != "both" ] && [ "${app_args[arch]}" != "all" ] &&
        [[ ${app_args[arch]} != "arm64-v8a"* ]] && [[ ${app_args[arch]} != "arm-v7a"* ]]; then
        abort "Wrong arch '${app_args[arch]}' for '$table_name'"
    fi

    # Parse additional options
    app_args[include_stock]=$(toml_get "$t" include-stock) || app_args[include_stock]=true
    vtf "${app_args[include_stock]}" "include-stock"

    app_args[dpi]=$(toml_get "$t" apkmirror-dpi) || app_args[dpi]="nodpi"

    # Handle dual architecture builds
    if [ "${app_args[arch]}" = both ]; then
        # Build arm64-v8a
        app_args[table]="$table_name (arm64-v8a)"
        app_args[arch]="arm64-v8a"
        idx=$((idx + 1))
        build_rv "$(declare -p app_args)" &

        # Build arm-v7a
        app_args[table]="$table_name (arm-v7a)"
        app_args[arch]="arm-v7a"

        if ((idx >= PARALLEL_JOBS)); then
            wait -n
            idx=$((idx - 1))
        fi
        idx=$((idx + 1))
        build_rv "$(declare -p app_args)" &
    else
        # Single architecture build
        idx=$((idx + 1))
        build_rv "$(declare -p app_args)" &
    fi
}

# Process all app configurations
log_info "Starting build process..."
for table_name in $(toml_get_table_names); do
    if [ -z "$table_name" ]; then continue; fi

    t=$(toml_get_table "$table_name")
    process_app_config "$table_name" "$t"
done

# Wait for all builds to complete
log_info "Waiting for all builds to complete..."
wait

# Clean up temporary files
rm -rf temp/tmp.* 2>/dev/null || :

# ==================== Post-Build ====================

# Check if any builds succeeded
if [ -z "$(ls -A1 "${BUILD_DIR}" 2>/dev/null)" ]; then
    abort "All builds failed."
fi

# Add build notes
log "\nInstall [Microg](https://github.com/ReVanced/GmsCore/releases) for non-root YouTube and YT Music APKs"
log "$(cat "$TEMP_DIR"/*-rv/changelog.md 2>/dev/null || :)"

# Add skipped builds info
SKIPPED=$(cat "$TEMP_DIR"/skipped 2>/dev/null || :)
if [ -n "$SKIPPED" ]; then
    log "\nSkipped:"
    log "$SKIPPED"
fi

pr "Build complete! Output in: $BUILD_DIR/"
pr "Done"
