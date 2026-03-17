#!/usr/bin/env bash
set -euo pipefail
# GmsCore (MicroG) download functions

# Get the repository for a GmsCore provider
# Args:
#   $1: Provider name (revanced, morphe, rex)
# Returns:
#   GitHub repository path (owner/repo) via stdout
_get_gmscore_repo() {
  local provider=$1
  case "$provider" in
    revanced) echo "ReVanced/GmsCore" ;;
    morphe) echo "MorpheApp/MicroG-RE" ;;
    rex) echo "YT-Advanced/GmsCore" ;;
    *) abort "Unknown GmsCore provider: $provider" ;;
  esac
}

# Fetch GmsCore from a provider
# Args:
#   $1: Provider name (revanced, morphe, rex)
# Returns:
#   Path to the downloaded APK via stdout
fetch_gmscore() {
  local provider=$1
  local repo
  repo=$(_get_gmscore_repo "$provider")

  log_info "Fetching latest GmsCore from $provider ($repo)..."

  local api_url="https://api.github.com/repos/${repo}/releases/latest"
  local release_json
  if ! release_json=$(gh_req "$api_url" -); then
    epr "Failed to fetch release info for $provider GmsCore"
    return 1
  fi

  local tag_name
  tag_name=$(jq -r '.tag_name' <<< "$release_json")

  local asset_info
  asset_info=$(jq -r '
    .assets[]
    | select(.name | endswith(".apk"))
    | [.browser_download_url, .name]
    | @tsv
  ' <<< "$release_json" | head -n1)

  if [[ -z "$asset_info" ]]; then
    epr "No APK assets found for $provider GmsCore"
    return 1
  fi

  local url name
  IFS=$'\t' read -r url name <<< "$asset_info"

  local output_dir="${BUILD_DIR}/GmsCore"
  mkdir -p "$output_dir"

  local output_file="${output_dir}/${provider}-${tag_name}-${name}"

  if ! gh_dl "$output_file" "$url"; then
    epr "Failed to download GmsCore from $provider"
    return 1
  fi

  pr "Downloaded $provider GmsCore $tag_name"
  echo "$output_file"
}
