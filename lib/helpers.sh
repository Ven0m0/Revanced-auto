#!/usr/bin/env bash
# Helper utility functions

# Check if a value is one of the provided options
# Args:
#   $1: Value to check
#   $@: Valid options
# Returns:
#   0 if value is in options, 1 otherwise
isoneof() {
	local i=$1 v
	shift
	for v; do
		[ "$v" = "$i" ] && return 0
	done
	return 1
}

# Get highest version from a list of versions
# Handles semantic versioning and sorts appropriately
get_highest_ver() {
	local vers m
	vers=$(tee)
	m=$(head -1 <<<"$vers")

	if ! semver_validate "$m"; then
		echo "$m"
	else
		sort -rV <<<"$vers" | head -1
	fi
}

# Validate semantic version format
# Args:
#   $1: Version string
# Returns:
#   0 if valid semver, 1 otherwise
semver_validate() {
	local a="${1%-*}"
	local a="${a#v}"
	local ac="${a//[.0-9]/}"
	[ ${#ac} = 0 ]
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
# Returns:
#   Highest supported version
get_patch_last_supported_ver() {
	local list_patches=$1 pkg_name=$2 inc_sel=$3 _exc_sel=$4 _exclusive=$5
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

	if ! op=$(java -jar "$rv_cli_jar" list-versions "$rv_patches_jar" -f "$pkg_name" 2>&1 | tail -n +3 | awk '{$1=$1}1'); then
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
