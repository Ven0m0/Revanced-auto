#!/usr/bin/env bash
# Extra utilities for CI/CD workflows

set -euo pipefail

CWD=$PWD
TEMP_DIR="temp"
BIN_DIR="bin"

# Source required libraries
source "${CWD}/scripts/lib/logger.sh"
source "${CWD}/scripts/lib/helpers.sh"
source "${CWD}/scripts/lib/config.sh"

# Set prebuilt tools
set_prebuilts

# Separate config for a specific app
# Usage: ./extras.sh separate-config <config.toml> <app_name> <output.toml>
separate_config() {
  local input_config=$1
  local app_name=$2
  local output_config=$3

  log_info "Separating config for: $app_name"

  if [ ! -f "$input_config" ]; then
    abort "Config file not found: $input_config"
  fi

  # Load the config
  toml_prep "$input_config" || abort "Failed to load config: $input_config"

  # Get main config
  local main_config
  main_config=$(toml_get_table_main)

  # Get the specific app table
  local app_table
  if ! app_table=$(toml_get_table "$app_name" 2>/dev/null); then
    abort "App '$app_name' not found in config"
  fi

  # Create a new config with just the main config and the specific app
  local new_config
  new_config=$(jq -n \
    --argjson main "$main_config" \
    --argjson app "$app_table" \
    --arg name "$app_name" \
    '$main + {($name): $app}')

  # Convert back to TOML if output is .toml, otherwise output JSON
  if [[ $output_config == *.toml ]]; then
    # For TOML output, we need to use a tool or write manually
    # Since we don't have a JSON->TOML converter, we'll output JSON with .toml extension
    # The build.sh accepts both .json and .toml
    echo "$new_config" >"$output_config"
    log_info "Separated config saved to: $output_config (JSON format)"
  else
    echo "$new_config" >"$output_config"
    log_info "Separated config saved to: $output_config"
  fi
}

# Combine build logs from multiple files
# Usage: ./extras.sh combine-logs <logs_directory>
combine_logs() {
  local logs_dir=$1

  log_info "Combining build logs from: $logs_dir"

  if [ ! -d "$logs_dir" ]; then
    abort "Logs directory not found: $logs_dir"
  fi

  # Find all build.md files and combine them
  local log_files
  log_files=$(find "$logs_dir" -name "build.md" -type f 2>/dev/null | sort)

  if [ "$log_files" = "" ]; then
    log_warn "No build.md files found in $logs_dir"
    echo "No builds completed"
    return 0
  fi

  # Combine all logs
  local first=true
  while IFS= read -r log_file; do
    if [ "$first" = true ]; then
      first=false
    else
      echo ""
      echo "---"
      echo ""
    fi
    cat "$log_file"
  done <<<"$log_files"
}

# Main command dispatcher
case "${1:-}" in
  separate-config)
    if [ $# -ne 4 ]; then
      echo "Usage: $0 separate-config <config.toml> <app_name> <output.toml>"
      exit 1
    fi
    separate_config "$2" "$3" "$4"
    ;;
  combine-logs)
    if [ $# -ne 2 ]; then
      echo "Usage: $0 combine-logs <logs_directory>"
      exit 1
    fi
    combine_logs "$2"
    ;;
  *)
    echo "Usage: $0 {separate-config|combine-logs} [args...]"
    echo ""
    echo "Commands:"
    echo "  separate-config <config.toml> <app_name> <output.toml>"
    echo "      Extract configuration for a specific app"
    echo ""
    echo "  combine-logs <logs_directory>"
    echo "      Combine build.md files from directory"
    exit 1
    ;;
esac
