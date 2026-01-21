#!/usr/bin/env bash
# Cache management library for ReVanced Builder
# Provides intelligent caching with validation and cleanup

# Cache configuration
readonly CACHE_DIR="${CACHE_DIR:-temp}"
readonly DEFAULT_CACHE_TTL=86400 # 24 hours in seconds
readonly CACHE_INDEX_FILE="$CACHE_DIR/.cache-index.json"

# Cache metadata structure (JSON):
# {
#   "path/to/file": {
#     "created": timestamp,
#     "accessed": timestamp,
#     "size": bytes,
#     "checksum": "sha256sum",
#     "url": "source_url",
#     "ttl": seconds
#   }
# }

# Initialize cache system
cache_init() {
  local cache_dir=${1:-$CACHE_DIR}

  # Create cache directory
  mkdir -p "$cache_dir"

  # Initialize index file if it doesn't exist
  if [[ ! -f "$CACHE_INDEX_FILE" ]]; then
    echo "{}" > "$CACHE_INDEX_FILE"
    log_debug "Created cache index: $CACHE_INDEX_FILE"
  fi

  log_debug "Cache initialized: $cache_dir"
}

# Check if cached file is valid
# Returns 0 if valid, 1 otherwise
cache_is_valid() {
  local file_path=$1
  local ttl=${2:-$DEFAULT_CACHE_TTL}

  # Check if file exists
  if [[ ! -f "$file_path" ]]; then
    log_debug "Cache miss: file not found - $file_path"
    return 1
  fi

  # Check if index exists
  if [[ ! -f "$CACHE_INDEX_FILE" ]]; then
    log_debug "Cache miss: index not found"
    return 1
  fi

  # Get cache entry from index
  local cache_entry
  cache_entry=$(jq -r --arg path "$file_path" '.[$path] // empty' "$CACHE_INDEX_FILE" 2> /dev/null)

  if [[ -z "$cache_entry" || "$cache_entry" == "null" ]]; then
    log_debug "Cache miss: no index entry for $file_path"
    return 1
  fi

  # Check TTL
  local created
  created=$(echo "$cache_entry" | jq -r '.created // 0')
  local now
  now=$(date +%s)
  local age=$((now - created))

  # Use TTL from cache entry if available, otherwise use provided/default TTL
  local entry_ttl
  entry_ttl=$(echo "$cache_entry" | jq -r '.ttl // 0')
  if [[ "$entry_ttl" -gt 0 ]]; then
    ttl=$entry_ttl
  fi

  if [[ $age -gt $ttl ]]; then
    log_debug "Cache expired: $file_path (age: ${age}s, ttl: ${ttl}s)"
    return 1
  fi

  # Verify checksum if available
  local stored_checksum
  stored_checksum=$(echo "$cache_entry" | jq -r '.checksum // ""')

  if [[ -n "$stored_checksum" ]]; then
    local current_checksum
    current_checksum=$(sha256sum "$file_path" | cut -d' ' -f1)

    if [[ "$current_checksum" != "$stored_checksum" ]]; then
      log_warn "Cache integrity check failed: $file_path"
      return 1
    fi
  fi

  log_debug "Cache hit: $file_path"
  return 0
}

# Add or update cache entry
cache_put() {
  local file_path=$1
  local source_url=${2:-""}
  local ttl=${3:-$DEFAULT_CACHE_TTL}

  if [[ ! -f "$file_path" ]]; then
    log_error "Cannot cache non-existent file: $file_path"
    return 1
  fi

  # Initialize cache if needed
  cache_init

  # Get file metadata
  local file_size
  file_size=$(stat -c%s "$file_path" 2> /dev/null || stat -f%z "$file_path" 2> /dev/null)
  local checksum
  checksum=$(sha256sum "$file_path" | cut -d' ' -f1)
  local now
  now=$(date +%s)

  # Create cache entry
  local cache_entry
  cache_entry=$(jq -n \
    --arg created "$now" \
    --arg accessed "$now" \
    --arg size "$file_size" \
    --arg checksum "$checksum" \
    --arg url "$source_url" \
    --arg ttl "$ttl" \
    '{
			created: ($created | tonumber),
			accessed: ($accessed | tonumber),
			size: ($size | tonumber),
			checksum: $checksum,
			url: $url,
			ttl: ($ttl | tonumber)
		}')

  # Update index
  local temp_index
  temp_index=$(mktemp)
  jq --arg path "$file_path" --argjson entry "$cache_entry" \
    '.[$path] = $entry' "$CACHE_INDEX_FILE" > "$temp_index"
  mv "$temp_index" "$CACHE_INDEX_FILE"

  log_debug "Cached: $file_path (size: $file_size, ttl: ${ttl}s)"
  return 0
}

# Update last accessed timestamp
cache_touch() {
  local file_path=$1

  if [[ ! -f "$CACHE_INDEX_FILE" ]]; then
    return 1
  fi

  local now
  now=$(date +%s)

  local temp_index
  temp_index=$(mktemp)
  jq --arg path "$file_path" --arg accessed "$now" \
    'if .[$path] then .[$path].accessed = ($accessed | tonumber) else . end' \
    "$CACHE_INDEX_FILE" > "$temp_index"
  mv "$temp_index" "$CACHE_INDEX_FILE"

  log_debug "Cache touched: $file_path"
}

# Remove cache entry
cache_remove() {
  local file_path=$1
  local remove_file=${2:-true}

  # Remove from index
  if [[ -f "$CACHE_INDEX_FILE" ]]; then
    local temp_index
    temp_index=$(mktemp)
    jq --arg path "$file_path" 'del(.[$path])' "$CACHE_INDEX_FILE" > "$temp_index"
    mv "$temp_index" "$CACHE_INDEX_FILE"
  fi

  # Remove file
  if [[ "$remove_file" == "true" && -f "$file_path" ]]; then
    rm -f "$file_path"
    log_debug "Removed from cache: $file_path"
  fi
}

# Get cache statistics
cache_stats() {
  if [[ ! -f "$CACHE_INDEX_FILE" ]]; then
    echo "Cache empty or not initialized"
    return 0
  fi

  local total_entries
  total_entries=$(jq 'length' "$CACHE_INDEX_FILE")

  local total_size
  total_size=$(jq '[.[] | .size] | add // 0' "$CACHE_INDEX_FILE")

  local now
  now=$(date +%s)

  # Count expired entries
  local expired_count
  expired_count=$(jq --arg now "$now" \
    '[.[] | select((.created + .ttl) < ($now | tonumber))] | length' \
    "$CACHE_INDEX_FILE")

  echo "Cache Statistics:"
  echo "  Total entries: $total_entries"
  echo "  Total size: $(numfmt --to=iec-i --suffix=B "$total_size" 2> /dev/null || echo "${total_size} bytes")"
  echo "  Expired entries: $expired_count"
  echo "  Cache directory: $CACHE_DIR"
}

# Clean expired cache entries
cache_cleanup() {
  local force=${1:-false}

  if [[ ! -f "$CACHE_INDEX_FILE" ]]; then
    log_info "No cache to clean"
    return 0
  fi

  local now
  now=$(date +%s)
  local removed_count=0

  log_info "Cleaning expired cache entries..."

  # Get list of expired entries
  local expired_entries
  expired_entries=$(jq -r --arg now "$now" \
    'to_entries | .[] | select((.value.created + .value.ttl) < ($now | tonumber)) | .key' \
    "$CACHE_INDEX_FILE")

  # Remove expired entries
  while IFS= read -r file_path; do
    if [[ -n "$file_path" ]]; then
      cache_remove "$file_path" true
      ((removed_count++))
    fi
  done <<< "$expired_entries"

  if [[ $removed_count -gt 0 ]]; then
    log_success "Removed $removed_count expired cache entries"
  else
    log_info "No expired entries to remove"
  fi

  # Force cleanup: remove entries for non-existent files
  if [[ "$force" == "true" ]]; then
    log_info "Performing forced cleanup..."

    local orphaned_count=0
    local all_entries
    all_entries=$(jq -r 'keys[]' "$CACHE_INDEX_FILE")

    while IFS= read -r file_path; do
      if [[ -n "$file_path" && ! -f "$file_path" ]]; then
        cache_remove "$file_path" false
        ((orphaned_count++))
      fi
    done <<< "$all_entries"

    if [[ $orphaned_count -gt 0 ]]; then
      log_success "Removed $orphaned_count orphaned index entries"
    fi
  fi

  return 0
}

# Clean cache entries by pattern
cache_clean_pattern() {
  local pattern=$1

  if [[ ! -f "$CACHE_INDEX_FILE" ]]; then
    return 0
  fi

  log_info "Cleaning cache entries matching: $pattern"

  local removed_count=0
  local matching_entries
  matching_entries=$(jq -r --arg pattern "$pattern" \
    'to_entries | .[] | select(.key | test($pattern)) | .key' \
    "$CACHE_INDEX_FILE")

  while IFS= read -r file_path; do
    if [[ -n "$file_path" ]]; then
      cache_remove "$file_path" true
      ((removed_count++))
    fi
  done <<< "$matching_entries"

  if [[ $removed_count -gt 0 ]]; then
    log_success "Removed $removed_count cache entries"
  else
    log_info "No matching entries found"
  fi
}

# Cache-aware download function
# Downloads file and caches it, or returns cached version if valid
cache_download() {
  local url=$1
  local output_path=$2
  local ttl=${3:-$DEFAULT_CACHE_TTL}
  local force_download=${4:-false}

  # Check if cached version is valid
  if [[ "$force_download" != "true" ]] && cache_is_valid "$output_path" "$ttl"; then
    log_info "Using cached file: $output_path"
    cache_touch "$output_path"
    return 0
  fi

  # Download file
  log_info "Downloading: $url"

  # Ensure parent directory exists
  mkdir -p "$(dirname "$output_path")"

  # Use existing req function from network.sh if available
  if declare -f req &> /dev/null; then
    if req "$url" "$output_path"; then
      # Cache the downloaded file
      cache_put "$output_path" "$url" "$ttl"
      return 0
    else
      log_error "Download failed: $url"
      return 1
    fi
  else
    # Fallback to direct curl/wget
    if command -v curl &> /dev/null; then
      if curl -sSL -o "$output_path" "$url"; then
        cache_put "$output_path" "$url" "$ttl"
        return 0
      fi
    elif command -v wget &> /dev/null; then
      if wget -q -O "$output_path" "$url"; then
        cache_put "$output_path" "$url" "$ttl"
        return 0
      fi
    fi

    log_error "Download failed: $url"
    return 1
  fi
}

# Export cache directory for use in other modules
get_cache_dir() {
  echo "$CACHE_DIR"
}

# Get cache path for a given key/identifier
get_cache_path() {
  local key=$1
  local subdir=${2:-""}

  if [[ -n "$subdir" ]]; then
    echo "$CACHE_DIR/$subdir/$key"
  else
    echo "$CACHE_DIR/$key"
  fi
}
