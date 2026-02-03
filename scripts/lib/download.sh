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
    local IFS=$'\n'
    vers=$(grep -iv "\(beta\|alpha\)" <<< "$vers")
    local v r_vers=()
    for v in "${vers[@]}"; do
      grep -iq "${v} \(beta\|alpha\)" <<< "$apkm_resp" || r_vers+=("$v")
    done
    echo "${r_vers[*]}"
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
  local dlurl

  # Process with Python script to avoid N+1 process spawning
  if dlurl=$(python3 "${CWD}/scripts/apkmirror_search.py" \
    --apk-bundle "$apk_bundle" \
    --dpi "$dpi" \
    --arch "$arch" <<< "$resp"); then
    echo "$dlurl"
    return 0
  fi

  return 1
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
    node=$("$HTMLQ" "div.table-row.headerFont:nth-last-child(1)" -r "span:nth-child(n+3)" <<< "$resp")

    if [[ "$node" ]]; then
      if ! dlurl=$(apk_mirror_search "$resp" "$dpi" "$arch" "APK"); then
        if ! dlurl=$(apk_mirror_search "$resp" "$dpi" "$arch" "BUNDLE"); then
          return 1
        else
          is_bundle=true
        fi
      fi
      [ "$dlurl" = "" ] && return 1
      resp=$(req "$dlurl" -)
    fi

    url=$(echo "$resp" | scrape_attr "a.btn" href --base https://www.apkmirror.com) || return 1
    url=$(req "$url" - | scrape_attr "span > a[rel = nofollow]" href --base https://www.apkmirror.com) || return 1
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
  scrape_text "tr.full:nth-child(1) > td:nth-child(3)" <<< "$__UPTODOWN_RESP_PKG__"
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
  local temp_dir
  temp_dir=$(mktemp -d)
  trap 'rm -rf -- "$temp_dir"' RETURN
  local pids=()

  for i in {1..5}; do
    (
      # Create isolated temp dir for cookies to avoid race conditions
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

  local failed_jobs=0
  local total_jobs=${#pids[@]}

  for pid in "${pids[@]}"; do
    if ! wait "$pid"; then
      failed_jobs=$((failed_jobs + 1))
    fi
  done

  if (( failed_jobs == total_jobs )); then
    log_warn "All Uptodown download attempts failed for version: $version"
  fi
  for i in {1..5}; do
    if [[ -f "${temp_dir}/${i}" ]]; then
      resp=$(cat "${temp_dir}/${i}")
      if [[ -z "$resp" ]]; then continue; fi

      if ! op=$(jq -e -r --arg ver "$version" '.data | map(select(.version == $ver)) | .[0]' <<< "$resp"); then
        continue
      fi

      if [[ "$(jq -e -r ".kindFile" <<< "$op")" = "xapk" ]]; then
        is_bundle=true
      fi

      if versionURL=$(jq -e -r '.versionURL' <<< "$op"); then
        break
      else
        rm -rf "$temp_dir"
        return 1
      fi
    fi
  done
  rm -rf "$temp_dir"

  if [[ "$versionURL" = "" ]]; then
    log_warn "Version not found on Uptodown: $version"
    return 1
  fi

  resp=$(req "$versionURL" -) || return 1

  local data_version files node_arch data_file_id
  data_version=$(scrape_attr '.button.variants' data-version <<< "$resp") || return 1

  if [[ "$data_version" ]]; then
    files=$(req "${uptodown_dlurl%/*}/app/${data_code}/version/${data_version}/files" - | jq -e -r .content) || return 1

    for ((n = 1; n < 12; n += 2)); do
      node_arch=$(scrape_text ".content > p:nth-child($n)" <<< "$files" | xargs) || return 1
      if [[ "$node_arch" = "" ]]; then return 1; fi
      if ! isoneof "$node_arch" "${apparch[@]}"; then continue; fi

      data_file_id=$(scrape_attr "div.variant:nth-child($((n + 1))) > .v-report" data-file-id <<< "$files") || return 1
      resp=$(req "${uptodown_dlurl}/download/${data_file_id}-x" -)
      break
    done
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

  __ARCHIVE_PKG_NAME__=$(awk -F/ '{print $NF}' <<< "$1")
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
