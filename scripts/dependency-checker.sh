#!/usr/bin/env bash
# Dependency update checker for ReVanced Builder
# Monitors ReVanced CLI, patches, and APK versions for updates
set -euo pipefail

# Determine script and repository root directories
declare -gr SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
declare -gr REPO_ROOT="${PROJECT_ROOT:-${SCRIPT_DIR%/scripts}}"

# Source utilities if available
if [[ -f "utils.sh" ]]; then
  source utils.sh
  # Shim log_error if missing
  if ! command -v log_error &> /dev/null; then
    log_error() { epr "$@" 2>/dev/null || echo "[ERROR] $*" >&2; }
  fi
else
  # Standalone mode - define basic functions
  log_info() { echo "[INFO] $*"; }
  log_success() { echo "[SUCCESS] $*"; }
  log_warn() { echo "[WARN] $*"; }
  log_error() { echo "[ERROR] $*" >&2; }
fi
# Configuration
GITHUB_API="${GITHUB_API_URL:-https://api.github.com}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
CONFIG_FILE="${1:-config.toml}"
CHECK_MODE="${CHECK_MODE:-all}"        # all, cli, patches, apks
OUTPUT_FORMAT="${OUTPUT_FORMAT:-text}" # text, json, markdown
# Make authenticated GitHub API requests
gh_api() {
  local endpoint=$1
  local headers=(-H "Accept: application/vnd.github.v3+json")
  if [[ -n "$GITHUB_TOKEN" ]]; then
    headers+=(-H "Authorization: token $GITHUB_TOKEN")
  fi
  if command -v gh_req &> /dev/null; then
    gh_req "$GITHUB_API/$endpoint" "-"
  else
    curl -sSL --fail --connect-timeout 10 --max-time 300 "${headers[@]}" "$GITHUB_API/$endpoint"
  fi
}
# Compare two semantic versions
# Returns: 0 if v1 < v2, 1 if v1 >= v2
version_less_than() {
  local v1=$1 v2=$2
  # Remove 'v' prefix if present
  v1="${v1#v}"
  v2="${v2#v}"
  # Use sort -V for version comparison
  if [[ "$(printf '%s\n%s' "$v1" "$v2" | sort -V | head -1)" == "$v1" && "$v1" != "$v2" ]]; then
    return 0
  else
    return 1
  fi
}
# Get latest release for a GitHub repository
get_latest_release() {
  local repo=$1
  local version_filter=${2:-latest} # latest, dev, or specific version
  log_info "Checking latest release for $repo"
  if [[ "$version_filter" == "latest" ]]; then
    local release
    release=$(gh_api "repos/$repo/releases/latest" 2> /dev/null || echo "{}")
    echo "$release" | jq -r '.tag_name // "unknown"'
  elif [[ "$version_filter" == "dev" ]]; then
    local releases
    releases=$(gh_api "repos/$repo/releases" 2> /dev/null || echo "[]")
    echo "$releases" | jq -r '.[0].tag_name // "unknown"'
  else
    # Specific version - just verify it exists
    local release
    release=$(gh_api "repos/$repo/releases/tags/$version_filter" 2> /dev/null || echo "{}")
    if [[ "$(echo "$release" | jq -r '.tag_name // "unknown"')" != "unknown" ]]; then
      echo "$version_filter"
    else
      echo "unknown"
    fi
  fi
}
# Check CLI updates
check_cli_updates() {
  local cli_source=$1
  local cli_version=$2
  log_info "Checking CLI updates: $cli_source"
  local latest_version
  latest_version=$(get_latest_release "$cli_source" "$cli_version")
  local update_available=false
  local current_normalized="${cli_version#v}"
  local latest_normalized="${latest_version#v}"
  if [[ "$latest_version" != "unknown" ]]; then
    if [[ "$cli_version" == "latest" || "$cli_version" == "dev" ]]; then
      # Always fetch for dev/latest
      update_available=false
      log_info "CLI version: $cli_version (latest: $latest_version)"
    elif version_less_than "$current_normalized" "$latest_normalized"; then
      update_available=true
      log_warn "CLI update available: $cli_version → $latest_version"
    else
      log_success "CLI is up to date: $cli_version"
    fi
  else
    log_error "Could not determine latest CLI version"
  fi
  # Return JSON object
  jq -n \
    --arg source "$cli_source" \
    --arg current "$cli_version" \
    --arg latest "$latest_version" \
    --arg update_available "$update_available" \
    '{
			component: "cli",
			source: $source,
			current_version: $current,
			latest_version: $latest,
			update_available: ($update_available == "true")
		}'
}
# Check patches updates
check_patches_updates() {
  local patches_source=$1
  local patches_version=$2
  log_info "Checking patches updates: $patches_source"
  local latest_version
  latest_version=$(get_latest_release "$patches_source" "$patches_version")
  local update_available=false
  local current_normalized="${patches_version#v}"
  local latest_normalized="${latest_version#v}"
  if [[ "$latest_version" != "unknown" ]]; then
    if [[ "$patches_version" == "latest" || "$patches_version" == "dev" ]]; then
      # Always fetch for dev/latest
      update_available=false
      log_info "Patches version: $patches_version (latest: $latest_version)"
    elif version_less_than "$current_normalized" "$latest_normalized"; then
      update_available=true
      log_warn "Patches update available: $patches_version → $latest_version"
    else
      log_success "Patches are up to date: $patches_version"
    fi
  else
    log_error "Could not determine latest patches version"
  fi
  # Return JSON object
  jq -n \
    --arg source "$patches_source" \
    --arg current "$patches_version" \
    --arg latest "$latest_version" \
    --arg update_available "$update_available" \
    '{
			component: "patches",
			source: $source,
			current_version: $current,
			latest_version: $latest,
			update_available: ($update_available == "true")
		}'
}
# Check APK version updates
check_apk_updates() {
  local app_name=$1
  local current_version=$2
  shift 2
  local urls=("$@")

  log_info "APK version check for $app_name: $current_version"

  local latest_version="unknown"
  local update_available=false

  if command -v get_uptodown_resp &> /dev/null; then
    for url in "${urls[@]}"; do
      if [[ -z "$url" ]]; then continue; fi

      local vers=""
      local provider
      case "$url" in
        *uptodown*)   provider="uptodown" ;;
        *apkmirror*)  provider="apkmirror" ;;
        *apkpure*)    provider="apkpure" ;;
        *archive.org*) provider="archive" ;;
        *aptoide*)    provider="aptoide" ;;
        *apkmonk*)    provider="apkmonk" ;;
        *)            provider="" ;;
      esac

      if [[ -n "$provider" ]]; then
        local get_resp_func="get_${provider}_resp"
        local get_vers_func="get_${provider}_vers"
        if "$get_resp_func" "$url" >/dev/null 2>&1; then
          vers=$("$get_vers_func" 2>/dev/null | head -n 1)
        fi
      fi

      if [[ -n "$vers" && "$vers" != "unknown" ]]; then
        latest_version="$vers"
        break
      fi
    done
  else
    log_error "Scraping functions not available. Are you running standalone without utils.sh?"
  fi

  local current_normalized="${current_version#v}"
  local latest_normalized="${latest_version#v}"

  if [[ "$latest_version" != "unknown" ]]; then
    if [[ "$current_version" == "auto" || "$current_version" == "latest" || "$current_version" == "beta" ]]; then
      update_available=false
      log_info "APK version ($app_name): $current_version (latest: $latest_version)"
    elif version_less_than "$current_normalized" "$latest_normalized"; then
      update_available=true
      log_warn "APK update available ($app_name): $current_version → $latest_version"
    else
      log_success "APK is up to date ($app_name): $current_version"
    fi
  else
    log_error "Could not determine latest APK version for $app_name"
  fi

  jq -n     --arg app "$app_name"     --arg current "$current_version"     --arg latest "$latest_version"     --arg update_available "$update_available"     '{
			component: "apk",
			app_name: $app,
			current_version: $current,
			latest_version: $latest,
			update_available: ($update_available == "true")
		}'
}
# Parse config.toml and check all dependencies
check_all_dependencies() {
  log_info "Checking all dependencies from $CONFIG_FILE"
  if [[ ! -f "$CONFIG_FILE" ]]; then
    log_error "Config file not found: $CONFIG_FILE"
    exit 1
  fi
  # Initialize results array
  local results=()
  # Check CLI
  local cli_pid=""
  local cli_temp=""
  if [[ "$CHECK_MODE" == "all" || "$CHECK_MODE" == "cli" ]]; then
    cli_temp=$(mktemp)
    local cli_source cli_version
    # Try to extract from config.toml
    if command -v grep &> /dev/null; then
      cli_source=$(grep -Po '(?<=cli-source = ["\x27]).*(?=["\x27])' "$CONFIG_FILE" 2> /dev/null || echo "inotia00/revanced-cli")
      cli_version=$(grep -Po '(?<=cli-version = ["\x27]).*(?=["\x27])' "$CONFIG_FILE" 2> /dev/null || echo "latest")
    else
      cli_source="inotia00/revanced-cli"
      cli_version="latest"
    fi
    # Run in background
    check_cli_updates "$cli_source" "$cli_version" > "$cli_temp" &
    cli_pid=$!
  fi

  # Check patches
  local patches_pid=""
  local patches_temp=""
  if [[ "$CHECK_MODE" == "all" || "$CHECK_MODE" == "patches" ]]; then
    patches_temp=$(mktemp)
    local patches_source patches_version
    if command -v grep &> /dev/null; then
      # Handle both array and string formats
      patches_source=$(grep -Po '(?<=patches-source = ).*' "$CONFIG_FILE" 2> /dev/null | head -1 || echo "anddea/revanced-patches")
      patches_source=$(echo "$patches_source" | tr -d '"' | tr -d "'" | tr -d '[' | tr -d ']' | cut -d',' -f1 | xargs)
      patches_version=$(grep -Po '(?<=patches-version = ["\x27]).*(?=["\x27])' "$CONFIG_FILE" 2> /dev/null || echo "latest")
    else
      patches_source="anddea/revanced-patches"
      patches_version="latest"
    fi
    # Run in background
    check_patches_updates "$patches_source" "$patches_version" > "$patches_temp" &
    patches_pid=$!
  fi

  # Wait for results
  if [[ -n "$cli_pid" ]]; then
    wait "$cli_pid"
    if [[ -f "$cli_temp" ]]; then
      local content
      content=$(cat "$cli_temp")
      if [[ -n "$content" ]]; then
        results+=("$content")
      fi
      rm "$cli_temp"
    fi
  fi

  if [[ -n "$patches_pid" ]]; then
    wait "$patches_pid"
    if [[ -f "$patches_temp" ]]; then
      local content
      content=$(cat "$patches_temp")
      if [[ -n "$content" ]]; then
        results+=("$content")
      fi
      rm "$patches_temp"
    fi
  fi
  # Check APKs (if requested)
  local apk_pids=()
  local apk_temps=()

  if [[ "$CHECK_MODE" == "all" || "$CHECK_MODE" == "apks" ]]; then
    log_info "Checking APK versions from $CONFIG_FILE"

    if command -v python3 &> /dev/null && command -v jq &> /dev/null; then
      local global_version="auto"
      if command -v grep &> /dev/null; then
        global_version=$(grep -m 1 -Po '(?<=^version = [\"\x27]).*(?=[\"\x27])' "$CONFIG_FILE" 2> /dev/null || echo "auto")
      fi

      local apps_json
      apps_json=$(python3 -c "import tomllib, sys, json; d=tomllib.load(open(sys.argv[1],'rb')); print(json.dumps(d))" "$CONFIG_FILE" | jq -c 'to_entries | map(select(.value | type == "object")) | map(select(.value.enabled == true)) | map({app: .key, version: (.value.version // "'"$global_version"'"), urls: [.value."uptodown-dlurl", .value."apkmirror-dlurl", .value."apkpure-dlurl", .value."archive-dlurl", .value."aptoide-dlurl"] | map(select(. != null))})')

      if [[ -n "$apps_json" && "$apps_json" != "[]" ]]; then
        # Use jq to create a null-byte separated stream for efficient processing in a while-read loop.
        echo "$apps_json" | jq -r '.[] | .app + "\u0000" + .version + "\u0000" + (.urls | join("\u0001"))' |
        while IFS=$'\0' read -r app_name app_version urls_str; do
          # Split the URL string (separated by \u0001) into an array.
          local urls=()
          if [[ -n "$urls_str" ]]; then
            mapfile -t urls < <(tr '\1' '\n' <<< "$urls_str")
          fi

          local apk_temp
          apk_temp=$(mktemp)
          apk_temps+=("$apk_temp")

          check_apk_updates "$app_name" "$app_version" "${urls[@]}" > "$apk_temp" &
          apk_pids+=("$!")
        done
      fi
    else
      log_warn "Python3 or jq not found. Skipping APK checks."
    fi
  fi

  # Wait for APK results
  for i in "${!apk_pids[@]}"; do
    wait "${apk_pids[$i]}"
    local temp_file="${apk_temps[$i]}"
    if [[ -f "$temp_file" ]]; then
      local content
      content=$(cat "$temp_file")
      if [[ -n "$content" ]]; then
        results+=("$content")
      fi
      rm -f "$temp_file"
    fi
  done
  # Format output
  format_results "${results[@]}"
}
# Format and output results
format_results() {
  local results=("$@")
  case "$OUTPUT_FORMAT" in
    json)
      # Combine all results into JSON array
      local json_array="["
      local first=true
      for result in "${results[@]}"; do
        if [[ "$first" != "true" ]]; then
          json_array+=","
        fi
        first=false
        json_array+="$result"
      done
      json_array+="]"
      echo "$json_array" | jq '.'
      ;;
    markdown)
      echo "# Dependency Update Report"
      echo ""
      echo "**Generated**: $(date '+%Y-%m-%d %H:%M:%S')"
      echo ""
      echo "## Summary"
      echo ""
      local updates_available=false
      for result in "${results[@]}"; do
        local component
        component=$(echo "$result" | jq -r '.component')
        local source
        source=$(echo "$result" | jq -r '.source // .app_name')
        local current
        current=$(echo "$result" | jq -r '.current_version')
        local latest
        latest=$(echo "$result" | jq -r '.latest_version')
        local update
        update=$(echo "$result" | jq -r '.update_available')
        echo "### $component: $source"
        echo ""
        echo "- **Current Version**: \`$current\`"
        echo "- **Latest Version**: \`$latest\`"
        if [[ "$update" == "true" ]]; then
          echo "- **Status**: 🔄 **Update Available**"
          updates_available=true
        else
          echo "- **Status**: ✅ Up to date"
        fi
        echo ""
      done
      if [[ "$updates_available" == "true" ]]; then
        echo "## 🔔 Action Required"
        echo ""
        echo "Updates are available. Consider updating your configuration."
      else
        echo "## ✅ All dependencies are up to date"
      fi
      ;;
    text | *)
      echo "Dependency Update Report"
      echo "========================"
      echo ""
      echo "Generated: $(date '+%Y-%m-%d %H:%M:%S')"
      echo ""
      local updates_available=false
      for result in "${results[@]}"; do
        local component
        component=$(echo "$result" | jq -r '.component')
        local source
        source=$(echo "$result" | jq -r '.source // .app_name')
        local current
        current=$(echo "$result" | jq -r '.current_version')
        local latest
        latest=$(echo "$result" | jq -r '.latest_version')
        local update
        update=$(echo "$result" | jq -r '.update_available')
        echo "[$component] $source"
        echo "  Current: $current"
        echo "  Latest:  $latest"
        if [[ "$update" == "true" ]]; then
          echo "  Status:  UPDATE AVAILABLE"
          updates_available=true
        else
          echo "  Status:  Up to date"
        fi
        echo ""
      done
      if [[ "$updates_available" == "true" ]]; then
        echo "⚠ Updates are available!"
      else
        echo "✓ All dependencies are up to date"
      fi
      ;;
  esac
}
# Show usage
show_usage() {
  cat << EOF
Usage: $0 [CONFIG_FILE] [OPTIONS]
Check for updates to ReVanced CLI, patches, and APK versions.
Arguments:
    CONFIG_FILE         Path to config.toml (default: config.toml)
Environment Variables:
    CHECK_MODE          What to check: all, cli, patches, apks (default: all)
    OUTPUT_FORMAT       Output format: text, json, markdown (default: text)
    GITHUB_TOKEN        GitHub personal access token (for API rate limits)
    GITHUB_API_URL      Custom GitHub API URL
Examples:
    # Check all dependencies
    $0
    # Check only CLI
    CHECK_MODE=cli $0
    # Check with custom config and JSON output
    OUTPUT_FORMAT=json $0 config-custom.toml
    # Generate markdown report
    OUTPUT_FORMAT=markdown $0 > dependency-report.md
    # With GitHub token (higher rate limits)
    GITHUB_TOKEN=ghp_xxx $0
EOF
}
# Main function
main() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    show_usage
    exit 0
  fi
  log_info "ReVanced Dependency Update Checker"
  log_info "===================================="
  echo ""
  check_all_dependencies
}
# Run main
main "$@"
