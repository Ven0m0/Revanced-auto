#!/usr/bin/env bash
set -euo pipefail
# =============================================================================
# Helper Utility Functions
# =============================================================================
# Common utility functions for validation, version comparison, and formatting
# =============================================================================

# Global hash cache for file checksums
# This allows subshells to inherit cached hashes if populated in parent
declare -gA __HASH_CACHE__

# Calculate or retrieve SHA256 hash of a file
# Args:
#   $1: File path
# Returns:
#   SHA256 hash
get_file_hash() {
  local file="${1:-}"
  if [[ -z "$file" || ! -f "$file" ]]; then
    return 1
  fi

  # Check cache first
  if [[ -v __HASH_CACHE__["$file"] ]]; then
    echo "${__HASH_CACHE__["$file"]}"
    return 0
  fi

  local hash_line
  if ! hash_line=$(sha256sum "$file"); then
    return 1
  fi
  local hash="${hash_line%% *}"

  # Update cache
  __HASH_CACHE__["$file"]="$hash"
  echo "$hash"
}
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
  # Validate version string (allow alphanumeric, dot, hyphen, underscore, plus)
  if [[ ! "$version" =~ ^[a-zA-Z0-9._+-]+$ ]]; then
    epr "Invalid version string provided"
    return 1
  fi
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
# Get last supported version for a patch
# Get last supported version for a patch
# Args:
#   $1: list_patches output
#   $2: Package name
#   $3: Included patches selection
#   $4: Excluded patches selection
#   $5: Exclusive patches selection
#   $6: CLI jar path (optional, uses $rv_cli_jar if not provided)
#   $7+: Patches jar path(s) - supports multiple jars for multi-source
# Returns:
#   Highest supported version (union across all patch sources)
get_patch_last_supported_ver() {
  local list_patches=$1 pkg_name=$2 inc_sel=$3 exc_sel=$4 exclusive=$5
  local cli_jar=${6:-$rv_cli_jar}
  shift 6
  local -a patches_jars=("$@")
  # If no patches jars provided, use default
  if [[ ${#patches_jars[@]} -eq 0 ]]; then
    patches_jars=("${rv_patches_jar:-}")
  fi

  local awk_script='
    BEGIN {
        # Build inclusion map
        has_inc = 0
        if (inc_patches != "") {
            split(inc_patches, p_arr, /[ \n]+/)
            for (i in p_arr) {
                gsub(/^"|"$/, "", p_arr[i])
                if (p_arr[i] != "") {
                    inc_map[p_arr[i]] = 1
                    has_inc = 1
                }
            }
        }

        # Build exclusion map
        if (exc_patches != "") {
            split(exc_patches, e_arr, /[ \n]+/)
            for (i in e_arr) {
                gsub(/^"|"$/, "", e_arr[i])
                if (e_arr[i] != "") {
                    exc_map[e_arr[i]] = 1
                }
            }
        }

        in_vers = 0
    }
    /^Name:/ {
        current_name = $2
        in_vers = 0
    }
    /^Compatible versions:/ {
        is_included = 0
        if (has_inc) {
            if (current_name in inc_map) is_included = 1
        } else {
            is_included = 1
        }

        if (current_name in exc_map) is_included = 0

        if (is_included) {
            in_vers = 1
            next
        }
    }
    in_vers && /^$/ {
        in_vers = 0
    }
    in_vers {
        gsub(/^[ \t]+|[ \t]+$/, "", $0)
        if ($0 != "") {
           count[$0]++
        }
    }
    END {
        max_c = 0
        for (v in count) {
            if (count[v] > max_c) max_c = count[v]
        }
        for (v in count) {
            if (count[v] == max_c) print v
        }
    }
  '

  local vers=""
  if [[ -n "$inc_sel" ]]; then
    # If patches are explicitly included, use the provided list_patches output ($1)
    if ! op=$(awk '{$1=$1}1' <<< "$list_patches"); then
      epr "list-patches: '$op'"
      return 1
    fi
    vers=$(awk -v inc_patches="$(list_args "$inc_sel")" -v exc_patches="$(list_args "$exc_sel")" "$awk_script" <<< "$op")
  else
    # Auto mode: Determine applicable patches for this package
    # We must fetch the list of patches filtered by package name to support exclusion correctly
    local all_vers_output=""
    local source_idx=1

    # Run list-patches for each jar in parallel
    local -a pids=()
    local temp_dir
    temp_dir=$(mktemp -d)
    trap 'rm -rf "$temp_dir"' RETURN

    local i=0
    for patches_jar in "${patches_jars[@]}"; do
      log_debug "Listing patches for package '$pkg_name' from source $((i + 1))/${#patches_jars[@]}"
      (
        # Invoke CLI to get patches specific to this package
        # Note: We use list-patches instead of list-versions to get patch names for exclusion filtering
        local op
        if ! op=$(java -jar "$cli_jar" list-patches "$patches_jar" -f "$pkg_name" 2>&1); then
             # Write error to file
             echo "$op" > "${temp_dir}/${i}.err"
        else
             echo "$op" > "${temp_dir}/${i}.out"
        fi
      ) &
      pids+=($!)
      i=$((i + 1))
    done

    # Wait for jobs
    for pid in "${pids[@]}"; do
      wait "$pid" || true
    done

    # Collect outputs
    i=0
    for patches_jar in "${patches_jars[@]}"; do
      source_idx=$((i + 1))
      if [[ -f "${temp_dir}/${i}.err" ]]; then
        local err_msg
        err_msg=$(cat "${temp_dir}/${i}.err")
        log_warn "Failed to list patches from source ${source_idx}: $err_msg"
      elif [[ -f "${temp_dir}/${i}.out" ]]; then
        all_vers_output+="$(cat "${temp_dir}/${i}.out")"$'\n'
      else
        log_warn "Failed to get patches from source ${source_idx}: No output"
      fi
      i=$((i + 1))
    done

    # Process combined output with AWK script (Counting logic + Exclusion)
    vers=$(awk -v inc_patches="" -v exc_patches="$(list_args "$exc_sel")" "$awk_script" <<< "$all_vers_output")
  fi

  if [[ "$vers" ]]; then
    local highest
    highest=$(get_highest_ver <<< "$vers")
    log_debug "Highest compatible version (max compatibility): $highest"
    echo "$highest"
    return 0
  fi

  log_warn "No compatible versions found"
  return 1
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
  uv run "${PROJECT_ROOT}/scripts/html_parser.py" --text "$selector"
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
  uv run "${PROJECT_ROOT}/scripts/html_parser.py" --attribute "$attr" "$selector"
}

# Check for Zip Slip vulnerability in an archive
# Args:
#   $1: Path to zip file
# Returns:
#   0 if safe, 1 if unsafe paths detected
check_zip_safety() {
  local zip_file=$1
  if [[ ! -f "$zip_file" ]]; then
    epr "check_zip_safety: file not found: $zip_file"
    return 1
  fi

  # Use Python for reliable cross-platform verification
  if ! uv run python3 -c "
import sys, zipfile, os
try:
    with zipfile.ZipFile(sys.argv[1], 'r') as zf:
        for name in zf.namelist():
            if os.path.isabs(name) or '..' in name.split('/'):
                print(f'Unsafe path detected: {name}')
                sys.exit(1)
except Exception as e:
    print(f'Error verification failed: {e}')
    sys.exit(1)
" "$zip_file"; then
    epr "Security check failed for $zip_file"
    return 1
  fi
  return 0
}
