#!/usr/bin/env bash
set -euo pipefail
# Generate GitHub Actions matrix from config.toml

# Source all utilities (provides logging, config parsing, helpers)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "${PROJECT_ROOT}/utils.sh"

# Load config
toml_prep "config.toml" > /dev/null

# Generate JSON matrix
echo "Generating build matrix..." >&2

# Use jq to filter and construct the JSON directly from __TOML__
# Select only object-type values (tables) and check their 'enabled' field
# If 'enabled' is missing or not false, include it in the matrix
jq -c '{include: [to_entries[] | select(.value | type == "object") | select(.value.enabled != false) | {id: .key}]}' <<< "$__TOML__"
