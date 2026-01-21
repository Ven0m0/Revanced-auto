#!/usr/bin/env bash
set -euo pipefail

# ReVanced Builder - Environment Check
# Wrapper around scripts/lib/checks.sh

# Source utilities (which sources logger.sh and checks.sh)
source utils.sh

# Run full check
check_full_environment
