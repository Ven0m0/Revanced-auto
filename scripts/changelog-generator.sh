#!/usr/bin/env bash
# Comprehensive changelog generator for ReVanced Builder
# Generates changelogs from git commits and ReVanced patches updates

set -euo pipefail

# Color codes
readonly CYAN='\033[0;36m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

# Configuration
GITHUB_API="${GITHUB_API_URL:-https://api.github.com}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

# Logging functions
log_info() { echo -e "${CYAN}ℹ${NC} $*" >&2; }
log_success() { echo -e "${GREEN}✓${NC} $*" >&2; }
log_warn() { echo -e "${YELLOW}⚠${NC} $*" >&2; }
log_error() { echo -e "${RED}✗${NC} $*" >&2; }

# Make authenticated GitHub API requests
gh_api_request() {
  local endpoint=$1
  local headers=(-H "Accept: application/vnd.github.v3+json")

  if [[ -n "$GITHUB_TOKEN" ]]; then
    headers+=(-H "Authorization: token $GITHUB_TOKEN")
  fi

  curl -sSL "${headers[@]}" "$GITHUB_API/$endpoint"
}

# Parse commits between two references (tags, commits, etc.)
parse_commits() {
  local from_ref=${1:-}
  local to_ref=${2:-HEAD}

  local range
  if [[ -z "$from_ref" ]]; then
    # Get commits from last tag to HEAD
    local last_tag
    last_tag=$(git describe --tags --abbrev=0 2> /dev/null || echo "")

    if [[ -z "$last_tag" ]]; then
      log_warn "No previous tag found, using all commits"
      range="$to_ref"
    else
      range="${last_tag}..${to_ref}"
    fi
  else
    range="${from_ref}..${to_ref}"
  fi

  log_info "Parsing commits from range: $range"

  # Parse commits using Python script for performance
  # Use Unit Separator (0x1F) as delimiter
  local separator=$'\x1f'
  git log "$range" --pretty=format:"%H${separator}%s${separator}%an${separator}%ae${separator}%ai" --no-merges | python3 "$(dirname "$0")/changelog_parser.py"

}

# Get ReVanced patches changelog for a repository
get_patches_changelog() {
  local repo=$1 # Format: "owner/repo"
  local from_version=${2:-}
  local to_version=${3:-latest}

  log_info "Fetching changelog for $repo ($from_version -> $to_version)"

  # Get releases between versions
  local releases
  releases=$(gh_api_request "repos/$repo/releases" 2> /dev/null || echo "[]")

  if [[ "$releases" == "[]" ]]; then
    log_warn "No releases found for $repo"
    return 0
  fi

  # Extract release notes between versions
  local capturing=false
  local found_to=false

  echo "$releases" | jq -r '.[] | "\(.tag_name)|\(.name)|\(.body)|\(.published_at)"' | while IFS='|' read -r tag name body published; do
    # Start capturing from to_version
    if [[ "$to_version" == "latest" && ! "$found_to" ]]; then
      capturing=true
      found_to=true
    elif [[ "$tag" == "$to_version" || "$name" == "$to_version" ]]; then
      capturing=true
      found_to=true
    fi

    if [[ "$capturing" == "true" ]]; then
      echo "### $name ($tag)"
      echo "_Published: $(date -d "$published" "+%Y-%m-%d" 2> /dev/null || echo "$published")_"
      echo ""
      echo "$body" | sed 's/^/  /'
      echo ""
    fi

    # Stop capturing at from_version
    if [[ -n "$from_version" && ("$tag" == "$from_version" || "$name" == "$from_version") ]]; then
      break
    fi
  done
}

# Get patches version from config or temp directory
get_current_patches_version() {
  local patches_source=$1

  # Check temp directory for downloaded patches
  local org_name="${patches_source%%/*}"
  local patches_dir="temp/${org_name}-rv"

  if [[ -d "$patches_dir" ]]; then
    # Find the most recent patches file
    local patches_file
    patches_file=$(find "$patches_dir" -name "*.rvp" -o -name "*.jar" | head -1)

    if [[ -n "$patches_file" ]]; then
      # Try to extract version from filename
      local version
      version=$(basename "$patches_file" | grep -oP 'v?\d+\.\d+\.\d+' || echo "unknown")
      echo "$version"
      return 0
    fi
  fi

  # Fallback: query GitHub API for latest release
  local latest_tag
  latest_tag=$(gh_api_request "repos/$patches_source/releases/latest" 2> /dev/null | jq -r '.tag_name // "unknown"')
  echo "$latest_tag"
}

# Generate comprehensive changelog
generate_changelog() {
  local format=${1:-markdown}
  local from_ref=${2:-}
  local to_ref=${3:-HEAD}
  local include_patches=${4:-true}

  log_info "Generating changelog (format: $format)"

  # Collect commits
  declare -A categorized_commits
  categorized_commits[features]=""
  categorized_commits[fixes]=""
  categorized_commits[improvements]=""
  categorized_commits[performance]=""
  categorized_commits[security]=""
  categorized_commits[documentation]=""
  categorized_commits[build]=""
  categorized_commits[refactor]=""
  categorized_commits[tests]=""
  categorized_commits[updates]=""
  categorized_commits[removals]=""
  categorized_commits[other]=""

  local separator=$'\x1f'
  while IFS=$separator read -r category scope description hash author date; do
    local line="- $description"
    if [[ -n "$scope" ]]; then
      line="- **$scope**: $description"
    fi
    line="$line ([$(echo "$hash" | cut -c1-7)])"

    categorized_commits[$category]+="$line"$'\n'
  done < <(parse_commits "$from_ref" "$to_ref")

  # Generate output based on format
  case "$format" in
    markdown | md)
      generate_markdown_changelog categorized_commits "$include_patches"
      ;;
    json)
      generate_json_changelog categorized_commits "$include_patches"
      ;;
    text | plain)
      generate_text_changelog categorized_commits "$include_patches"
      ;;
    *)
      log_error "Unknown format: $format"
      return 1
      ;;
  esac
}

# Generate markdown changelog
generate_markdown_changelog() {
  local -n commits="$1"
  local include_patches=$2

  local build_date
  build_date=$(date +"%Y-%m-%d")

  cat << EOF
# Changelog - $build_date

## 🚀 What's New

EOF

  # Features
  if [[ -n "${commits[features]}" ]]; then
    echo "### ✨ New Features"
    echo ""
    echo "${commits[features]}"
  fi

  # Improvements
  if [[ -n "${commits[improvements]}" ]]; then
    echo "### 📈 Improvements"
    echo ""
    echo "${commits[improvements]}"
  fi

  # Bug Fixes
  if [[ -n "${commits[fixes]}" ]]; then
    echo "### 🐛 Bug Fixes"
    echo ""
    echo "${commits[fixes]}"
  fi

  # Performance
  if [[ -n "${commits[performance]}" ]]; then
    echo "### ⚡ Performance"
    echo ""
    echo "${commits[performance]}"
  fi

  # Security
  if [[ -n "${commits[security]}" ]]; then
    echo "### 🔒 Security"
    echo ""
    echo "${commits[security]}"
  fi

  # Updates
  if [[ -n "${commits[updates]}" ]]; then
    echo "### 🔄 Updates"
    echo ""
    echo "${commits[updates]}"
  fi

  # Documentation
  if [[ -n "${commits[documentation]}" ]]; then
    echo "### 📚 Documentation"
    echo ""
    echo "${commits[documentation]}"
  fi

  # Build & CI
  if [[ -n "${commits[build]}" ]]; then
    echo "### 🔧 Build & CI"
    echo ""
    echo "${commits[build]}"
  fi

  # Refactoring
  if [[ -n "${commits[refactor]}" ]]; then
    echo "### ♻️ Code Refactoring"
    echo ""
    echo "${commits[refactor]}"
  fi

  # Tests
  if [[ -n "${commits[tests]}" ]]; then
    echo "### ✅ Tests"
    echo ""
    echo "${commits[tests]}"
  fi

  # Removals
  if [[ -n "${commits[removals]}" ]]; then
    echo "### 🗑️ Removals & Deprecations"
    echo ""
    echo "${commits[removals]}"
  fi

  # Other
  if [[ -n "${commits[other]}" ]]; then
    echo "### 📝 Other Changes"
    echo ""
    echo "${commits[other]}"
  fi

  # Include patches changelog if requested
  if [[ "$include_patches" == "true" ]]; then
    echo ""
    echo "## 📦 ReVanced Patches Updates"
    echo ""

    # Try to read patches sources from config
    if [[ -f "config.toml" ]]; then
      # Get patches sources from config
      local -a patches_sources=()
      mapfile -t patches_sources < <(grep -Po '(?<=patches-source = ).*' config.toml | tr -d '"' | tr -d "'" || true)

      if [[ ${#patches_sources[@]} -gt 0 ]]; then
        for source in "${patches_sources[@]}"; do
          echo "### $source"
          echo ""
          local current_version
          current_version=$(get_current_patches_version "$source")
          echo "**Current Version**: \`$current_version\`"
          echo ""

          # Get changelog from GitHub releases
          local patches_changelog
          patches_changelog=$(get_patches_changelog "$source" "" "latest" 2> /dev/null || echo "")

          if [[ -n "$patches_changelog" ]]; then
            echo "$patches_changelog"
          else
            echo "_No changelog available_"
          fi
          echo ""
        done
      fi
    fi
  fi

  cat << EOF

---

_Generated on $build_date by [changelog-generator.sh](scripts/changelog-generator.sh)_
EOF
}

# Generate JSON changelog
generate_json_changelog() {
  local -n commits="$1"
  local include_patches=$2

  local build_date
  build_date=$(date -Iseconds)

  cat << EOF
{
  "generated_at": "$build_date",
  "changes": {
EOF

  local first=true
  for category in features improvements fixes performance security updates documentation build refactor tests removals other; do
    if [[ -n "${commits[$category]}" ]]; then
      if [[ "$first" != "true" ]]; then
        echo ","
      fi
      first=false

      echo "    \"$category\": ["
      local item_first=true
      while IFS= read -r line; do
        if [[ -n "$line" ]]; then
          if [[ "$item_first" != "true" ]]; then
            echo ","
          fi
          item_first=false

          # Extract description and hash
          local desc
          desc=$(echo "$line" | sed -E 's/^- (\*\*[^*]+\*\*: )?//' | sed -E 's/ \([a-f0-9]{7}\)$//')
          local hash
          hash=$(echo "$line" | grep -oP '\([a-f0-9]{7}\)' | tr -d '()')

          echo -n "      {\"description\": \"$desc\", \"commit\": \"$hash\"}"
        fi
      done <<< "${commits[$category]}"
      echo ""
      echo -n "    ]"
    fi
  done

  echo ""
  echo "  }"
  echo "}"
}

# Generate plain text changelog
generate_text_changelog() {
  local -n commits="$1"
  local include_patches=$2

  local build_date
  build_date=$(date +"%Y-%m-%d")

  echo "CHANGELOG - $build_date"
  echo "================================"
  echo ""

  for category in features improvements fixes performance security updates documentation build refactor tests removals other; do
    if [[ -n "${commits[$category]}" ]]; then
      local category_name="${category^^}"
      echo "$category_name:"
      echo "--------"
      echo "${commits[$category]}"
    fi
  done
}

# Show usage information
show_usage() {
  cat << EOF
Usage: $0 [OPTIONS]

Generate comprehensive changelogs from git commits and ReVanced patches updates.

Options:
    -f, --format FORMAT       Output format: markdown (default), json, text
    --from REF                Start reference (tag, commit, etc.)
    --to REF                  End reference (default: HEAD)
    --no-patches              Exclude ReVanced patches changelog
    -o, --output FILE         Write output to file instead of stdout
    -h, --help                Show this help message

Environment Variables:
    GITHUB_TOKEN              GitHub personal access token (for API rate limits)
    GITHUB_API_URL            Custom GitHub API URL (default: https://api.github.com)

Examples:
    # Generate markdown changelog for latest changes
    $0

    # Generate changelog between two tags
    $0 --from v1.0.0 --to v2.0.0

    # Generate JSON changelog
    $0 --format json

    # Save to file
    $0 --output CHANGELOG.md

    # Without patches changelog
    $0 --no-patches

EOF
}

# Main function
main() {
  local format="markdown"
  local from_ref=""
  local to_ref="HEAD"
  local include_patches="true"
  local output_file=""

  # Parse arguments
  while [[ $# -gt 0 ]]; do
    case $1 in
      -f | --format)
        format="$2"
        shift 2
        ;;
      --from)
        from_ref="$2"
        shift 2
        ;;
      --to)
        to_ref="$2"
        shift 2
        ;;
      --no-patches)
        include_patches="false"
        shift
        ;;
      -o | --output)
        output_file="$2"
        shift 2
        ;;
      -h | --help)
        show_usage
        exit 0
        ;;
      *)
        log_error "Unknown option: $1"
        show_usage
        exit 1
        ;;
    esac
  done

  # Generate changelog
  if [[ -n "$output_file" ]]; then
    log_info "Writing changelog to: $output_file"
    generate_changelog "$format" "$from_ref" "$to_ref" "$include_patches" > "$output_file"
    log_success "Changelog generated: $output_file"
  else
    generate_changelog "$format" "$from_ref" "$to_ref" "$include_patches"
  fi
}

# Run main function
main "$@"
