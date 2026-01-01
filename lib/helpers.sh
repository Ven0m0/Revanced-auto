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

	if ! op=$(java -jar "$cli_jar" list-versions "$patches_jar" -f "$pkg_name" 2>&1 | tail -n +3 | awk '{$1=$1}1'); then
		epr "list-versions: '$op'"
		return 1
	fi

	if [ "$op" = "Any" ]; then return; fi

	pcount=$(head -1 <<<"$op")
	pcount=${pcount#*(}
	pcount=${pcount% *}

	if [ -z "$pcount" ]; then
		abort "unreachable: '$pcount'"
	fi

	grep -F "($pcount patch" <<<"$op" | sed 's/ (.* patch.*//' | get_highest_ver || return 1
}

# Set prebuilt binary paths based on architecture
set_prebuilts() {
	APKSIGNER="${BIN_DIR}/apksigner.jar"
	local arch
	arch=$(uname -m)

	if [ "$arch" = aarch64 ]; then
		arch=arm64
	elif [ "${arch:0:5}" = "armv7" ]; then
		arch=arm
	fi

	HTMLQ="${BIN_DIR}/htmlq/htmlq-${arch}"
	AAPT2="${BIN_DIR}/aapt2/aapt2-${arch}"
	TOML="${BIN_DIR}/toml/tq-${arch}"

	log_debug "Set prebuilts for architecture: $arch"
}

# Create module config file
# Args:
#   $1: Module template directory
#   $2: Package name
#   $3: Version
#   $4: Architecture
# Returns:
#   Creates config file in module template
module_config() {
	local ma=""
	if [ "$4" = "arm64-v8a" ]; then
		ma="arm64"
	elif [ "$4" = "arm-v7a" ]; then
		ma="arm"
	fi
	echo "PKG_NAME=$2
PKG_VER=$3
MODULE_ARCH=$ma" >"$1/config"
}

# Create module.prop file for Magisk module
# Args:
#   $1: Module ID
#   $2: Module name
#   $3: Version
#   $4: Description
#   $5: Update JSON URL
#   $6: Module template directory
# Returns:
#   Creates module.prop file in module template
module_prop() {
	echo "id=${1}
name=${2}
version=v${3}
versionCode=${NEXT_VER_CODE}
author=j-hc
description=${4}" >"${6}/module.prop"

	if [ "$ENABLE_MAGISK_UPDATE" = true ]; then echo "updateJson=${5}" >>"${6}/module.prop"; fi
}
