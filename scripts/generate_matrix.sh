#!/usr/bin/env bash
# Generate GitHub Actions matrix from config.toml
set -e

# Source config parsing
source lib/logger.sh
source lib/helpers.sh
source lib/config.sh

# Mock toml parser path if needed or rely on environment
if [ -z "$TOML" ]; then
    TOML="bin/toml/tq-$(uname -m)"
    if [ ! -f "$TOML" ]; then
        # Fallback for CI environments where tq might be elsewhere or we rely on toml-cli
        if command -v toml-cli &>/dev/null; then
             TOML="toml-cli"
        else
             # Assuming standard location in project bin if not set
             TOML="./bin/toml/tq-x86_64" 
        fi
    fi
    export TOML
fi

# Load config
toml_prep "config.toml" >/dev/null

# Generate JSON matrix
echo "Generating build matrix..." >&2

# Use jq to filter and construct the JSON directly from __TOML__
# select(.value.enabled != false) handles both explicit true and missing (null != false is true)
# but toml_get handles defaults. 
# Direct jq approach is cleaner if we assume structure.

# We need to handle the case where 'enabled' is missing (default true).
jq -c '{include: [to_entries[] | select(.value.enabled != false) | {id: .key}]}' <<<"$__TOML__"
