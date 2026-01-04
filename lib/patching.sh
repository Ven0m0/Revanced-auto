#!/usr/bin/env bash
# APK patching and building functions

# Check APK signature against known signatures
# Args:
#   $1: APK file path
#   $2: Package name
# Returns:
#   0 if signature valid or not in sig.txt, 1 on mismatch
check_sig() {
    local file=$1 pkg_name=$2

    if ! grep -q "$pkg_name" sig.txt; then
        log_debug "No signature check required for $pkg_name"
        return 0
    fi

    log_info "Verifying APK signature for $pkg_name"
    local sig
    sig=$(java -jar "$APKSIGNER" verify --print-certs "$file" | grep ^Signer | grep SHA-256 | tail -1 | awk '{print $NF}')

    if grep -qFx "$sig $pkg_name" sig.txt; then
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
        "https://github.com/REAndroid/APKEditor/releases/download/V1.4.2/APKEditor-1.4.2.jar" >/dev/null || return 1

    if ! OP=$(java -jar "$TEMP_DIR/apkeditor.jar" merge -i "${bundle}" -o "${bundle}.mzip" -clean-meta -f 2>&1); then
        epr "APKEditor ERROR: $OP"
        return 1
    fi

    # Repackage using zip (required for apksig compatibility)
    mkdir "${bundle}-zip" || return 1
    unzip -qo "${bundle}.mzip" -d "${bundle}-zip" || return 1

    (
        cd "${bundle}-zip" || return 1
        zip -0rq "${CWD}/${bundle}.zip" . || return 1
    )

    # Copy merged APK (signing is done during patching step)
    cp "${bundle}.zip" "${output}"
    local ret=$?

    rm -r "${bundle}-zip" "${bundle}.zip" "${bundle}.mzip" 2>/dev/null || :
    return $ret
}

# Patch APK using ReVanced CLI
# Args:
#   $1: Stock APK path
#   $2: Patched APK output path
#   $3: Patcher arguments
#   $4: ReVanced CLI JAR path
#   $5: Patches JAR path
# Returns:
#   0 on success, 1 on failure
patch_apk() {
    local stock_input=$1 patched_apk=$2 patcher_args=$3 rv_cli_jar=$4 rv_patches_jar=$5

    local cmd="env -u GITHUB_REPOSITORY java -jar $rv_cli_jar patch $stock_input --purge -o $patched_apk -p $rv_patches_jar"
    cmd+=" --keystore=ks.keystore --keystore-entry-password=123456789"
    cmd+=" --keystore-password=123456789 --signer=jhc --keystore-entry-alias=jhc"
    cmd+=" $patcher_args"

    if [ "$OS" = Android ]; then
        cmd+=" --custom-aapt2-binary=${AAPT2}"
    fi

    pr "$cmd"

    if eval "$cmd"; then
        if [ -f "$patched_apk" ]; then
            return 0
        else
            epr "Patching succeeded but output APK not found: $patched_apk"
            return 1
        fi
    else
        rm -f "$patched_apk" 2>/dev/null
        epr "Patching failed for APK"
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

    if [ "$version_mode" = auto ]; then
        log_info "Auto-detecting compatible version"
        if ! version=$(get_patch_last_supported_ver "$list_patches" "$pkg_name" \
            "$inc_patches" "$exc_patches" "$exclusive" "${args[cli]}" "${args[ptjar]}"); then
            return 1
        fi

        if [ -z "$version" ]; then
            log_debug "No specific version required, using latest"
            version_mode="latest"
        fi
    fi

    if [ "$version_mode" = "auto" ] && [ -z "$version" ]; then
        version_mode="latest"
    fi

    if isoneof "$version_mode" latest beta; then
        if [ "$version_mode" = beta ]; then
            __AAV__="true"
            log_info "Fetching latest beta version"
        else
            __AAV__="false"
            log_info "Fetching latest stable version"
        fi

        local pkgvers
        pkgvers=$(get_"${dl_from}"_vers)
        version=$(get_highest_ver <<<"$pkgvers") || version=$(head -1 <<<"$pkgvers")
    elif [ "$version_mode" != "auto" ]; then
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

    if [ "${args[excluded_patches]}" ]; then
        p_patcher_args+=("$(join_args "${args[excluded_patches]}" -d)")
        log_debug "Excluded patches: ${args[excluded_patches]}"
    fi

    if [ "${args[included_patches]}" ]; then
        p_patcher_args+=("$(join_args "${args[included_patches]}" -e)")
        log_debug "Included patches: ${args[included_patches]}"
    fi

    if [ "${args[exclusive_patches]}" = true ]; then
        p_patcher_args+=("--exclusive")
        log_debug "Exclusive patches mode enabled"
    fi

    if [ "${args[patcher_args]}" ]; then
        p_patcher_args+=("${args[patcher_args]}")
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
        if [ -z "${args[${dl_p}_dlurl]}" ]; then continue; fi

        pr "Downloading '${table}' from ${dl_p}"

        if ! isoneof $dl_p "${tried_dl[@]}"; then
            get_${dl_p}_resp "${args[${dl_p}_dlurl]}"
        fi

        if dl_${dl_p} "${args[${dl_p}_dlurl]}" "$version" "$stock_apk" "$arch" "$dpi"; then
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
#   $2: Array name to update (p_patcher_args)
# Returns:
#   Updates the specified array, echoes microg_patch name
_handle_microg_patch() {
    local list_patches=$1
    local array_name=${2:-p_patcher_args}
    local microg_patch

    microg_patch=$(grep "^Name: " <<<"$list_patches" | grep -i "gmscore\|microg" || :)
    microg_patch=${microg_patch#*: }

    if [ -n "$microg_patch" ] && [[ ${p_patcher_args[*]} =~ $microg_patch ]]; then
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

    if [ "${args[riplib]}" != true ]; then
        return
    fi

    log_info "Applying library stripping optimization"
    patcher_args+=("--rip-lib x86_64 --rip-lib x86")

    if [ "$arch" = "arm64-v8a" ]; then
        patcher_args+=("--rip-lib armeabi-v7a")
    elif [ "$arch" = "arm-v7a" ]; then
        patcher_args+=("--rip-lib arm64-v8a")
    fi
}

# Main build function for ReVanced APK/Module
# Args:
#   $1: Associative array declaration string with build args
build_rv() {
    eval "declare -A args=${1#*=}"

    local version="" pkg_name=""
    local mode_arg=${args[build_mode]} version_mode=${args[version]}
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
        if [ -z "${args[${dl_p}_dlurl]}" ]; then continue; fi

        if ! get_${dl_p}_resp "${args[${dl_p}_dlurl]}" || ! pkg_name=$(get_"${dl_p}"_pkg_name); then
            args[${dl_p}_dlurl]=""
            epr "ERROR: Could not find ${table} in ${dl_p}"
            continue
        fi

        tried_dl+=("$dl_p")
        dl_from=$dl_p
        break
    done

    if [ -z "$pkg_name" ]; then
        epr "Empty package name, not building ${table}."
        return 0
    fi

    log_info "Package name: $pkg_name"

    # Get patch information
    local list_patches
    list_patches=$(java -jar "${args[cli]}" list-patches "${args[ptjar]}" -f "$pkg_name" -v -p 2>&1)

    # Determine version to build
    version=$(_determine_version "$version_mode" "$pkg_name" "$dl_from" "$list_patches" \
        "${args[included_patches]}" "${args[excluded_patches]}" "${args[exclusive_patches]}")

    if [ -z "$version" ]; then
        epr "Empty version, not building ${table}."
        return 0
    fi

    # Handle force flag for non-auto versions
    if ! [ "$version_mode" = "auto" ] || isoneof "$version_mode" latest beta; then
        p_patcher_args+=("-f")
    fi

    pr "Choosing version '${version}' for ${table}"

    # Download stock APK
    local version_f=${version// /}
    version_f=${version_f#v}
    local stock_apk="${TEMP_DIR}/${pkg_name}-${version_f}-${arch_f}.apk"

    if [ ! -f "$stock_apk" ]; then
        if ! _download_stock_apk "$stock_apk" "$version" "$arch" "${args[dpi]}"; then
            epr "Failed to download stock APK"
            return 0
        fi
    else
        log_info "Using cached stock APK: $stock_apk"
    fi

    # Verify signature
    if ! OP=$(check_sig "$stock_apk" "$pkg_name" 2>&1) &&
        ! grep -qFx "ERROR: Missing META-INF/MANIFEST.MF" <<<"$OP"; then
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

    if [ -n "$microg_patch" ]; then
        patcher_args+=("-e \"${microg_patch}\"")
    fi

    # Apply optimizations
    _apply_riplib_optimization "$arch"

    # Patch APK
    if [ "${NORB:-}" != true ] || [ ! -f "$patched_apk" ]; then
        if ! patch_apk "$stock_apk" "$patched_apk" "${patcher_args[*]}" "${args[cli]}" "${args[ptjar]}"; then
            epr "Building '${table}' failed!"
            return 0
        fi
    else
        log_info "Using existing patched APK: $patched_apk"
    fi

    # Zipalign the patched APK for optimization
    log_info "Applying zipalign to patched APK"
    local aligned_apk="${patched_apk%.apk}-aligned.apk"
    if command -v zipalign &>/dev/null; then
        if zipalign -f -p 4 "$patched_apk" "$aligned_apk"; then
            log_info "APK successfully zipaligned"
            mv -f "$aligned_apk" "$patched_apk"
        else
            log_warn "zipalign failed, continuing with unaligned APK"
            rm -f "$aligned_apk" 2>/dev/null || :
        fi
    else
        log_warn "zipalign not found in PATH, skipping alignment"
    fi

    # Prepare APK output
    local apk_output="${BUILD_DIR}/${app_name_l}-${rv_brand_f}-v${version_f}-${arch_f}.apk"

    # Apply aapt2 optimization if enabled and architecture is arm64-v8a
    local apk_to_move="$patched_apk"
    if [ "${ENABLE_AAPT2_OPTIMIZE:-false}" = "true" ] && [ "$arch" = "arm64-v8a" ]; then
        log_info "Applying aapt2 optimization (en, xxhdpi, arm64-v8a only)"
        local optimized_apk="${patched_apk%.apk}-optimized.apk"
        if [ -f "scripts/aapt2-optimize.sh" ]; then
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
