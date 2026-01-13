#!/usr/bin/env bash
# Release management script for ReVanced Builder
# Handles creation and cleanup of GitHub releases

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${CYAN}ℹ${NC} $*"
}

log_success() {
    echo -e "${GREEN}✓${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $*"
}

log_error() {
    echo -e "${RED}✗${NC} $*"
}

# Check if gh CLI is available
check_gh_cli() {
    if ! command -v gh &> /dev/null; then
        log_error "GitHub CLI (gh) is not installed or not in PATH"
        exit 1
    fi

    # Check authentication
    if ! gh auth status &> /dev/null; then
        log_error "GitHub CLI is not authenticated. Run: gh auth login"
        exit 1
    fi

    log_success "GitHub CLI authenticated"
}

# Delete old release and tag
delete_release() {
    local tag=$1

    log_info "Checking for existing release: $tag"

    if gh release view "$tag" &> /dev/null; then
        log_warn "Deleting existing release: $tag"
        if gh release delete "$tag" --yes --cleanup-tag 2>&1; then
            log_success "Release deleted: $tag"
        else
            log_warn "Failed to delete release (may not exist)"
        fi
    else
        log_info "No existing release found: $tag"
    fi

    # Also try to delete the tag directly if it exists
    if git rev-parse "$tag" &> /dev/null; then
        log_warn "Deleting git tag: $tag"
        git tag -d "$tag" 2>/dev/null || true
        git push origin --delete "$tag" 2>/dev/null || true
    fi
}

# Create new release
create_release() {
    local tag=$1
    local title=$2
    local notes=$3
    local prerelease=${4:-false}

    log_info "Creating new release: $tag"

    local args=(
        "$tag"
        --title "$title"
        --notes "$notes"
    )

    if [[ "$prerelease" == "true" ]]; then
        args+=(--prerelease)
        log_info "Marking as pre-release"
    fi

    if gh release create "${args[@]}"; then
        log_success "Release created: $tag"
        return 0
    else
        log_error "Failed to create release"
        return 1
    fi
}

# Upload APK files to release
upload_apks() {
    local tag=$1
    local apk_dir=$2

    log_info "Uploading APKs from: $apk_dir"

    if [[ ! -d "$apk_dir" ]]; then
        log_error "APK directory not found: $apk_dir"
        return 1
    fi

    local count=0
    for apk in "$apk_dir"/*.apk; do
        if [[ -f "$apk" ]]; then
            local filename=$(basename "$apk")
            log_info "Uploading: $filename"

            if gh release upload "$tag" "$apk" --clobber 2>&1; then
                log_success "Uploaded: $filename"
                ((count++))
            else
                log_error "Failed to upload: $filename"
                return 1
            fi
        fi
    done

    if [[ $count -eq 0 ]]; then
        log_warn "No APK files found in: $apk_dir"
        return 1
    fi

    log_success "Uploaded $count APK file(s)"
    return 0
}

# Generate release notes from build logs
generate_release_notes() {
    local build_logs_dir=${1:-"build-logs"}
    local build_date=$(date +"%Y-%m-%d")

    cat << EOF
# ReVanced Builds - $build_date

Automated daily build of ReVanced applications.

## 📦 Included Apps

EOF

    # Combine all build.md files
    if [[ -d "$build_logs_dir" ]]; then
        for log in "$build_logs_dir"/*.md; do
            if [[ -f "$log" ]]; then
                cat "$log"
                echo ""
            fi
        done
    fi

    cat << EOF

## 📥 Installation

1. Download the APK for your device architecture:
   - **arm64-v8a**: Modern 64-bit devices (recommended)
   - **armeabi-v7a**: Older 32-bit devices

2. Install [MicroG](https://github.com/ReVanced/GmsCore/releases) if not already installed (required for YouTube/YouTube Music)

3. Install the downloaded APK

4. Enjoy!

## ⚙️ Build Information

- **Build Date**: $build_date
- **Build System**: [ReVanced Builder](https://github.com/$GITHUB_REPOSITORY)
- **Patches**: Multiple sources supported (see config.toml)

## 🔧 Technical Details

- APK Signature: v1 + v2 (maximum compatibility)
- Optimizations: AAPT2, riplib, zipalign
- Architecture-specific builds for smaller file sizes

---

🤖 Automated build from [ReVanced Builder](https://github.com/$GITHUB_REPOSITORY)
EOF
}

# Main workflow: delete old and create new release
manage_release() {
    local tag=${1:-"latest"}
    local apk_dir=${2:-"build"}
    local build_logs_dir=${3:-"build-logs"}
    local prerelease=${4:-false}

    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "Release Management: $tag"
    log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Check prerequisites
    check_gh_cli

    # Delete old release
    delete_release "$tag"
    echo ""

    # Generate release notes
    log_info "Generating release notes..."
    local notes
    notes=$(generate_release_notes "$build_logs_dir")
    echo ""

    # Create new release
    local title="Latest Builds"
    if [[ "$prerelease" == "true" ]]; then
        title="Latest Builds (Pre-release)"
    fi

    if ! create_release "$tag" "$title" "$notes" "$prerelease"; then
        log_error "Failed to create release"
        exit 1
    fi
    echo ""

    # Upload APKs
    if ! upload_apks "$tag" "$apk_dir"; then
        log_error "Failed to upload APKs"
        exit 1
    fi
    echo ""

    log_success "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_success "Release management complete!"
    log_success "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# Usage information
show_usage() {
    cat << EOF
Usage: $0 [COMMAND] [OPTIONS]

Commands:
    manage <tag> <apk_dir> <logs_dir> [prerelease]
        Complete release management workflow
        - Delete old release and tag
        - Create new release with notes
        - Upload APKs
        Default: tag=latest, apk_dir=build, logs_dir=build-logs, prerelease=false

    delete <tag>
        Delete a release and its tag
        Default: tag=latest

    create <tag> <title> <notes> [prerelease]
        Create a new release
        Default: prerelease=false

    upload <tag> <apk_dir>
        Upload APKs to an existing release
        Default: apk_dir=build

    notes [logs_dir]
        Generate release notes from build logs
        Default: logs_dir=build-logs

Examples:
    # Full workflow (daily builds)
    $0 manage latest build build-logs false

    # Dev/pre-release builds
    $0 manage latest-dev build build-logs true

    # Just delete old release
    $0 delete latest

    # Create release with custom notes
    $0 create v1.0.0 "Version 1.0.0" "Release notes here"

EOF
}

# Parse command line arguments
main() {
    local command=${1:-""}

    case "$command" in
        manage)
            manage_release "${2:-latest}" "${3:-build}" "${4:-build-logs}" "${5:-false}"
            ;;
        delete)
            check_gh_cli
            delete_release "${2:-latest}"
            ;;
        create)
            check_gh_cli
            create_release "${2:-latest}" "${3:-Latest Builds}" "${4:-Automated builds}" "${5:-false}"
            ;;
        upload)
            check_gh_cli
            upload_apks "${2:-latest}" "${3:-build}"
            ;;
        notes)
            generate_release_notes "${2:-build-logs}"
            ;;
        help|--help|-h)
            show_usage
            ;;
        "")
            log_error "No command specified"
            echo ""
            show_usage
            exit 1
            ;;
        *)
            log_error "Unknown command: $command"
            echo ""
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
