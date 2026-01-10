#!/usr/bin/env bash
# =============================================================================
# Configuration Parsing Functions
# =============================================================================
# Provides TOML and JSON configuration parsing capabilities
# Uses jq for JSON manipulation and Python (tomllib) for TOML parsing
# =============================================================================

# Global variable to store parsed config (converted to JSON)
__TOML__=""
__CONFIG_FILE__=""

# Load and parse config file (TOML or JSON)
# Args:
#   $1: Path to config file
# Returns:
#   0 on success, 1 on failure
# Note: Parsed config is stored in __TOML__ as JSON
toml_prep() {
	local config_file="${1:-config.toml}"

	# Validate file exists
	if [[ ! -f "$config_file" ]]; then
		log_warn "Config file not found: $config_file"
		return 1
	fi

	# Validate file is readable
	if [[ ! -r "$config_file" ]]; then
		epr "Config file not readable: $config_file"
		return 1
	fi

	local ext="${config_file##*.}"
	log_debug "Loading config file: $config_file (format: $ext)"

	# Parse based on file extension
	case "$ext" in
	toml)
		# Parse TOML to JSON using Python
		if ! __TOML__=$(python3 scripts/toml_get.py --file "$config_file" 2>&1); then
			epr "Failed to parse TOML config: $config_file"
			epr "Parser output: $__TOML__"
			return 1
		fi
		;;

	json)
		# Validate JSON syntax before loading
		if ! __TOML__=$(jq -e . "$config_file" 2>&1); then
			epr "Invalid JSON in config file: $config_file"
			epr "JSON error: $__TOML__"
			return 1
		fi
		;;

	*)
		abort "Unsupported config file extension: .$ext (only .toml and .json are supported)"
		;;
	esac

	# Verify we got valid JSON output
	if [[ -z "$__TOML__" ]] || ! jq -e . <<<"$__TOML__" &>/dev/null; then
		epr "Config parsing produced invalid JSON"
		return 1
	fi

	__CONFIG_FILE__="$config_file"
	log_debug "Config loaded successfully ($(echo "$__TOML__" | jq -r 'keys | length') keys)"
	return 0
}

# Get all table names from config
# Returns: List of table names (one per line)
# Note: Only returns top-level objects, not primitive values
toml_get_table_names() {
	if [[ -z "$__TOML__" ]]; then
		log_warn "Config not loaded - call toml_prep first"
		return 1
	fi
	jq -r -e 'to_entries[] | select(.value | type == "object") | .key' <<<"$__TOML__" 2>/dev/null || true
}

# Get main config (non-object entries)
# Returns: JSON object containing only primitive (non-table) values
toml_get_table_main() {
	if [[ -z "$__TOML__" ]]; then
		log_warn "Config not loaded - call toml_prep first"
		return 1
	fi
	jq -r -e 'to_entries | map(select(.value | type != "object")) | from_entries' <<<"$__TOML__" 2>/dev/null || echo "{}"
}

# Get a specific table from config
# Args:
#   $1: Table name
# Returns: JSON object for the specified table
toml_get_table() {
	local table_name="${1:-}"

	if [[ -z "$table_name" ]]; then
		log_warn "toml_get_table: table name required"
		return 1
	fi

	if [[ -z "$__TOML__" ]]; then
		log_warn "Config not loaded - call toml_prep first"
		return 1
	fi

	jq -r -e ".\"${table_name}\"" <<<"$__TOML__" 2>/dev/null || {
		log_debug "Table not found: $table_name"
		return 1
	}
}

# Get a value from a table
# Args:
#   $1: Table object (JSON)
#   $2: Key name
# Returns:
#   Value or empty string if not found (returns 1 on failure)
# Note: Automatically trims whitespace and normalizes quotes
toml_get() {
	local table_json="${1:-}"
	local key="${2:-}"

	if [[ -z "$table_json" ]] || [[ -z "$key" ]]; then
		log_debug "toml_get: table and key required"
		return 1
	fi

	local value
	if ! value=$(jq -r ".\"${key}\" | values" <<<"$table_json" 2>/dev/null); then
		return 1
	fi

	if [[ -z "$value" ]] || [[ "$value" == "null" ]]; then
		return 1
	fi

	# Trim leading/trailing whitespace using helper function
	value=$(trim_whitespace "$value")

	# Normalize quotes (single to double)
	value="${value//"'"/'"'}"

	echo "$value"
	return 0
}

# Parse a table into a Bash associative array definition (DEPRECATED - DO NOT USE)
# Args:
#   $1: Table object (JSON)
# Returns:
#   String to be eval'd: ([key]="value" ...)
# WARNING: This function is deprecated and unsafe. Use toml_load_table_safe instead.
toml_parse_table_to_array() {
	local table_json="${1:-}"
	if [[ -z "$table_json" ]]; then
		echo "()"
		return
	fi
	# Use @sh to safely quote values for eval
	jq -r 'to_entries | map("[\(.key)]=\(.value | @sh)") | join(" ")' <<<"$table_json" 2>/dev/null || echo "()"
}

# Safely load a table into a named associative array (no eval)
# Args:
#   $1: Variable name to store the associative array
#   $2: Table object (JSON)
# Side effects:
#   Populates the named array with table key-value pairs
# Note: Arrays in JSON are converted to space-separated strings for simple use
toml_load_table_safe() {
	local var_name="$1"
	local table_json="$2"

	if [[ -z "$table_json" ]] || [[ "$table_json" == "null" ]]; then
		return
	fi

	# Read key-value pairs line by line (NUL-separated for safety)
	while IFS= read -r -d '' key && IFS= read -r -d '' value; do
		# Handle arrays: convert to newline-separated string for Bash
		if [[ "$value" == "["* ]]; then
			# Parse JSON array into Bash-friendly format
			value=$(jq -r '.[]' <<<"$value" 2>/dev/null | tr '\n' ' ' | sed 's/ $//')
		fi
		eval "${var_name}[${key}]=\"\${value}\""
	done < <(jq -j 'to_entries[] | .key, "\u0000", (.value | tostring), "\u0000"' <<<"$table_json" 2>/dev/null)
}

# Get array from table as a Bash array
# Args:
#   $1: Variable name to store the array
#   $2: Table object (JSON)
#   $3: Key name
# Side effects:
#   Populates the named array with values
toml_get_array() {
	local var_name="$1"
	local table_json="$2"
	local key="$3"

	local json_array
	if ! json_array=$(jq -e ".\"${key}\"" <<<"$table_json" 2>/dev/null); then
		return 1
	fi

	if [[ "$json_array" == "null" ]]; then
		return 1
	fi

	# Read array elements line by line
	local -a elements=()
	while IFS= read -r element; do
		elements+=("$element")
	done < <(jq -r '.[]' <<<"$json_array" 2>/dev/null)

	# Use nameref to populate caller's array
	eval "${var_name}=(\"\${elements[@]}\")"
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

	while read -r table_name; do
		if [ "$table_name" = "" ]; then continue; fi

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
				last_patches=$(gh_req "$rv_rel/tags/${PATCHES_VER}" -)
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
	done < <(toml_get_table_names)

	if [ "$prcfg" = true ]; then
		local query=""
		for table in "${upped[@]}"; do
			if [ "$query" != "" ]; then query+=" or "; fi
			query+=".key == \"$table\""
		done
		jq "to_entries | map(select(${query} or (.value | type != \"object\"))) | from_entries" <<<"$__TOML__"
	fi
}
