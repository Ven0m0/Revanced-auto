#!/usr/bin/env bash
set -euo pipefail
# CLI wrapper for downloading GmsCore (MicroG)

# Source utilities
# shellcheck source=utils.sh
source "$(dirname "$0")/../utils.sh"

usage() {
  echo "Usage: $0 [revanced|morphe|rex]"
  echo ""
  echo "Providers:"
  echo "  revanced - Official ReVanced GmsCore"
  echo "  morphe   - Wst_Xda (Morphe) GmsCore"
  echo "  rex      - YT-Advanced (Rex) GmsCore"
  exit 1
}

if [[ $# -eq 0 ]]; then
  usage
fi

provider=$1
case "$provider" in
  revanced|morphe|rex)
    fetch_gmscore "$provider" > /dev/null
    ;;
  *)
    usage
    ;;
esac
