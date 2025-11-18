#!/usr/bin/env bash
# Configuration parsing functions for TOML and JSON

# Global variable to store parsed config
__TOML__=""

# Load and parse config file (TOML or JSON)
# Args:
#   $1: Path to config file
# Returns:
#   0 on success, 1 on failure
toml_prep() {
	if [ ! -f "$1" ]; then
		log_warn "Config file not found: $1"
		return 1
	fi

	local ext="${1##*.}"
	log_debug "Loading config file: $1 (format: $ext)"

	if [ "$ext" = "toml" ]; then
		if ! __TOML__=$($TOML --output json --file "$1" .); then
			epr "Failed to parse TOML config: $1"
			return 1
		fi
	elif [ "$ext" = "json" ]; then
		if ! __TOML__=$(cat "$1"); then
			epr "Failed to read JSON config: $1"
			return 1
		fi
	else
		abort "Unsupported config extension: $ext (only .toml and .json supported)"
	fi

	log_debug "Config loaded successfully"
	return 0
}

# Get all table names from config
toml_get_table_names() {
	jq -r -e 'to_entries[] | select(.value | type == "object") | .key' <<<"$__TOML__"
}

# Get main config (non-object entries)
toml_get_table_main() {
	jq -r -e 'to_entries | map(select(.value | type != "object")) | from_entries' <<<"$__TOML__"
}

# Get a specific table from config
# Args:
#   $1: Table name
toml_get_table() {
	jq -r -e ".\"${1}\"" <<<"$__TOML__"
}

# Get a value from a table
# Args:
#   $1: Table object (JSON)
#   $2: Key name
# Returns:
#   Value or empty string if not found
toml_get() {
	local op
	op=$(jq -r ".\"${2}\" | values" <<<"$1" 2>/dev/null)
	if [ -n "$op" ]; then
		# Trim whitespace
		op="${op#"${op%%[![:space:]]*}"}"
		op="${op%"${op##*[![:space:]]}"}"
		# Replace single quotes with double quotes
		op=${op//"'"/'"'}
		echo "$op"
	else
		return 1
	fi
}

# Validate boolean value
# Args:
#   $1: Value to validate
#   $2: Field name (for error message)
vtf() {
	if ! isoneof "${1}" "true" "false"; then
		abort "ERROR: '${1}' is not a valid option for '${2}': only true or false is allowed"
	fi
}

# Update config based on latest patches
# Returns:
#   Updated config JSON if patches changed
config_update() {
	if [ ! -f build.md ]; then
		abort "build.md not available"
	fi

	declare -A sources
	: >"$TEMP_DIR"/skipped
	local upped=()
	local prcfg=false

	for table_name in $(toml_get_table_names); do
		if [ -z "$table_name" ]; then continue; fi

		t=$(toml_get_table "$table_name")
		enabled=$(toml_get "$t" enabled) || enabled=true
		if [ "$enabled" = false ]; then continue; fi

		PATCHES_SRC=$(toml_get "$t" patches-source) || PATCHES_SRC=$DEF_PATCHES_SRC
		PATCHES_VER=$(toml_get "$t" patches-version) || PATCHES_VER=$DEF_PATCHES_VER

		if [[ -v sources["$PATCHES_SRC/$PATCHES_VER"] ]]; then
			if [ "${sources["$PATCHES_SRC/$PATCHES_VER"]}" = 1 ]; then
				upped+=("$table_name")
			fi
		else
			sources["$PATCHES_SRC/$PATCHES_VER"]=0
			local rv_rel="https://api.github.com/repos/${PATCHES_SRC}/releases"

			if [ "$PATCHES_VER" = "dev" ]; then
				last_patches=$(gh_req "$rv_rel" - | jq -e -r '.[0]')
			elif [ "$PATCHES_VER" = "latest" ]; then
				last_patches=$(gh_req "$rv_rel/latest" -)
			else
				last_patches=$(gh_req "$rv_rel/tags/${ver}" -)
			fi

			if ! last_patches=$(jq -e -r '.assets[] | select(.name | endswith("rvp")) | .name' <<<"$last_patches"); then
				abort "Failed to get patches version"
			fi

			if [ "$last_patches" ]; then
				if ! OP=$(grep "^Patches: ${PATCHES_SRC%%/*}/" build.md | grep "$last_patches"); then
					sources["$PATCHES_SRC/$PATCHES_VER"]=1
					prcfg=true
					upped+=("$table_name")
				else
					echo "$OP" >>"$TEMP_DIR"/skipped
				fi
			fi
		fi
	done

	if [ "$prcfg" = true ]; then
		local query=""
		for table in "${upped[@]}"; do
			if [ -n "$query" ]; then query+=" or "; fi
			query+=".key == \"$table\""
		done
		jq "to_entries | map(select(${query} or (.value | type != \"object\"))) | from_entries" <<<"$__TOML__"
	fi
}
