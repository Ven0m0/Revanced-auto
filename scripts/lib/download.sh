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
	sed -n 's;.*id=\(.*\)" class="accent_color.*;\1;p' <<<"$__APKMIRROR_RESP__"
}

# Get available versions from APKMirror
get_apkmirror_vers() {
	local vers apkm_resp
	apkm_resp=$(req "https://www.apkmirror.com/uploads/?appcategory=${__APKMIRROR_CAT__}" -)
	vers=$(sed -n 's;.*Version:</span><span class="infoSlide-value">\(.*\) </span>.*;\1;p' <<<"$apkm_resp" | awk '{$1=$1}1')

	if [[ "$__AAV__" = false ]]; then
		local IFS=$'\n'
		vers=$(grep -iv "\(beta\|alpha\)" <<<"$vers")
		local v r_vers=()
		for v in "${vers[@]}"; do
			grep -iq "${v} \(beta\|alpha\)" <<<"$apkm_resp" || r_vers+=("$v")
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
	local apparch dlurl app_table

	if [[ "$arch" = all ]]; then
		apparch=(universal noarch 'arm64-v8a + armeabi-v7a')
	else
		apparch=("$arch" universal noarch 'arm64-v8a + armeabi-v7a')
	fi

	# Use Python to properly parse HTML and handle rows with varying field counts
	# This approach correctly handles rows with 7+ fields by processing entire row elements
	dlurl=$(echo "$resp" | python3 -c '
import sys
from lxml import html

bundle = sys.argv[1]
dpi = sys.argv[2]
arch = sys.argv[3]

try:
    tree = html.fromstring(sys.stdin.read())
    rows = tree.cssselect("div.table-row.headerFont")
    for row in rows:
        texts = [el.text_content().strip() for el in row.cssselect("span")]
        # Rows have 7+ fields; only process the first 7 for matching
        if len(texts) >= 7 and texts[2] == bundle and texts[5] == dpi and texts[3] in [arch, "universal", "noarch", "arm64-v8a + armeabi-v7a"]:
            link = row.cssselect("div a")[0]
            url = link.get("href")
            if not url.startswith("http"):
                url = "https://www.apkmirror.com" + url
            print(url)
            sys.exit(0)
except Exception:
    sys.exit(1)
' "$bundle" "$dpi" "$arch" 2>/dev/null)

	if [[ -n "$dlurl" ]]; then
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
		apkmname=$(scrape_text "h1.marginZero" <<<"$__APKMIRROR_RESP__")
		apkmname="${apkmname,,}"
		apkmname="${apkmname// /-}"
		apkmname="${apkmname//[^a-z0-9-]/}"
		url="${url}/${apkmname}-${version//./-}-release/"

		log_info "Searching APKMirror release page: $url"
		resp=$(req "$url" -) || return 1

		# Check if variants table exists
		if scrape_text "div.table-row.headerFont" <<<"$resp" >/dev/null 2>&1; then
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
	scrape_text "tr.full:nth-child(1) > td:nth-child(3)" <<<"$__UPTODOWN_RESP_PKG__"
}

# Get available versions from Uptodown
get_uptodown_vers() {
	scrape_text ".version" <<<"$__UPTODOWN_RESP__"
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
	data_code=$(scrape_attr "#detail-app-name" data-code <<<"$__UPTODOWN_RESP__")
	local versionURL="" is_bundle=false

	log_info "Searching Uptodown for version: $version"

	# Optimization: Cache version list responses to avoid repeated polling (TTL: 1 hour)
	# This saves 2-8 seconds per download when cache hits
	local cache_key="uptodown_versions_$(echo "$data_code" | tr -d './\\')"
	local cache_file="${TEMP_DIR}/.cache_${cache_key}.json"
	local cache_lock="${cache_file}.lock"
	local cache_ttl=3600  # 1 hour

	# Try cache first with file locking to prevent race conditions
	local all_versions=""
	{
		# Use flock to ensure atomic cache operations (prevent concurrent access)
		flock -x 200

		if [[ -f "$cache_file" ]]; then
			local cache_age cache_mtime now
			now=$(date +%s)
			cache_mtime=$(stat -c%Y "$cache_file" 2>/dev/null || stat -f%m "$cache_file" 2>/dev/null || echo "")
			if [[ -n "$cache_mtime" ]]; then
				cache_age=$((now - cache_mtime))
				if [[ $cache_age -lt $cache_ttl ]]; then
					all_versions=$(cat "$cache_file")
					log_debug "Using cached Uptodown version list (age: ${cache_age}s)"
				fi
			else
				log_debug "Could not determine cache file mtime; treating as cache miss"
			fi
		fi

		# If no cache, fetch and combine all pages
		if [[ -z "$all_versions" ]]; then
			log_debug "Fetching Uptodown version pages (no cache)"
			local -a page_responses=()
			for i in {1..5}; do
				local page_resp
				page_resp=$(req "${uptodown_dlurl}/apps/${data_code}/versions/${i}" -)
				if [[ -n "$page_resp" && "$page_resp" != "null" ]]; then
					page_responses+=("$page_resp")
				fi
			done

			# Combine all pages into one JSON array
			if [[ ${#page_responses[@]} -gt 0 ]]; then
				all_versions=$(printf '%s\n' "${page_responses[@]}" | jq -s '[.[].data[]?] | unique_by(.version)')
				# Cache the combined result atomically to avoid partial writes
				local tmp_cache_file="${cache_file}.$$.$RANDOM.tmp"
				printf '%s\n' "$all_versions" > "$tmp_cache_file"
				mv -f "$tmp_cache_file" "$cache_file"
				log_debug "Cached ${#page_responses[@]} Uptodown version pages"
			fi
		fi
	} 200>"$cache_lock"

	# Search in cached/combined version list
	if [[ -n "$all_versions" && "$all_versions" != "null" ]]; then
		if op=$(jq -e -r "map(select(.version == \"${version}\")) | .[0]" <<<"$all_versions" 2>/dev/null); then
			if [[ "$(jq -e -r ".kindFile" <<<"$op")" = "xapk" ]]; then
				is_bundle=true
			fi

			if versionURL=$(jq -e -r '.versionURL' <<<"$op" 2>/dev/null); then
				log_debug "Found version in Uptodown cache/data"
			else
				return 1
			fi
		else
			log_warn "Version $version not found in Uptodown version list"
			return 1
		fi
	else
		log_warn "Failed to fetch Uptodown version list"
		return 1
	fi

	if [[ "$versionURL" = "" ]]; then
		log_warn "Version not found on Uptodown: $version"
		return 1
	fi

	resp=$(req "$versionURL" -) || return 1

	local data_version files node_arch data_file_id
	data_version=$(scrape_attr '.button.variants' data-version <<<"$resp") || return 1

	if [[ "$data_version" ]]; then
		files=$(req "${uptodown_dlurl%/*}/app/${data_code}/version/${data_version}/files" - | jq -e -r .content) || return 1

		for ((n = 1; n < 12; n += 2)); do
			node_arch=$(scrape_text ".content > p:nth-child($n)" <<<"$files" | xargs) || return 1
			if [[ "$node_arch" = "" ]]; then return 1; fi
			if ! isoneof "$node_arch" "${apparch[@]}"; then continue; fi

			data_file_id=$(scrape_attr "div.variant:nth-child($((n + 1))) > .v-report" data-file-id <<<"$files") || return 1
			resp=$(req "${uptodown_dlurl}/download/${data_file_id}-x" -)
			break
		done
	fi

	local data_url
	data_url=$(scrape_attr "#detail-download-button" data-url <<<"$resp") || return 1


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
		__ARCHIVE_RESP__=$(sed -n 's;^<a href="\(.*\)"[^"]*;\1;p' <<<"$r")
	fi

	__ARCHIVE_PKG_NAME__=$(awk -F/ '{print $NF}' <<<"$1")
}

# Get package name from Archive.org
get_archive_pkg_name() {
	echo "$__ARCHIVE_PKG_NAME__"
}

# Get available versions from Archive.org
get_archive_vers() {
	sed 's/^[^-]*-//;s/-\(all\|arm64-v8a\|arm-v7a\)\.apk//g' <<<"$__ARCHIVE_RESP__"
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
	path=$(grep "${version_f#v}-${arch}" <<<"$__ARCHIVE_RESP__") || return 1

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
