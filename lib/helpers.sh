#!/usr/bin/env bash
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

	first_version=$(head -1 <<<"$versions")

	# If first version is not semver, return as-is (may be date-based or custom)
	if ! semver_validate "$first_version"; then
		echo "$first_version"
		return 0
	fi

	# Use version sort for semantic versions
	sort -rV <<<"$versions" | head -1
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
	tr -d '\t\r' <<<"$1" | tr -s ' ' | sed 's/" "/"\n"/g' | sed 's/\([^"]\)"\([^"]\)/\1'\''\2/g' | grep -v '^$' || :
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
	if [ "$arch" = "arm-v7a" ]; then
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

	if [ "$arch" = "all" ]; then
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
#   $7: Patches jar path (optional, uses $rv_patches_jar if not provided)
# Returns:
#   Highest supported version
get_patch_last_supported_ver() {
	local list_patches=$1 pkg_name=$2 inc_sel=$3 _exc_sel=$4 _exclusive=$5
	local cli_jar=${6:-$rv_cli_jar}
	local patches_jar=${7:-$rv_patches_jar}
	local op

	if [ "$inc_sel" ]; then
		if ! op=$(awk '{$1=$1}1' <<<"$list_patches"); then
			epr "list-patches: '$op'"
			return 1
		fi

		local ver vers="" NL=$'\n'
		while IFS= read -r line; do
			line="${line:1:${#line}-2}"
			ver=$(sed -n "/^Name: $line\$/,/^\$/p" <<<"$op" | sed -n "/^Compatible versions:\$/,/^\$/p" | tail -n +2)
			vers=${ver}${NL}
		done <<<"$(list_args "$inc_sel")"

		vers=$(awk '{$1=$1}1' <<<"$vers")
		if [ "$vers" ]; then
			get_highest_ver <<<"$vers"
			return
		fi
	fi

	if ! op=$(java -jar "$cli_jar" list-versions "$patches_jar" -f "$pkg_name" 2>&1 | tail -n +3); then
		epr "list-versions: '$op'"
		return 1
	fi

	if [ "$op" = "Any" ]; then return; fi

	pcount=$(head -1 <<<"$op")
	pcount=${pcount#*(}
	pcount=${pcount% *}

	if [ "$pcount" = "" ]; then
		abort "unreachable: '$pcount'"
	fi

	grep -F "($pcount patch" <<<"$op" | sed 's/ (.* patch.*//' | get_highest_ver || return 1
}

# Set prebuilt binary paths based on architecture
set_prebuilts() {
	export APKSIGNER="${BIN_DIR}/apksigner.jar"
	local arch
	arch=$(uname -m)

	if [ "$arch" = aarch64 ]; then
		arch=arm64
	elif [ "${arch:0:5}" = "armv7" ]; then
		arch=arm
	elif [ "$arch" = x86_64 ]; then
		# Note: Prebuilt x86_64 binaries not provided
		# Users need to build or obtain x86_64 versions
		# For now, try to use arm64 (may work via emulation)
		log_warn "x86_64 architecture detected - using arm64 binaries (may require ARM emulation)"
		arch=arm64
	fi

	export HTMLQ="${BIN_DIR}/htmlq/htmlq-${arch}"
	export AAPT2="${BIN_DIR}/aapt2/aapt2-${arch}"
	export TOML="${BIN_DIR}/toml/tq-${arch}"

	log_debug "Set prebuilts for architecture: $arch"
}
