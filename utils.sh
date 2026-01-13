#!/usr/bin/env bash
set -euo pipefail

# Main utilities loader - sources all modular components
# Refactored for better maintainability and organization
LC_ALL=C
# Global constants
export CWD=$PWD
export TEMP_DIR="temp"
export BIN_DIR="bin"
export BUILD_DIR="build"

# GitHub authentication header
if [[ "${GITHUB_TOKEN-}" ]]; then
	export GH_HEADER="Authorization: token ${GITHUB_TOKEN}"
else
	export GH_HEADER=
fi

# Version code for builds
export NEXT_VER_CODE=${NEXT_VER_CODE:-$(date +'%Y%m%d')}

# Operating system detection
OS=$(uname -o)
export OS

# Source all library modules
LIB_DIR="${CWD}/lib"

# Check if lib directory exists
if [[ ! -d "$LIB_DIR" ]]; then
	echo "ERROR: Library directory not found: $LIB_DIR"
	exit 1
fi

# Source modules in dependency order
source "${LIB_DIR}/logger.sh" || {
	echo "Failed to load logger.sh"
	exit 1
}
source "${LIB_DIR}/helpers.sh" || {
	echo "Failed to load helpers.sh"
	exit 1
}
source "${LIB_DIR}/config.sh" || {
	echo "Failed to load config.sh"
	exit 1
}
source "${LIB_DIR}/network.sh" || {
	echo "Failed to load network.sh"
	exit 1
}
source "${LIB_DIR}/cache.sh" || {
	echo "Failed to load cache.sh"
	exit 1
}
source "${LIB_DIR}/prebuilts.sh" || {
	echo "Failed to load prebuilts.sh"
	exit 1
}
source "${LIB_DIR}/download.sh" || {
	echo "Failed to load download.sh"
	exit 1
}
source "${LIB_DIR}/patching.sh" || {
	echo "Failed to load patching.sh"
	exit 1
}

log_debug "All utility modules loaded successfully"
