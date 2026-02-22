#!/usr/bin/env bash
set -euo pipefail
# APK download functions for multiple sources
# Global variables for caching responses
__APKMIRROR_RESP__=""
__APKMIRROR_CAT__=""
__UPTODOWN_RESP__=""
__UPTODOWN_RESP_PKG__=""
__ARCHIVE_RESP__=""
__ARCHIVE_PKG_NAME__=""
__AAV__="false" # Allow Alpha/Beta Versions
# ==================== APKMirror ====================
# Get APKMirror page response
# Args:
#   $1: APKMirror URL
get_apkmirror_resp() {
  log_info "Fetching APKMirror page: $1"
  __APKMIRROR_RESP__=$(req "${1}" -)
  __APKMIRROR_CAT__="${1##*/}"
}
# Get package name from APKMirror
get_apkmirror_pkg_name() {
  sed -n 's;.*id=\(.*\)" class="accent_color.*;\1;p' <<< "$__APKMIRROR_RESP__"
}
# Get available versions from APKMirror
get_apkmirror_vers() {
  local vers apkm_resp
  apkm_resp=$(req "https://www.apkmirror.com/uploads/?appcategory=${__APKMIRROR_CAT__}" -)
  vers=$(sed -n 's;.*Version:</span><span class="infoSlide-value">\(.*\) </span>.*;\1;p' <<< "$apkm_resp" | awk '{$1=$1}1')
  if [[ "$__AAV__" = false ]]; then
    vers=$(grep -iv "\(beta\|alpha\)" <<< "$vers")
    if [[ -n "$vers" ]]; then
      local pattern bad_vers
      # Escape dots in versions for regex safety
      pattern=$(printf "%s" "$vers" | sed 's/\./\\./g' | tr '\n' '|')
      pattern="${pattern%|}"
      # Find versions that are followed by beta/alpha in HTML
      bad_vers=$(grep -Eoi "(${pattern})[[:space:]]+(beta|alpha)" <<< "$apkm_resp" | awk '{print tolower($1)}' | sort -u)
      if [[ -n "$bad_vers" ]]; then
        vers=$(grep -vxFf <(echo "$bad_vers") <<< "$vers" || true)
      fi
    fi
    echo "$vers"
  else
    echo "$vers"
  fi
}
# Search for specific APK variant in APKMirror page
# Args:
#   $1: Response HTML
#   $2: DPI
#   $3: Architecture
#   $4: APK bundle type
# Returns:
#   Download URL
apk_mirror_search() {
  local resp="$1" dpi="$2" arch="$3" apk_bundle="$4"
  # Delegate to Python script for efficient parsing
  uv run "${PROJECT_ROOT}/scripts/apkmirror_search.py" \
    --apk-bundle "$apk_bundle" \
    --dpi "$dpi" \
    --arch "$arch" \
    <<< "$resp"
}
# Download APK from APKMirror
# Args:
#   $1: Base URL
#   $2: Version
#   $3: Output file path
#   $4: Architecture
#   $5: DPI
dl_apkmirror() {
  local url=$1 version=${2// /-} output=$3 arch=$4 dpi=$5 is_bundle=false
  if [[ -f "${output}.apkm" ]]; then
    is_bundle=true
  else
    # Normalize architecture name
    arch=$(normalize_arch "$arch")
    local resp node apkmname dlurl=""
    apkmname=$(scrape_text "h1.marginZero" <<< "$__APKMIRROR_RESP__")
    apkmname="${apkmname,,}"
    apkmname="${apkmname// /-}"
    apkmname="${apkmname//[^a-z0-9-]/}"
    url="${url}/${apkmname}-${version//./-}-release/"
    log_info "Searching APKMirror release page: $url"
    resp=$(req "$url" -) || return 1
    local ret
    # Try APK first
    if dlurl=$(apk_mirror_search "$resp" "$dpi" "$arch" "APK"); then
      # Found APK, follow link
      resp=$(req "$dlurl" -)
    else
      ret=$?
      if [[ $ret -eq 2 ]]; then
        # No variants table found (exit code 2), fall through to legacy/direct scraping
        :
      else
        # Table found but no APK, try BUNDLE
        if dlurl=$(apk_mirror_search "$resp" "$dpi" "$arch" "BUNDLE"); then
          is_bundle=true
          resp=$(req "$dlurl" -)
        else
          # Table exists but no compatible version found
          return 1
        fi
      fi
    fi
    url=$(echo "$resp" | scrape_attr "a.btn" href) || return 1
    url=$(req "$url" - | scrape_attr "span > a[rel = nofollow]" href) || return 1
  fi
  if [[ "$is_bundle" = true ]]; then
    log_info "Downloading APK bundle from APKMirror"
    req "$url" "${output}.apkm" || return 1
    merge_splits "${output}.apkm" "$output"
  else
    log_info "Downloading APK from APKMirror"
    req "$url" "$output" || return 1
  fi
}
# ==================== Uptodown ====================
# Get Uptodown page response
# Args:
#   $1: Uptodown URL
get_uptodown_resp() {
  log_info "Fetching Uptodown page: $1"
  __UPTODOWN_RESP__=$(req "${1}/versions" -)
  __UPTODOWN_RESP_PKG__=$(req "${1}/download" -)
}
# Get package name from Uptodown
get_uptodown_pkg_name() {
  local pkg_name
  pkg_name=$(scrape_text "tr.full:nth-child(1) > td:nth-child(3)" <<< "$__UPTODOWN_RESP_PKG__")

  if [[ ! "$pkg_name" =~ ^[a-zA-Z0-9._]+$ ]]; then
    epr "Invalid package name from Uptodown: $pkg_name"
    return 1
  fi
  echo "$pkg_name"
}
# Get available versions from Uptodown
get_uptodown_vers() {
  scrape_text ".version" <<< "$__UPTODOWN_RESP__"
}
# Download APK from Uptodown
# Args:
#   $1: Base URL
#   $2: Version
#   $3: Output file path
#   $4: Architecture
#   $5: DPI (unused)
# Helper function to search for version on Uptodown
# Args:
#   $1: Uptodown URL
#   $2: Data code
#   $3: Version
# Returns:
#   JSON object of the version to stdout, or exit 1 if not found
_uptodown_search_version() {
  local uptodown_dlurl=$1 data_code=$2 version=$3
  local temp_dir resp op

  temp_dir=$(mktemp -d)
  trap 'rm -rf -- "$temp_dir"' RETURN

  # Speculative fetch: Try page 1 first
  (
    local parent_cookie_file="${TEMP_DIR:-}/cookie.txt"
    TEMP_DIR=$(mktemp -d)
    if [[ -f "$parent_cookie_file" ]]; then
      cp "$parent_cookie_file" "${TEMP_DIR}/cookie.txt"
    fi
    if ! req "${uptodown_dlurl}/apps/${data_code}/versions/1" - > "${temp_dir}/1"; then
      rm -f "${temp_dir}/1"
    fi
    rm -rf "$TEMP_DIR" || true
  )

  # Check page 1
  if [[ -f "${temp_dir}/1" ]]; then
    resp=$(cat "${temp_dir}/1")
    if [[ -n "$resp" ]]; then
      if op=$(jq -e -r --arg ver "$version" '.data | map(select(.version == $ver)) | .[0]' <<< "$resp"); then
        if jq -e -r '.versionURL' <<< "$op" >/dev/null; then
           echo "$op"
           return 0
        fi
      fi
    fi
  fi

  # Search pages 2-5
  log_info "Version not found on page 1, searching pages 2-5..."
  local pids=()
  for i in {2..5}; do
    (
        local parent_cookie_file="${TEMP_DIR:-}/cookie.txt"
        TEMP_DIR=$(mktemp -d)
        if [[ -f "$parent_cookie_file" ]]; then
          cp "$parent_cookie_file" "${TEMP_DIR}/cookie.txt"
        fi
        if ! req "${uptodown_dlurl}/apps/${data_code}/versions/${i}" - > "${temp_dir}/${i}"; then
          rm -f "${temp_dir}/${i}"
        fi
        rm -rf "$TEMP_DIR" || true
    ) &
    pids+=($!)
  done

  for pid in "${pids[@]}"; do
    wait "$pid" || true
  done

  for i in {2..5}; do
    if [[ -f "${temp_dir}/${i}" ]]; then
      resp=$(cat "${temp_dir}/${i}")
      if [[ -z "$resp" ]]; then continue; fi
      if op=$(jq -e -r --arg ver "$version" '.data | map(select(.version == $ver)) | .[0]' <<< "$resp"); then
         if jq -e -r '.versionURL' <<< "$op" >/dev/null; then
           echo "$op"
           return 0
         fi
      fi
    fi
  done

  return 1
}

dl_uptodown() {
  local uptodown_dlurl=$1 version=$2 output=$3 arch=$4 _dpi=$5
  local apparch
  # Normalize architecture name
  arch=$(normalize_arch "$arch")
  if [[ "$arch" = all ]]; then
    apparch=('arm64-v8a, armeabi-v7a, x86, x86_64' 'arm64-v8a, armeabi-v7a')
  else
    apparch=("$arch" 'arm64-v8a, armeabi-v7a, x86, x86_64' 'arm64-v8a, armeabi-v7a')
  fi
  local op resp data_code
  data_code=$(scrape_attr "#detail-app-name" data-code <<< "$__UPTODOWN_RESP__")
  local versionURL="" is_bundle=false
  log_info "Searching Uptodown for version: $version"
  local version_data
  if version_data=$(_uptodown_search_version "$uptodown_dlurl" "$data_code" "$version"); then
    versionURL=$(jq -r '.versionURL' <<< "$version_data")
    if [[ "$(jq -r '.kindFile' <<< "$version_data")" == "xapk" ]]; then
      is_bundle=true
    fi
  else
    log_warn "Version not found on Uptodown: $version"
    return 1
  fi
  resp=$(req "$versionURL" -) || return 1
  local data_version files data_file_id
  data_version=$(scrape_attr '.button.variants' data-version <<< "$resp") || return 1
  if [[ "$data_version" ]]; then
    files=$(req "${uptodown_dlurl%/*}/app/${data_code}/version/${data_version}/files" - | jq -e -r .content) || return 1
    if data_file_id=$(uv run "${PROJECT_ROOT}/scripts/uptodown_search.py" "${apparch[@]}" <<< "$files"); then
      resp=$(req "${uptodown_dlurl}/download/${data_file_id}-x" -)
    fi
  fi
  local data_url
  data_url=$(scrape_attr "#detail-download-button" data-url <<< "$resp") || return 1
  if [[ "$is_bundle" = true ]]; then
    log_info "Downloading APK bundle from Uptodown"
    req "https://dw.uptodown.com/dwn/${data_url}" "$output.apkm" || return 1
    merge_splits "${output}.apkm" "$output"
  else
    log_info "Downloading APK from Uptodown"
    req "https://dw.uptodown.com/dwn/${data_url}" "$output"
  fi
}
# ==================== Archive.org ====================
# Get Archive.org page response
# Args:
#   $1: Archive.org URL
get_archive_resp() {
  log_info "Fetching Archive.org page: $1"
  local r
  r=$(req "$1" -)
  if [[ "$r" = "" ]]; then
    return 1
  else
    __ARCHIVE_RESP__=$(sed -n 's;^<a href="\(.*\)"[^"]*;\1;p' <<< "$r")
  fi
  local pkg_name="${1##*/}"
  if [[ ! "$pkg_name" =~ ^[a-zA-Z0-9._-]+$ ]]; then
    epr "Invalid package name from Archive.org URL: $pkg_name"
    return 1
  fi
  if [[ "$pkg_name" == *".."* ]]; then
    epr "Invalid package name from Archive.org URL (contains ..): $pkg_name"
    return 1
  fi
  __ARCHIVE_PKG_NAME__="$pkg_name"
}
# Get package name from Archive.org
get_archive_pkg_name() {
  echo "$__ARCHIVE_PKG_NAME__"
}
# Get available versions from Archive.org
get_archive_vers() {
  sed 's/^[^-]*-//;s/-\(all\|arm64-v8a\|arm-v7a\)\.apk//g' <<< "$__ARCHIVE_RESP__"
}
# Download APK from Archive.org
# Args:
#   $1: Base URL
#   $2: Version
#   $3: Output file path
#   $4: Architecture
dl_archive() {
  local url=$1 version=$2 output=$3 arch=$4
  local path version_f="${version// /}"
  log_info "Searching Archive.org for version: $version_f"
  path=$(grep "${version_f#v}-${arch}" <<< "$__ARCHIVE_RESP__") || return 1
  # Validate path to prevent path traversal attacks
  if [[ ! "$path" =~ ^[a-zA-Z0-9._/-]+$ ]]; then
    epr "Invalid path from Archive.org (contains unsafe characters): $path"
    return 1
  fi
  # Ensure path doesn't contain directory traversal sequences
  if [[ "$path" == *".."* ]]; then
    epr "Invalid path from Archive.org (contains ..): $path"
    return 1
  fi
  log_info "Downloading APK from Archive.org"
  req "${url}/${path}" "$output"
}
