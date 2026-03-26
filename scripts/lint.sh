#!/usr/bin/env bash
set -euo pipefail
# Unified linting script for all file types
# Usage: ./scripts/lint.sh [--fix]
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"
FIX_MODE=false
EXIT_CODE=0
# Parse arguments
if [[ "${1:-}" == "--fix" ]]; then
  FIX_MODE=true
fi
# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
log_section() {
  echo -e "\n${BLUE}==>${NC} $1"
}
log_success() {
  echo -e "${GREEN}✓${NC} $1"
}
log_error() {
  echo -e "${RED}✗${NC} $1"
}
log_warn() {
  echo -e "${YELLOW}!${NC} $1"
}
check_command() {
  if ! command -v "$1" &> /dev/null; then
    log_warn "$1 not found, skipping $2 checks"
    return 1
  fi
  return 0
}
# ============================================================================
# Python - Ruff
# ============================================================================
log_section "Python (Ruff)"
if check_command "ruff" "Python"; then
  PYTHON_FILES=$(find . -name "*.py" -not -path "./.git/*" -not -path "./build/*" -not -path "./temp/*" 2> /dev/null || true)
  if [[ -n "$PYTHON_FILES" ]]; then
    if [[ "$FIX_MODE" == true ]]; then
      if ruff check --fix . && ruff format .; then
        log_success "Python files formatted and linted"
      else
        log_error "Python linting failed"
        EXIT_CODE=1
      fi
    else
      if ruff check . && ruff format --check .; then
        log_success "Python files pass linting"
      else
        log_error "Python linting failed"
        EXIT_CODE=1
      fi
    fi
  else
    log_warn "No Python files found"
  fi
fi
# ============================================================================
# Python - MyPy (Type Checking)
# ============================================================================
log_section "Python Type Checking (MyPy)"
if check_command "mypy" "Python Type Checker"; then
  PYTHON_FILES=$(find . -name "*.py" -not -path "./.git/*" -not -path "./build/*" -not -path "./temp/*" -not -path "./.venv/*" -not -path "./venv/*" 2> /dev/null || true)
  if [[ -n "$PYTHON_FILES" ]]; then
    if mypy --strict scripts/*.py; then
      log_success "Python type checking passed"
    else
      log_error "Python type checking failed"
      EXIT_CODE=1
    fi
  else
    log_warn "No Python files found"
  fi
fi
# ============================================================================
# Shell - ShellCheck, shfmt, shellharden
# ============================================================================
log_section "Shell Scripts"
SHELL_FILES=()
mapfile -t SHELL_FILES < <(find . -name "*.sh" -not -path "./.git/*" -not -path "./build/*" -not -path "./temp/*" 2> /dev/null || true)
if [[ ${#SHELL_FILES[@]} -gt 0 ]]; then
  # ShellCheck
  if check_command "shellcheck" "ShellCheck"; then
    if shellcheck --color=always "${SHELL_FILES[@]}"; then
      log_success "ShellCheck passed"
    else
      log_error "ShellCheck failed"
      EXIT_CODE=1
    fi
  fi
  # shfmt (exclude files with complex regex that confuse shfmt parser)
  if check_command "shfmt" "shfmt"; then
    SHFMT_FILES=()
    for f in "${SHELL_FILES[@]}"; do
      [[ "$f" == *changelog-generator.sh ]] || SHFMT_FILES+=("$f")
    done
    if [[ ${#SHFMT_FILES[@]} -gt 0 ]]; then
      if [[ "$FIX_MODE" == true ]]; then
        if shfmt -w -i 2 -bn -ci -sr "${SHFMT_FILES[@]}"; then
          log_success "Shell scripts formatted with shfmt"
        else
          log_error "shfmt failed"
          EXIT_CODE=1
        fi
      else
        if shfmt -d -i 2 -bn -ci -sr "${SHFMT_FILES[@]}"; then
          log_success "Shell scripts pass shfmt"
        else
          log_error "shfmt check failed"
          EXIT_CODE=1
        fi
      fi
    fi
  fi
  # shellharden
  if check_command "shellharden" "shellharden"; then
    if [[ "$FIX_MODE" == true ]]; then
      for file in "${SHELL_FILES[@]}"; do
        if shellharden --replace "$file"; then
          log_success "Hardened: $file"
        else
          log_error "shellharden failed on: $file"
          EXIT_CODE=1
        fi
      done
    else
      sh_pass=true
      for file in "${SHELL_FILES[@]}"; do
        shellharden --check "$file" 2> /dev/null || sh_pass=false
      done
      if "$sh_pass"; then
        log_success "Shell scripts pass shellharden"
      else
        log_warn "shellharden suggests improvements (run with --fix to apply)"
      fi
    fi
  fi
else
  log_warn "No shell scripts found"
fi
# ============================================================================
# YAML - yamllint, yamlfmt
# ============================================================================
log_section "YAML Files"
YAML_FILES=$(find . \( -name "*.yml" -o -name "*.yaml" \) -not -path "./.git/*" -not -path "./build/*" -not -path "./temp/*" 2> /dev/null || true)
if [[ -n "$YAML_FILES" ]]; then
  # yamllint
  if check_command "yamllint" "yamllint"; then
    if echo "$YAML_FILES" | xargs yamllint; then
      log_success "YAML files pass yamllint"
    else
      log_error "yamllint failed"
      EXIT_CODE=1
    fi
  fi
  # yamlfmt
  if check_command "yamlfmt" "yamlfmt"; then
    if [[ "$FIX_MODE" == true ]]; then
      if yamlfmt -w .; then
        log_success "YAML files formatted with yamlfmt"
      else
        log_error "yamlfmt failed"
        EXIT_CODE=1
      fi
    else
      if yamlfmt -dry .; then
        log_success "YAML files pass yamlfmt"
      else
        log_error "yamlfmt check failed"
        EXIT_CODE=1
      fi
    fi
  fi
else
  log_warn "No YAML files found"
fi
# ============================================================================
# TOML - taplo
# ============================================================================
log_section "TOML Files"
TOML_FILES=$(find . -name "*.toml" -not -path "./.git/*" -not -path "./build/*" -not -path "./temp/*" 2> /dev/null || true)
if [[ -n "$TOML_FILES" ]]; then
  if check_command "taplo" "TOML"; then
    if [[ "$FIX_MODE" == true ]]; then
      if taplo format; then
        log_success "TOML files formatted with taplo"
      else
        log_error "taplo format failed"
        EXIT_CODE=1
      fi
    else
      if taplo format --check; then
        log_success "TOML files pass taplo"
      else
        log_error "taplo check failed"
        EXIT_CODE=1
      fi
    fi
    if taplo lint; then
      log_success "TOML files pass taplo lint"
    else
      log_error "taplo lint failed"
      EXIT_CODE=1
    fi
  fi
else
  log_warn "No TOML files found"
fi
# ============================================================================
# JSON/HTML/JS/TS/CSS - Biome
# ============================================================================
log_section "JSON/HTML/JS/TS/CSS (Biome)"
if check_command "biome" "JSON/HTML/JS/TS/CSS"; then
  if [[ "$FIX_MODE" == true ]]; then
    if biome check --write .; then
      log_success "Biome check and format completed"
    else
      log_error "Biome failed"
      EXIT_CODE=1
    fi
  else
    if biome check .; then
      log_success "Files pass Biome checks"
    else
      log_error "Biome check failed"
      EXIT_CODE=1
    fi
  fi
fi
# ============================================================================
# Summary
# ============================================================================
echo ""
echo "========================================"
if [[ $EXIT_CODE -eq 0 ]]; then
  log_success "All linting checks passed!"
else
  log_error "Some linting checks failed"
  if [[ "$FIX_MODE" == false ]]; then
    echo ""
    echo "Run with --fix to automatically fix issues:"
    echo "  ./scripts/lint.sh --fix"
  fi
fi
echo "========================================"
exit "$EXIT_CODE"
