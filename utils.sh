#!/usr/bin/env bash
set -euo pipefail
# Main utilities loader - sources all modular components
# Refactored for better maintainability and organization
LC_ALL=C
# Global constants
export PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CWD="$PROJECT_ROOT" TEMP_DIR="${PROJECT_ROOT}/temp" BIN_DIR="${PROJECT_ROOT}/bin" BUILD_DIR="${PROJECT_ROOT}/build"
# GitHub authentication header
if [[ "${GITHUB_TOKEN-}" ]]; then
  export GH_HEADER="Authorization: token ${GITHUB_TOKEN}"
else
  export GH_HEADER=
fi
# Version code for builds
export NEXT_VER_CODE=${NEXT_VER_CODE:-$(date +'%Y%m%d')}
# Operating system detection
export OS=$(uname -o)
# Source all library modules
LIB_DIR="${PROJECT_ROOT}/scripts/lib"
if [[ ! -d "$LIB_DIR" ]]; then
  echo "ERROR: Library directory not found: $LIB_DIR"
  exit 1
fi
_source_lib() {
  source "${LIB_DIR}/$1" || {
    echo "Failed to load $1"
    exit 1
  }
}
# Source modules in dependency order
_source_lib logger.sh
_source_lib helpers.sh
_source_lib config.sh
_source_lib network.sh
_source_lib cache.sh
_source_lib prebuilts.sh
_source_lib download.sh
_source_lib patching.sh
_source_lib app_processor.sh
_source_lib checks.sh
unset -f _source_lib
log_debug "All utility modules loaded successfully"
