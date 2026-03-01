#!/usr/bin/env bash
set -euo pipefail
# ReVanced prebuilts management

# Default aapt2 binary source repository
readonly AAPT2_SOURCE_DEFAULT="Graywizard888/Custom-Enhancify-aapt2-binary"
readonly AAPT2_CACHE_TTL=604800 # 7 days

# Map uname -m to aapt2 release asset name
_get_aapt2_asset_name() {
  local machine_arch
  machine_arch=$(uname -m)
  case "$machine_arch" in
    aarch64 | arm64) echo "aapt2-arm64-v8a" ;;
    armv7* | armv8l) echo "aapt2-armeabi-v7a" ;;
    x86_64) echo "aapt2-arm64-v8a" ;;
    *) echo "" ;;
  esac
}

# Fetch the latest aapt2 binary from a GitHub releases repo
# Args:
#   $1: GitHub repo (owner/name), defaults to AAPT2_SOURCE_DEFAULT
# Returns:
#   Path to the downloaded aapt2 binary via stdout
# Uses caching to avoid redundant downloads (7-day TTL)
fetch_aapt2_binary() {
  local aapt2_repo="${1:-$AAPT2_SOURCE_DEFAULT}"
  local asset_name
  asset_name=$(_get_aapt2_asset_name)

  if [[ -z "$asset_name" ]]; then
    log_warn "No aapt2 binary available for architecture: $(uname -m)"
    return 1
  fi

  local cache_dir="${TEMP_DIR}/aapt2-cache"
  mkdir -p "$cache_dir"

  local cached_binary="${cache_dir}/${asset_name}"
  local cache_path
  cache_path=$(get_cache_path "aapt2-${asset_name}" "aapt2")

  # Check cache first
  if [[ -f "$cached_binary" ]] && [[ -x "$cached_binary" ]]; then
    local cache_meta="${cache_dir}/${asset_name}.meta"
    if [[ -f "$cache_meta" ]]; then
      local cached_at
      read -r cached_at < "$cache_meta"
      local now
      now=$(date +%s)
      if (( (now - cached_at) < AAPT2_CACHE_TTL )); then
        log_debug "Using cached aapt2 binary: $cached_binary"
        echo "$cached_binary"
        return 0
      fi
    fi
  fi

  log_info "Fetching latest aapt2 binary from ${aapt2_repo}..."

  local api_url="https://api.github.com/repos/${aapt2_repo}/releases/latest"
  local release_json
  if ! release_json=$(gh_req "$api_url" -); then
    log_warn "Failed to fetch aapt2 release info from ${aapt2_repo}"
    # Return cached binary if available even if expired
    if [[ -f "$cached_binary" ]] && [[ -x "$cached_binary" ]]; then
      log_warn "Using expired cached aapt2 binary as fallback"
      echo "$cached_binary"
      return 0
    fi
    return 1
  fi

  local download_url tag_name
  download_url=$(jq -r --arg name "$asset_name" \
    '.assets[] | select(.name == $name) | .browser_download_url' <<< "$release_json")
  tag_name=$(jq -r '.tag_name' <<< "$release_json")

  if [[ -z "$download_url" || "$download_url" == "null" ]]; then
    log_warn "Asset '${asset_name}' not found in ${aapt2_repo} ${tag_name}"
    if [[ -f "$cached_binary" ]] && [[ -x "$cached_binary" ]]; then
      log_warn "Using expired cached aapt2 binary as fallback"
      echo "$cached_binary"
      return 0
    fi
    return 1
  fi

  log_info "Downloading aapt2 ${tag_name} (${asset_name})..."
  local asset_url
  asset_url=$(jq -r --arg name "$asset_name" \
    '.assets[] | select(.name == $name) | .url' <<< "$release_json")

  if ! gh_dl "$cached_binary" "$asset_url"; then
    log_warn "Failed to download aapt2 binary"
    if [[ -f "$cached_binary" ]] && [[ -x "$cached_binary" ]]; then
      log_warn "Using expired cached aapt2 binary as fallback"
      echo "$cached_binary"
      return 0
    fi
    return 1
  fi

  chmod +x "$cached_binary"

  # Update cache timestamp
  date +%s > "${cache_dir}/${asset_name}.meta"

  pr "Downloaded aapt2 ${tag_name} for $(uname -m)"
  echo "$cached_binary"
  return 0
}

# Resolve a single ReVanced artifact (CLI or Patches)
# Args:
#   $1: Source (e.g., "j-hc/revanced-cli")
#   $2: Tag ("CLI" or "Patches")
#   $3: Version
#   $4: File prefix ("revanced-cli" or "patches")
#   $5: Changelog directory
# Returns:
#   Path to artifact file
resolve_rv_artifact() {
  local src=$1 tag=$2 ver=$3 fprefix=$4 cl_dir=$5
  local ext grab_cl dir
  dir="$cl_dir"
  if [[ "$tag" = "CLI" ]]; then
    ext="jar"
    grab_cl=false
  elif [[ "$tag" = "Patches" ]]; then
    ext="rvp"
    grab_cl=true
  else
    abort "unreachable: invalid tag $tag"
  fi
  # Morphe-style sources use .mpp patch format
  local is_morphe=false
  if [[ "$tag" = "Patches" ]]; then
    case "$src" in
      MorpheApp/* | */morphe-* | */rvx-morphed | */anddea-rvx-morphed | */patcheddit)
        ext="mpp"
        is_morphe=true
        ;;
    esac
  fi
  local rv_rel="https://api.github.com/repos/${src}/releases" name_ver
  # Handle version selection
  if [[ "$ver" = "dev" ]]; then
    log_info "Fetching dev version for $tag"
    # Initialize cache if needed
    if [[ -z "${RV_DEV_VER_CACHE+x}" ]]; then
      declare -gA RV_DEV_VER_CACHE
    fi
    if [[ -n "${RV_DEV_VER_CACHE[$rv_rel]-}" ]]; then
      ver="${RV_DEV_VER_CACHE[$rv_rel]}"
      log_debug "Using cached dev version: $ver"
    else
      local resp
      resp=$(gh_req "$rv_rel" -) || return 1
      ver=$(jq -e -r '.[] | .tag_name' <<< "$resp" | get_highest_ver) || return 1
      RV_DEV_VER_CACHE[$rv_rel]="$ver"
      log_debug "Selected dev version: $ver"
    fi
  fi
  # Check if file already exists locally (try both .mpp and .rvp for patches)
  local url file tag_name name
  file=$(find "$dir" -name "${fprefix}-${ver#v}*.${ext}" -type f 2> /dev/null || find "$dir" -name "${fprefix}-*.${ext}" -type f 2> /dev/null)
  # For Morphe sources, also try the alternate extension if primary not found
  if [[ -z "$file" && "$tag" = "Patches" ]]; then
    local alt_ext
    if [[ "$is_morphe" == "true" ]]; then alt_ext="rvp"; else alt_ext="mpp"; fi
    file=$(find "$dir" -name "${fprefix}-${ver#v}*.${alt_ext}" -type f 2> /dev/null || find "$dir" -name "${fprefix}-*.${alt_ext}" -type f 2> /dev/null)
  fi
  if [[ -z "$file" ]]; then
    log_info "Downloading $tag from GitHub"
    local resp asset
    resp=$(gh_req "$rv_rel" -) || return 1
    tag_name=$(jq -r ".[0].tag_name" <<< "$resp")
    asset=$(jq -e -r "first(.[0].assets[] | select(.name | endswith(\".$ext\")))" <<< "$resp" 2>/dev/null) || true
    # Fallback: if .mpp not found, try .rvp (and vice versa)
    if [[ -z "${asset:-}" || "${asset:-}" == "null" ]]; then
      if [[ "$is_morphe" == "true" ]]; then
        log_debug "No .mpp asset found, trying .rvp fallback"
        asset=$(jq -e -r 'first(.[0].assets[] | select(.name | endswith(".rvp")))' <<< "$resp") || return 1
      else
        log_debug "No .rvp asset found, trying .mpp fallback"
        asset=$(jq -e -r 'first(.[0].assets[] | select(.name | endswith(".mpp")))' <<< "$resp") || return 1
      fi
    fi
    url=$(jq -r .url <<< "$asset")
    name=$(basename "$(jq -r .name <<< "$asset")")
    file="${dir}/${name}"
    gh_dl "$file" "$url" >&2 || return 1
    echo "$tag: $(cut -d/ -f1 <<< "$src")/${name}  " >> "${cl_dir}/changelog.md"
  else
    grab_cl=false
    local for_err=$file
    if [[ "$ver" = "latest" ]]; then
      file=$(grep -v '/[^/]*dev[^/]*$' <<< "$file" | head -1)
    else
      file=$(grep "/[^/]*${ver#v}[^/]*\$" <<< "$file" | head -1)
    fi
    if [[ -z "$file" ]]; then
      abort "filter fail: '$for_err' with '$ver'"
    fi
    name=$(basename "$file")
    tag_name=$(cut -d'-' -f3- <<< "$name")
    tag_name=v${tag_name%.*}
    log_debug "Using cached $tag: $file"
  fi
  # Handle patches-specific processing
  if [[ "$tag" = "Patches" ]]; then
    if [[ "$grab_cl" = true ]]; then
      printf "[Changelog](https://github.com/%s/releases/tag/%s)\n\n" "$src" "$tag_name" >> "${cl_dir}/changelog.md"
    fi
    # Remove integrations checks if requested
    if [[ "${REMOVE_RV_INTEGRATIONS_CHECKS:-}" = true ]]; then
      if ! _remove_integrations_checks "$file"; then
        log_warn "Patching revanced-integrations failed"
      fi
    fi
  fi
  echo "$file"
}
# Get ReVanced CLI and patches from multiple sources
# Args:
#   $1: CLI source (e.g., "j-hc/revanced-cli")
#   $2: CLI version
#   $3+: Patches sources (e.g., "ReVanced/revanced-patches" "anddea/revanced-patches")
# Environment:
#   PATCHES_VER: Patches version (used for all sources)
# Returns:
#   Newline-separated paths: CLI JAR on first line, then patches files
# Note:
#   Output format:
#     /path/to/cli.jar
#     /path/to/patches1.rvp
#     /path/to/patches2.rvp
get_rv_prebuilts_multi() {
  local cli_src=$1 cli_ver=$2
  shift 2
  local -a patches_srcs=("$@")
  if [[ ${#patches_srcs[@]} -eq 0 ]]; then
    abort "get_rv_prebuilts_multi: no patch sources provided"
  fi
  log_debug "Downloading prebuilts for ${#patches_srcs[@]} patch source(s)"
  # Use first patch source to determine cache directory for CLI logging
  local first_patches_src=${patches_srcs[0]}
  local cl_dir=${first_patches_src%/*}
  cl_dir=${TEMP_DIR}/${cl_dir,,}-rv
  [[ -d "$cl_dir" ]] || mkdir -p "$cl_dir"
  # Download CLI once (shared across all patch sources)
  # Morphe CLI uses "morphe-cli" prefix instead of "revanced-cli"
  local cli_prefix="revanced-cli"
  case "$cli_src" in
    MorpheApp/* | */morphe-cli) cli_prefix="morphe-cli" ;;
  esac
  local cli_jar
  cli_jar=$(resolve_rv_artifact "$cli_src" "CLI" "$cli_ver" "$cli_prefix" "$cl_dir")
  echo "$cli_jar"
  # Download patches from each source
  local idx=1
  for patches_src in "${patches_srcs[@]}"; do
    log_info "Downloading patches from ${patches_src} (${idx}/${#patches_srcs[@]})"
    pr "Getting prebuilts (${patches_src%/*})" >&2
    # Recalculate cl_dir for this patch source
    cl_dir=${patches_src%/*}
    cl_dir=${TEMP_DIR}/${cl_dir,,}-rv
    [[ -d "$cl_dir" ]] || mkdir -p "$cl_dir"
    local patches_jar
    patches_jar=$(resolve_rv_artifact "$patches_src" "Patches" "$PATCHES_VER" "patches" "$cl_dir")
    echo "$patches_jar"
    idx=$((idx + 1))
  done
  log_debug "Downloaded CLI and ${#patches_srcs[@]} patch bundle(s)"
}
# Remove integrations checks from patches
# Args:
#   $1: Patches file path
# Returns:
#   0 on success, 1 on failure
_remove_integrations_checks() {
  local file=$1
  log_info "Removing integrations checks from patches"
  (
    mkdir -p "${file}-zip" || return 1
    unzip -qo "$file" -d "${file}-zip" || return 1
    java -cp "${BIN_DIR}/paccer.jar:${BIN_DIR}/dexlib2.jar" com.jhc.Main \
      "${file}-zip/extensions/shared.rve" \
      "${file}-zip/extensions/shared-patched.rve" || return 1
    mv -f "${file}-zip/extensions/shared-patched.rve" \
      "${file}-zip/extensions/shared.rve" || return 1
    rm "$file" || return 1
    cd "${file}-zip" || return 1
    zip -0rq "${PROJECT_ROOT}/$(basename "${file}")" . || return 1
  ) >&2
  local ret=$?
  rm -rf "${file}-zip" 2> /dev/null || :
  return "$ret"
}
