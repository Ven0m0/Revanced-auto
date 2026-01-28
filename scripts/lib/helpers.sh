#!/usr/bin/env bash
set -euo pipefail
# =============================================================================
# Helper Utility Functions
# =============================================================================
# Common utility functions for validation, version comparison, and formatting
# =============================================================================

# Check if a value is one of the provided options
# Args:
#   $1: Value to check
#   $@: Valid options
# Returns:
#   0 if value is in options, 1 otherwise
# Example: isoneof "apk" "apk" "module" "both" && echo "valid"
isoneof() {
  local target="${1:-}"
  local option

  if [[ -z "$target" ]]; then
    return 1
  fi

  shift
  for option in "$@"; do
    [[ "$option" == "$target" ]] && return 0
  done
  return 1
}

# Get highest version from a list of versions
# Handles semantic versioning and sorts appropriately
# Args:
#   stdin: List of versions (one per line)
# Returns:
#   Highest version string
# Example: echo -e "1.0.0\n2.0.0\n1.5.0" | get_highest_ver
get_highest_ver() {
  local versions first_version

  # Read all versions from stdin
  versions=$(cat)

  if [[ -z "$versions" ]]; then
    log_debug "get_highest_ver: no versions provided"
    return 1
  fi

  first_version=$(head -1 <<< "$versions")

  # If first version is not semver, return as-is (may be date-based or custom)
  if ! semver_validate "$first_version"; then
    echo "$first_version"
    return 0
  fi

  # Use version sort for semantic versions
  sort -rV <<< "$versions" | head -1
}

# Validate semantic version format
# Args:
#   $1: Version string
# Returns:
#   0 if valid semver, 1 otherwise
# Example: semver_validate "1.2.3" && echo "valid semver"
semver_validate() {
  local version="${1:-}"

  if [[ -z "$version" ]]; then
    return 1
  fi

  # Remove metadata suffix (everything after -)
  version="${version%-*}"

  # Remove 'v' prefix if present
  version="${version#v}"

  # Remove all digits and dots - if anything remains, it's not semver
  local cleaned="${version//[.0-9]/}"

  # Valid semver should have nothing left after removing digits and dots
  [[ ${#cleaned} -eq 0 ]]
}

# Convert space-separated list to newline-separated
# Args:
#   $1: String with items
# Returns:
#   Newline-separated list
list_args() {
  tr -d '\t\r' <<< "$1" | tr -s ' ' | sed 's/" "/"\n"/g' | sed 's/\([^"]\)"\([^"]\)/\1'\''\2/g' | grep -v '^$' || :
}

# Join arguments with a prefix
# Args:
#   $1: String with items
#   $2: Prefix to add
# Returns:
#   Space-separated list with prefix
join_args() {
  list_args "$1" | sed "s/^/${2} /" | paste -sd " " - || :
}

# Normalize architecture name for APK downloads
# Args:
#   $1: Architecture name
# Returns:
#   Normalized architecture name
# Example: normalize_arch "arm-v7a" -> "armeabi-v7a"
normalize_arch() {
  local arch="${1:-}"

  # Convert arm-v7a to armeabi-v7a for APK compatibility
  if [[ "$arch" = "arm-v7a" ]]; then
    echo "armeabi-v7a"
  else
    echo "$arch"
  fi
}

# Format version string for filenames
# Removes spaces and 'v' prefix
# Args:
#   $1: Version string
# Returns:
#   Formatted version string
# Example: format_version "v 1.2.3" -> "1.2.3"
format_version() {
  local version="${1:-}"

  # Remove spaces
  version="${version// /}"
  # Remove 'v' prefix
  version="${version#v}"

  echo "$version"
}

# Trim leading and trailing whitespace from string
# Args:
#   $1: String to trim
# Returns:
#   Trimmed string
trim_whitespace() {
  local value="${1:-}"

  # Remove leading whitespace
  value="${value#"${value%%[![:space:]]*}"}"
  # Remove trailing whitespace
  value="${value%"${value##*[![:space:]]}"}"
  echo "$value"
}

# Get architecture preference list for APK downloads
# Args:
#   $1: Requested architecture
#   $2: Separator (default: newline for APKMirror, comma for Uptodown)
# Returns:
#   List of architectures to try in order of preference
get_arch_preference() {
  local arch="${1:-}"
  local sep="${2:-$'\n'}" # Default to newline separator

  if [[ "$arch" = "all" ]]; then
    echo "universal${sep}noarch${sep}arm64-v8a + armeabi-v7a"
  else
    echo "${arch}${sep}universal${sep}noarch${sep}arm64-v8a + armeabi-v7a"
  fi
}

# Get last supported version for a patch
# Args:
#   $1: list_patches output
#   $2: Package name
#   $3: Included patches selection
#   $4: Excluded patches selection
#   $5: Exclusive flag
#   $6: CLI jar path (optional, uses $rv_cli_jar if not provided)
#   $7+: Patches jar path(s) - supports multiple jars for multi-source
# Returns:
#   Highest supported version (union across all patch sources)
get_patch_last_supported_ver() {
  local list_patches=$1 pkg_name=$2 inc_sel=$3 _exc_sel=$4 _exclusive=$5
  local cli_jar=${6:-$rv_cli_jar}
  shift 6
  local -a patches_jars=("$@")

  # If no patches jars provided, use default
  if [[ ${#patches_jars[@]} -eq 0 ]]; then
    patches_jars=("${rv_patches_jar:-}")
  fi

  local op

  if [[ "$inc_sel" ]]; then
    if ! op=$(awk '{$1=$1}1' <<< "$list_patches"); then
      epr "list-patches: '$op'"
      return 1
    fi

    # Use single awk invocation instead of multiple sed calls in a loop
    local vers
    vers=$(awk -v patches="$(list_args "$inc_sel")" '
			BEGIN {
				# Build array of patch names
				split(patches, p_arr, "\n")
				for (i in p_arr) {
					# Remove quotes from patch names
					gsub(/^"|"$/, "", p_arr[i])
					patches_map[p_arr[i]] = 1
				}
				in_vers = 0
			}
			/^Name:/ {
				current_name = $2
				in_vers = 0
			}
			/^Compatible versions:/ && (current_name in patches_map) {
				in_vers = 1
				next
			}
			in_vers && /^$/ {
				in_vers = 0
			}
			in_vers {
				print
			}
		' <<< "$op")

    vers=$(awk '{$1=$1}1' <<< "$vers")
    if [[ "$vers" ]]; then
      get_highest_ver <<< "$vers"
      return
    fi
  fi

  # Collect versions from all patch sources (union approach)
  local all_versions="" source_idx=1

  # Create temp dir for parallel processing
  local temp_dir
  temp_dir=$(mktemp -d)
  local pids=()
  local i=0

  # Launch all jobs in parallel
  for patches_jar in "${patches_jars[@]}"; do
    log_debug "Checking compatible versions from patch source $((i + 1))/${#patches_jars[@]}"

    (
      local op
      if ! op=$(java -jar "$cli_jar" list-versions "$patches_jar" -f "$pkg_name" 2>&1 | tail -n +3); then
        # Write error to file
        echo "$op" > "${temp_dir}/${i}.err"
        exit 1
      fi

      echo "$op" > "${temp_dir}/${i}.out"
    ) &
    pids+=($!)
    i=$((i + 1))
  done

  # Wait for all jobs to complete
  for pid in "${pids[@]}"; do
    wait "$pid" || true
  done

  # Process results
  i=0
  for patches_jar in "${patches_jars[@]}"; do
    source_idx=$((i + 1))

    if [[ -f "${temp_dir}/${i}.err" ]]; then
      local err_msg
      err_msg=$(cat "${temp_dir}/${i}.err")
      log_warn "Failed to get versions from patch source ${source_idx}: $err_msg"
      i=$((i + 1))
      continue
    fi

    if [[ ! -f "${temp_dir}/${i}.out" ]]; then
      # Should not happen if err file not present, but safety check
      log_warn "Failed to get versions from patch source ${source_idx}: No output"
      i=$((i + 1))
      continue
    fi

    local op
    op=$(cat "${temp_dir}/${i}.out")

    if [[ "$op" = "Any" ]]; then
      # This source supports any version - skip to next
      i=$((i + 1))
      continue
    fi

    local pcount
    pcount=$(head -1 <<< "$op")
    pcount=${pcount#*(}
    pcount=${pcount% *}

    if [[ "$pcount" = "" ]]; then
      log_warn "Could not determine patch count for source ${source_idx}"
      i=$((i + 1))
      continue
    fi

    # Extract versions supported by this source
    local source_versions
    source_versions=$(grep -F "($pcount patch" <<< "$op" | sed 's/ (.* patch.*//')

    if [[ "$source_versions" ]]; then
      all_versions+="$source_versions"$'\n'
      log_debug "Source ${source_idx} supports $(echo "$source_versions" | wc -l) version(s)"
    fi

    i=$((i + 1))
  done

  rm -rf "$temp_dir"

  if [[ -z "$all_versions" ]]; then
    log_warn "No compatible versions found across ${#patches_jars[@]} patch source(s)"
    return 1
  fi

  # Union: remove duplicates and get highest version
  local highest_version
  highest_version=$(echo "$all_versions" | sort -u -V | tail -1)
  log_debug "Highest compatible version (union): $highest_version"
  echo "$highest_version"
}

# Set prebuilt binary paths based on architecture
set_prebuilts() {
  export APKSIGNER="${BIN_DIR}/apksigner.jar"
  local arch
  arch=$(uname -m)

  if [[ "$arch" = aarch64 ]]; then
    arch=arm64
  elif [[ "${arch:0:5}" = "armv7" ]]; then
    arch=arm
  elif [[ "$arch" = x86_64 ]]; then
    arch=x86_64
  fi

  # Auto-detect aapt2: prefer system binary, fall back to bundled
  local system_aapt2
  system_aapt2=$(command -v aapt2 || true)

  if [[ -n "$system_aapt2" ]] && [[ -x "$system_aapt2" ]]; then
    # System aapt2 found and executable
    export AAPT2="$system_aapt2"
    log_debug "Using system aapt2: $system_aapt2"
  else
    # Fall back to bundled binary
    local bundled_aapt2="${BIN_DIR}/aapt2/aapt2-${arch}"

    if [[ -f "$bundled_aapt2" ]] && [[ -x "$bundled_aapt2" ]]; then
      export AAPT2="$bundled_aapt2"
      log_debug "Using bundled aapt2 for architecture: $arch"
    elif [[ "$arch" = "x86_64" ]]; then
      # x86_64 bundled binary not available
      log_warn "No bundled aapt2 for x86_64 architecture"
      log_warn "Install system aapt2 or build from source: https://developer.android.com/tools/aapt2"

      # Try arm64 with emulation as last resort
      local arm64_aapt2="${BIN_DIR}/aapt2/aapt2-arm64"
      if [[ -f "$arm64_aapt2" ]] && [[ -x "$arm64_aapt2" ]]; then
        export AAPT2="$arm64_aapt2"
        log_warn "Attempting to use arm64 aapt2 (requires ARM emulation)"
      else
        log_warn "No compatible aapt2 found - aapt2 optimization will be disabled"
        export AAPT2=""
      fi
    else
      log_warn "Bundled aapt2 not found or not executable: $bundled_aapt2"
      export AAPT2=""
    fi
  fi

  log_debug "Set prebuilts for architecture: $arch (AAPT2=${AAPT2:-none})"
}

# Scrape text content from HTML using a CSS selector
# Args:
#   $1: Selector
#   stdin: HTML content
# Returns:
#   Extracted text
# Note: Uses Python HTML parser (scripts/html_parser.py)
scrape_text() {
  local selector=$1
  python3 "${CWD}/scripts/html_parser.py" --text "$selector"
}

# Scrape attribute value from HTML using a CSS selector
# Args:
#   $1: Selector
#   $2: Attribute name
#   stdin: HTML content
# Returns:
#   Extracted attribute value
# Note: Uses Python HTML parser (scripts/html_parser.py)
scrape_attr() {
  local selector=$1
  local attr=$2
  python3 "${CWD}/scripts/html_parser.py" --attribute "$attr" "$selector"
}
