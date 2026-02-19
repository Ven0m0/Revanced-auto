#!/usr/bin/env bash
source ./utils.sh
ROOT_DIR=$PWD
WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT
gh_dl() { return 0; }
java() { return 0; }
cd "$WORK_DIR"
export CWD="$WORK_DIR"
export TEMP_DIR="$WORK_DIR/temp"
mkdir -p "$TEMP_DIR"
uv run "$ROOT_DIR/tests/security_repro_zip_slip.py" "malicious.mzip"
if merge_splits "malicious" "output.apk"; then
    echo "FAIL: merge_splits succeeded on malicious zip (Vulnerable)"
ls -R "$WORK_DIR"
    if [[ -f "$WORK_DIR/evil.txt" ]]; then
        echo "CONFIRMED: Zip Slip executed successfully"
    fi
    exit 1
else
    echo "PASS: merge_splits failed safely (Secure)"
    exit 0
fi
