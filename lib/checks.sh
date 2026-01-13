#!/usr/bin/env bash
set -euo pipefail

# Environment Check Functions
# Centralizes logic for checking tools, versions, and assets

# Check for required system tools
# Returns 1 if any tool is missing
check_system_tools() {
    local missing=()
    
    for tool in jq java zip python3; do
        if ! command -v "$tool" &>/dev/null; then
            missing+=("$tool")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        epr "Missing required system tools: ${missing[*]}"
        return 1
    fi
    log_debug "All system tools found"
    return 0
}

# Check Java version >= 21
check_java_version() {
    local java_version
    java_version=$(java -version 2>&1 | head -n 1)
    
    local major_version="0"
    if [[ $java_version =~ "([0-9]+)\.([0-9]+)" ]]; then
        if [[ ${BASH_REMATCH[1]} == "1" ]]; then
            major_version="${BASH_REMATCH[2]}"
        else
            major_version="${BASH_REMATCH[1]}"
        fi
    elif [[ $java_version =~ "([0-9]+)" ]]; then
        major_version="${BASH_REMATCH[1]}"
    fi

    if [[ $major_version -lt 21 ]]; then
        epr "Java version must be 21 or higher (found: Java ${major_version})"
        return 1
    fi
    log_debug "Java version ok: ${major_version}"
    return 0
}

# Check project assets
check_assets() {
    if [[ ! -f "assets/ks.keystore" ]]; then
         # Only warn as it can be created
         log_warn "assets/ks.keystore not found (will be created during build)"
    fi
    
    if [[ ! -f "assets/sig.txt" ]]; then
         log_warn "assets/sig.txt not found (signature verification disabled)"
    fi
    
    return 0
}

# Main prerequisite check (used by build.sh)
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! check_system_tools; then
        exit 1
    fi
    
    if ! check_java_version; then
        exit 1
    fi

    check_assets
    
    log_info "Prerequisites check passed"
}
