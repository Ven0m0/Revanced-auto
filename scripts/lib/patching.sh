#!/usr/bin/env bash
set -euo pipefail
# APK patching and building functions
# Cache for signature verification (format: "pkg:version" -> signature)
declare -gA __SIG_CACHE__
# Check APK signature against known signatures
# Args:
#   $1: APK file path
#   $2: Package name
#   $3: Version (optional, for caching)
# Returns:
#   0 if signature valid or not in sig.txt, 1 on mismatch
check_sig() {
  local file=$1 pkg_name=$2 version=${3:-}
  if ! grep -q "$pkg_name" assets/sig.txt; then
    log_debug "No signature check required for $pkg_name"
    return 0
  fi
  local cache_key="${pkg_name}:${version}"
  local sig
  # Check cache first
  if [[ -n "$version" ]] && [[ -v __SIG_CACHE__[$cache_key] ]]; then
    sig="${__SIG_CACHE__[$cache_key]}"
    log_debug "Using cached signature for $cache_key"
  else
    log_info "Verifying APK signature for $pkg_name"
    sig=$(java -jar "$APKSIGNER" verify --print-certs "$file" | grep ^Signer | grep SHA-256 | tail -1 | awk '{print $NF}')
    # Cache the signature
    if [[ -n "$version" ]]; then
      __SIG_CACHE__[$cache_key]="$sig"
    fi
  fi
  if grep -qFx "$sig $pkg_name" assets/sig.txt; then
    log_debug "Signature valid: $sig"
    return 0
  else
    epr "Signature mismatch for $pkg_name: $sig"
    return 1
  fi
}
# Merge split APKs into a single APK
# Args:
#   $1: Bundle file path
#   $2: Output file path
# Returns:
#   0 on success, 1 on failure
merge_splits() {
  local bundle=$1 output=$2
  pr "Merging splits"
  gh_dl "$TEMP_DIR/apkeditor.jar" \
    "https://github.com/REAndroid/APKEditor/releases/download/V1.4.2/APKEditor-1.4.2.jar" > /dev/null || return 1
  if ! OP=$(java -jar "$TEMP_DIR/apkeditor.jar" merge -i "$bundle" -o "${bundle}.mzip" -clean-meta -f 2>&1); then
    epr "APKEditor ERROR: $OP"
    return 1
  fi
  # Repackage using zip (required for apksig compatibility)
  mkdir "${bundle}-zip" || return 1
  check_zip_safety "${bundle}.mzip" || return 1
  unzip -qo "${bundle}.mzip" -d "${bundle}-zip" || return 1
  (
    cd "${bundle}-zip" || return 1
    zip -0rq "${bundle}.zip" . || return 1
  )
  # Copy merged APK (signing is done during patching step)
  cp "${bundle}.zip" "$output"
  local ret=$?
  rm -r "${bundle}-zip" "${bundle}.zip" "${bundle}.mzip" 2> /dev/null || :
  return "$ret"
}
# Patch APK using ReVanced CLI
# Args:
#   $1: Stock APK path
#   $2: Patched APK output path
#   $3: Patcher arguments (space-separated string)
#   $4: ReVanced CLI JAR path
#   $5+: Patches JAR path(s) - supports multiple for multi-source patching
# Returns:
#   0 on success, 1 on failure
patch_apk() {
  local stock_input=$1 patched_apk=$2 patcher_args=$3 rv_cli_jar=$4
  shift 4
  local -a rv_patches_jars=("$@")
  if [[ ${#rv_patches_jars[@]} -eq 0 ]]; then
    abort "patch_apk: at least one patches JAR required"
  fi
  log_debug "Patching with ${#rv_patches_jars[@]} patch bundle(s)"
  # Validate keystore configuration (fail fast for public CI)
  local keystore="${KEYSTORE_PATH:-assets/ks.keystore}"
  if [[ -z "${KEYSTORE_PASSWORD:-}" ]]; then
    abort "KEYSTORE_PASSWORD environment variable is required but not set"
  fi
  if [[ -z "${KEYSTORE_ENTRY_PASSWORD:-}" ]]; then
    abort "KEYSTORE_ENTRY_PASSWORD environment variable is required but not set"
  fi
  if [[ ! -f "$keystore" ]]; then
    abort "Keystore not found: $keystore"
  fi
  local keystore_pass="$KEYSTORE_PASSWORD"
  local keystore_entry_pass="$KEYSTORE_ENTRY_PASSWORD"
  local keystore_alias="${KEYSTORE_ALIAS:-jhc}"
  local keystore_signer="${KEYSTORE_SIGNER:-jhc}"
  # Build command as array (no eval, no injection)
  local -a cmd=(
    env
    -u GITHUB_REPOSITORY
    java
    -jar "$rv_cli_jar"
    patch
    "$stock_input"
    --purge
    -o "$patched_apk"
  )
  # Add -p flag for each patches jar (order matters - last wins on conflicts)
  for patches_jar in "${rv_patches_jars[@]}"; do
    cmd+=("-p" "$patches_jar")
  done
  # Add keystore configuration (use env vars for passwords)
  # Export passwords to environment for safer passing
  export RV_KEYSTORE_PASSWORD="$keystore_pass"
  export RV_KEYSTORE_ENTRY_PASSWORD="$keystore_entry_pass"
  cmd+=(
    "--keystore=$keystore"
    "--keystore-entry-password=env:RV_KEYSTORE_ENTRY_PASSWORD"
    "--keystore-password=env:RV_KEYSTORE_PASSWORD"
    "--signer=$keystore_signer"
    "--keystore-entry-alias=$keystore_alias"
  )
  # Add patcher args (split space-separated string into array elements)
  if [[ -n "$patcher_args" ]]; then
    local arg
    while IFS= read -r arg; do
      [[ -n "$arg" ]] && cmd+=("$arg")
    done < <(xargs -n1 <<< "$patcher_args")
  fi
  # Add Android-specific AAPT2 if needed
  if [[ "$OS" = "Android" ]]; then
    cmd+=("--custom-aapt2-binary=${AAPT2}")
  fi
  # Log command with secrets redacted
  local -a redacted_cmd=("${cmd[@]}")
  for i in "${!redacted_cmd[@]}"; do
    if [[ "${redacted_cmd[$i]}" == --keystore-*password=* ]]; then
      redacted_cmd[$i]="${redacted_cmd[$i]%%=*}=***"
    fi
  done
  pr "Executing: ${redacted_cmd[*]}"
  # Execute command (no eval - direct array expansion)
  if ! "${cmd[@]}"; then
    rm -f "$patched_apk" 2> /dev/null
    epr "Patching failed for APK"
    return 1
  fi
  if [[ ! -f "$patched_apk" ]]; then
    epr "Patching succeeded but output APK not found: $patched_apk"
    return 1
  fi
  # Re-sign with apksigner to enforce v1+v2 signature scheme (never higher)
  log_info "Re-signing APK with v1+v2 signature scheme enforcement"
  local temp_signed="${patched_apk}.tmp-signed.apk"
  # Use environment variables for passwords (already exported above)
  local -a sign_cmd=(
    java
    -jar "$APKSIGNER"
    sign
    --ks "$keystore"
    --ks-pass "env:RV_KEYSTORE_PASSWORD"
    --ks-key-alias "$keystore_alias"
    --key-pass "env:RV_KEYSTORE_ENTRY_PASSWORD"
    --v1-signing-enabled true
    --v2-signing-enabled true
    --v3-signing-enabled false
    --v4-signing-enabled false
    --out "$temp_signed"
    "$patched_apk"
  )
  # No need to redact - passwords are now in env vars, not command line
  log_debug "Re-signing: ${sign_cmd[*]}"
  if "${sign_cmd[@]}"; then
    mv -f "$temp_signed" "$patched_apk"
    log_info "APK re-signed successfully with v1+v2 only"
    return 0
  else
    rm -f "$temp_signed" 2> /dev/null
    epr "Re-signing with apksigner failed"
    return 1
  fi
}
# Determine target version for patching
# Args:
#   $1: Version mode (auto/latest/beta/specific)
#   $2: Package name
#   $3: Download source
#   $4: List patches output
#   $5: Included patches
#   $6: Excluded patches
#   $7: Exclusive patches flag
# Returns:
#   Version string via stdout
_determine_version() {
  local version_mode=$1 pkg_name=$2 dl_from=$3
  local list_patches=$4 inc_patches=$5 exc_patches=$6 exclusive=$7
  local version=""
  if [[ "$version_mode" = auto ]]; then
    log_info "Auto-detecting compatible version"
    # Convert space-separated string to array for version detection
    local -a patches_jars_array
    read -ra patches_jars_array <<< "${args[ptjars]}"
    if ! version=$(get_patch_last_supported_ver "$list_patches" "$pkg_name" \
      "$inc_patches" "$exc_patches" "$exclusive" "${args[cli]}" "${patches_jars_array[@]}"); then
      return 1
    fi
    if [[ "$version" = "" ]]; then
      log_debug "No specific version required, using latest"
      version_mode="latest"
    fi
  fi
  if isoneof "$version_mode" latest beta; then
    if [[ "$version_mode" = beta ]]; then
      __AAV__="true"
      log_info "Fetching latest beta version"
    else
      __AAV__="false"
      log_info "Fetching latest stable version"
    fi
    local pkgvers
    pkgvers=$(get_"${dl_from}"_vers)
    version=$(get_highest_ver <<< "$pkgvers") || version=$(head -1 <<< "$pkgvers")
  elif [[ "$version_mode" != "auto" ]]; then
    version=$version_mode
  fi
  echo "$version"
}
# Build patcher arguments array
# Args:
#   Variables from args associative array
# Returns:
#   Sets p_patcher_args array
_build_patcher_args() {
  p_patcher_args=()
  if [[ "${args[excluded_patches]}" ]]; then
    p_patcher_args+=("$(join_args "${args[excluded_patches]}" -d)")
    log_debug "Excluded patches: ${args[excluded_patches]}"
  fi
  if [[ "${args[included_patches]}" ]]; then
    p_patcher_args+=("$(join_args "${args[included_patches]}" -e)")
    log_debug "Included patches: ${args[included_patches]}"
  fi
  if [[ "${args[exclusive_patches]}" = true ]]; then
    p_patcher_args+=("--exclusive")
    log_debug "Exclusive patches mode enabled"
  fi
  # Parse patcher_args from space-separated string back to array
  if [[ "${args[patcher_args]}" ]]; then
    # Split on spaces while preserving quoted arguments
    local arg
    while IFS= read -r arg; do
      [[ "$arg" != "" ]] && p_patcher_args+=("$arg")
    done < <(xargs -n1 <<< "${args[patcher_args]}")
  fi
}
# Download stock APK from available sources
# Args:
#   $1: Stock APK path
#   $2: Version
#   $3: Architecture
#   $4: DPI
# Returns:
#   0 on success, 1 on failure
_download_stock_apk() {
  local stock_apk=$1 version=$2 arch=$3 dpi=$4
  local table=${args[table]}
  for dl_p in archive apkmirror uptodown; do
    if [[ "${args[${dl_p}_dlurl]}" = "" ]]; then continue; fi
    pr "Downloading '${table}' from ${dl_p}"
    if ! isoneof "$dl_p" "${tried_dl[@]}"; then
      get_"${dl_p}"_resp "${args[${dl_p}_dlurl]}"
    fi
    if dl_"$dl_p" "${args[${dl_p}_dlurl]}" "$version" "$stock_apk" "$arch" "$dpi"; then
      return 0
    else
      epr "ERROR: Could not download '${table}' from ${dl_p} with version '${version}', arch '${arch}', dpi '${dpi}'"
    fi
  done
  return 1
}
# Handle MicroG patch inclusion/exclusion
# Args:
#   $1: List patches output
# Returns:
#   Updates p_patcher_args array, echoes microg_patch name
_handle_microg_patch() {
  local list_patches=$1
  local microg_patch
  microg_patch=$(grep "^Name: " <<< "$list_patches" | grep -i "gmscore\|microg" || :)
  microg_patch=${microg_patch#*: }
  if [[ "$microg_patch" != "" && "${p_patcher_args[*]}" =~ ${microg_patch} ]]; then
    epr "You can't include/exclude microg patch as that's done by rvmm builder automatically."
    p_patcher_args=("${p_patcher_args[@]//-[ei] ${microg_patch}/}")
  fi
  echo "$microg_patch"
}
# Apply library stripping optimizations
# Args:
#   $1: Architecture
# Returns:
#   Updates the global patcher_args array with riplib flags
_apply_riplib_optimization() {
  local arch=$1
  if [[ "${args[riplib]}" != true ]]; then
    return
  fi
  log_info "Applying library stripping optimization"
  patcher_args+=("--rip-lib x86_64 --rip-lib x86")
  if [[ "$arch" = "arm64-v8a" ]]; then
    patcher_args+=("--rip-lib armeabi-v7a")
  elif [[ "$arch" = "arm-v7a" ]]; then
    patcher_args+=("--rip-lib arm64-v8a")
  fi
}
# Main build function for ReVanced APK/Module
# Args:
#   $1: Path to temporary file containing serialized array
# Get cached list of patches
# Args:
#   $1: Path to CLI JAR
#   $2: Path to patches JAR
# Returns:
#   List of patches (via stdout)
get_cached_patches_list() {
  local cli_jar=$1 patches_jar=$2
  if [[ ! -f "$cli_jar" || ! -f "$patches_jar" ]]; then
    log_warn "get_cached_patches_list: jars not found"
    return 1
  fi
  # Calculate cache key based on hashes of both jars
  local cli_hash patches_hash
  if ! cli_hash=$(get_file_hash "$cli_jar"); then
    log_warn "Failed to get hash for '$cli_jar'"
    return 1
  fi
  if ! patches_hash=$(get_file_hash "$patches_jar"); then
    log_warn "Failed to get hash for '$patches_jar'"
    return 1
  fi
  local cache_key="patches-list-${cli_hash}-${patches_hash}.txt"
  local cache_path
  cache_path=$(get_cache_path "$cache_key" "patches")
  # Ensure cache directory exists
  mkdir -p "$(dirname "$cache_path")"
  # Check cache
  if cache_is_valid "$cache_path"; then
    log_debug "Using cached patch list: $cache_path"
    cat "$cache_path"
    return 0
  fi
  log_debug "Generating patch list cache..."
  # Run list-patches without -f pkg_name to get full list
  local temp_file
  temp_file=$(mktemp)
  if ! java -jar "$cli_jar" list-patches "$patches_jar" -v -p > "$temp_file" 2>&1; then
    rm -f "$temp_file"
    log_warn "Failed to list patches"
    return 1
  fi
  # Atomic update of cache
  mv "$temp_file" "$cache_path"
  cache_put "$cache_path"
  cat "$cache_path"
}
build_rv() {
  local args_file=$1
  declare -A args
  # Safely load args from file
  while IFS='=' read -r key value; do
    [[ -n "$key" && "$key" != \#* ]] && args[$key]=$value
  done < "$args_file"
  # Clean up temp file
  rm -f "$args_file"
  local version="" pkg_name=""
  local version_mode=${args[version]}
  local app_name=${args[app_name]}
  local app_name_l=${app_name,,}
  app_name_l=${app_name_l// /-}
  local table=${args[table]}
  local dl_from=${args[dl_from]}
  local arch=${args[arch]}
  local arch_f="${arch// /}"
  log_info "Building ${table} (${arch})"
  # Build patcher arguments
  _build_patcher_args
  # Determine package name from download sources
  local tried_dl=()
  for dl_p in archive apkmirror uptodown; do
    if [[ "${args[${dl_p}_dlurl]}" = "" ]]; then continue; fi
    if ! get_"${dl_p}"_resp "${args[${dl_p}_dlurl]}" || ! pkg_name=$(get_"${dl_p}"_pkg_name); then
      args[${dl_p}_dlurl]=""
      epr "ERROR: Could not find ${table} in ${dl_p}"
      continue
    fi
    tried_dl+=("$dl_p")
    dl_from=$dl_p
    break
  done
  if [[ "$pkg_name" = "" ]]; then
    epr "Empty package name, not building ${table}."
    return 0
  fi
  log_info "Package name: $pkg_name"
  # Get patch information from all patch sources (run in parallel for performance)
  local list_patches="" source_idx=1
  local -a patches_jars_array
  read -ra patches_jars_array <<< "${args[ptjars]}"
  log_debug "Listing patches from ${#patches_jars_array[@]} source(s)"

  # Pre-calculate hashes to populate global cache for parallel subshells
  get_file_hash "${args[cli]}" > /dev/null || :
  for jar in "${patches_jars_array[@]}"; do
    get_file_hash "$jar" > /dev/null || :
  done
  # Run list-patches commands in parallel to save time
  local -a temp_files=() pids=()
  for patches_jar in "${patches_jars_array[@]}"; do
    log_debug "Listing patches from source ${source_idx}/${#patches_jars_array[@]}: $patches_jar"
    local temp_file
    temp_file=$(mktemp)
    temp_files+=("$temp_file")
    # Run in background
    (get_cached_patches_list "${args[cli]}" "$patches_jar" > "$temp_file") &
    pids+=($!)
    source_idx=$((source_idx + 1))
  done
  # Wait for all background jobs and collect results
  for pid in "${pids[@]}"; do
    wait "$pid"
  done
  # Combine results from temp files
  for temp_file in "${temp_files[@]}"; do
    list_patches+="$(cat "$temp_file")"$'\n'
    rm -f "$temp_file"
  done
  # Determine version to build
  version=$(_determine_version "$version_mode" "$pkg_name" "$dl_from" "$list_patches" \
    "${args[included_patches]}" "${args[excluded_patches]}" "${args[exclusive_patches]}")
  if [[ "$version" = "" ]]; then
    epr "Empty version, not building ${table}."
    return 0
  fi
  # Handle force flag for non-auto versions
  if ! [[ "$version_mode" == "auto" ]] || isoneof "$version_mode" latest beta; then
    p_patcher_args+=("-f")
  fi
  pr "Choosing version '${version}' for ${table}"
  # Download stock APK
  local version_f
  version_f=$(format_version "$version")
  local stock_apk="${TEMP_DIR}/${pkg_name}-${version_f}-${arch_f}.apk"
  if [[ ! -f "$stock_apk" ]]; then
    if ! _download_stock_apk "$stock_apk" "$version" "$arch" "${args[dpi]}"; then
      epr "Failed to download stock APK"
      return 0
    fi
  else
    log_info "Using cached stock APK: $stock_apk"
  fi
  # Verify signature (with version for caching)
  if ! OP=$(check_sig "$stock_apk" "$pkg_name" "$version_f" 2>&1) \
    && ! grep -qFx "ERROR: Missing META-INF/MANIFEST.MF" <<< "$OP"; then
    abort "APK signature mismatch '$stock_apk': $OP"
  fi
  log "${table}: ${version}"
  # Handle MicroG patch
  local microg_patch
  microg_patch=$(_handle_microg_patch "$list_patches")
  # Build APK (Magisk module support removed)
  local patcher_args patched_apk
  local rv_brand_f=${args[rv_brand],,}
  rv_brand_f=${rv_brand_f// /-}
  patcher_args=("${p_patcher_args[@]}")
  pr "Building '${table}' in APK mode"
  # Set output filename
  patched_apk="${TEMP_DIR}/${app_name_l}-${rv_brand_f}-${version_f}-${arch_f}.apk"
  if [[ "$microg_patch" != "" ]]; then
    patcher_args+=("-e \"${microg_patch}\"")
  fi
  # Apply optimizations
  _apply_riplib_optimization "$arch"
  # Patch APK
  if [[ "${NORB:-}" != true || ! -f "$patched_apk" ]]; then
    # Convert space-separated patches jars to array for patch_apk
    local -a patches_jars_array
    read -ra patches_jars_array <<< "${args[ptjars]}"
    if ! patch_apk "$stock_apk" "$patched_apk" "${patcher_args[*]}" "${args[cli]}" "${patches_jars_array[@]}"; then
      epr "Building '${table}' failed!"
      return 0
    fi
  else
    log_info "Using existing patched APK: $patched_apk"
  fi
  # Zipalign the patched APK for optimization
  log_info "Applying zipalign to patched APK"
  local aligned_apk="${patched_apk%.apk}-aligned.apk"
  if command -v zipalign &> /dev/null; then
    if zipalign -f -p 4 "$patched_apk" "$aligned_apk"; then
      log_info "APK successfully zipaligned"
      mv -f "$aligned_apk" "$patched_apk"
    else
      log_warn "zipalign failed, continuing with unaligned APK"
      rm -f "$aligned_apk" 2> /dev/null || :
    fi
  else
    log_warn "zipalign not found in PATH, skipping alignment"
  fi
  # Prepare APK output
  local apk_output="${BUILD_DIR}/${app_name_l}-${rv_brand_f}-v${version_f}-${arch_f}.apk"
  # Apply aapt2 optimization if enabled and architecture is arm64-v8a
  local apk_to_move="$patched_apk"
  if [[ "${ENABLE_AAPT2_OPTIMIZE:-false}" = "true" && "$arch" = "arm64-v8a" ]]; then
    log_info "Applying aapt2 optimization (en, xxhdpi, arm64-v8a only)"
    local optimized_apk="${patched_apk%.apk}-optimized.apk"
    if [[ -f "scripts/aapt2-optimize.sh" ]]; then
      if ./scripts/aapt2-optimize.sh "$patched_apk" "$optimized_apk"; then
        apk_to_move="$optimized_apk"
      else
        log_info "aapt2 optimization failed, using unoptimized APK"
      fi
    else
      log_info "aapt2-optimize.sh not found, skipping optimization"
    fi
  fi
  mv -f "$apk_to_move" "$apk_output"
  pr "Built ${table}: '${apk_output}'"
}
