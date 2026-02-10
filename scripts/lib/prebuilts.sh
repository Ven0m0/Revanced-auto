#!/usr/bin/env bash
set -euo pipefail
# ReVanced prebuilts management
# Fixed syntax error in loop structure

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
  local ext grab_cl

  if [[ "$tag" = "CLI" ]]; then
    ext="jar"
    grab_cl=false
  elif [[ "$tag" = "Patches" ]]; then
    ext="rvp"
    grab_cl=true
  else
    abort "unreachable: invalid tag $tag"
  fi

  local rv_rel="https://api.github.com/repos/${src}/releases" name_ver

  # Handle version selection
  if [[ "$ver" = "dev" ]]; then
    log_info "Fetching dev version for $tag"
    local resp
    resp=$(gh_req "$rv_rel" -) || return 1
    ver=$(jq -e -r '.[] | .tag_name' <<< "$resp" | get_highest_ver) || return 1
    log_debug "Selected dev version: $ver"
  fi

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

  # Check if file already exists locally
  local url file tag_name name
file=$(find "$dir" -name "${fprefix}-${name_ver#v}*.${ext}" -type f 2> /dev/null)

  if [[ "$file" = "" ]]; then
    log_info "Downloading $tag from GitHub"
    local resp asset
    resp=$(gh_req "$rv_rel" -) || return 1
    tag_name=$(jq -r '.tag_name' <<< "$resp")
    asset=$(jq -e -r "first(.assets[] | select(.name | endswith(\".$ext\")))" <<< "$resp") || return 1
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

    if [[ "$file" = "" ]]; then
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

# Get ReVanced CLI and patches
# Args:
#   $1: CLI source (e.g., "j-hc/revanced-cli")
#   $2: CLI version
#   $3: Patches source (e.g., "ReVanced/revanced-patches")
#   $4: Patches version
# Returns:
#   Paths to CLI JAR and patches file
get_rv_prebuilts() {
  local cli_src=$1 cli_ver=$2 patches_src=$3 patches_ver=$4
  pr "Getting prebuilts (${patches_src%/*})" >&2

  local cl_dir=${patches_src%/*}
  cl_dir=${TEMP_DIR}/${cl_dir,,}-rv
  [ -d "$cl_dir" ] || mkdir -p "$cl_dir"

  local files=()

  files+=("$(resolve_rv_artifact "$cli_src" "CLI" "$cli_ver" "revanced-cli" "$cl_dir")")
  files+=("$(resolve_rv_artifact "$patches_src" "Patches" "$patches_ver" "patches" "$cl_dir")")

  echo "${files[@]}"
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
  [ -d "$cl_dir" ] || mkdir -p "$cl_dir"

  # Download CLI once (shared across all patch sources)
  local cli_jar
  cli_jar=$(resolve_rv_artifact "$cli_src" "CLI" "$cli_ver" "revanced-cli" "$cl_dir")
  echo "$cli_jar"

  # Download patches from each source
  local idx=1
  for patches_src in "${patches_srcs[@]}"; do
    log_info "Downloading patches from ${patches_src} (${idx}/${#patches_srcs[@]})"

    pr "Getting prebuilts (${patches_src%/*})" >&2

    # Recalculate cl_dir for this patch source
    cl_dir=${patches_src%/*}
    cl_dir=${TEMP_DIR}/${cl_dir,,}-rv
    [ -d "$cl_dir" ] || mkdir -p "$cl_dir"

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
    zip -0rq "${CWD}/${file}" . || return 1
  ) >&2

  local ret=$?
  rm -rf "${file}-zip" 2> /dev/null || :
  return "$ret"
}
# Force CI update 1770206204
