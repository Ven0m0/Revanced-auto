# Claude Code Automations — Design

**Date**: 2026-02-22
**Status**: Approved
**Scope**: Add four Claude Code automations to the Revanced-auto project

---

## What We're Building

Four automation components to improve the development workflow for this Bash/Python APK patching system:

1. **Hookify rules** — auto-lint shell and Python files on edit
2. **security-reviewer subagent** — specialized agent for catching path traversal, injection, insecure curl
3. **run-tests skill** — slash command to run the scattered test suite
4. **GitHub MCP server** — install for workflow/PR/issue management

---

## Component Designs

### 1. Hookify Rules (2 rules)

**Shell lint rule** — triggers on PostToolUse(Edit|Write) for `*.sh` files.
Runs: `shellcheck --color=always "$file" && shfmt -d -i 2 -bn -ci -sr "$file"`

**Python lint rule** — triggers on PostToolUse(Edit|Write) for `*.py` files.
Runs: `ruff check "$file" && mypy --strict "$file"`

Both rules are created via the `hookify:hookify` skill using conversational input.
Config stored in `.claude/settings.json` under `hooks.PostToolUse`.

### 2. Security Reviewer Subagent

**File**: `.claude/agents/security-reviewer.md`
**Tools**: Read, Glob, Grep (read-only — no edits)
**Trigger**: When editing download.sh, network.sh, or any code handling user-controlled paths or external network requests.

Checks for:
- Path traversal (zip-slip, user-controlled extraction paths)
- Insecure curl patterns (piping to shell, missing `--fail`)
- Unquoted variable expansions in shell
- Hardcoded credentials or secrets
- `eval` usage

### 3. Run-Tests Skill

**File**: `.claude/skills/run-tests.md`
**Invocation**: User-only (`disable-model-invocation: true`)
**Usage**: `/run-tests [suite]`

Maps suite names to test scripts:
- `apkmirror` → `./tests/test_apkmirror_search.sh`
- `multi-source` → `./tests/test-multi-source.sh`
- `helpers` → `./tests/test_helpers_format_version.sh`
- `zip-slip` → `./tests/test_zip_slip.sh`
- `all` → run all suites + syntax check all `.sh` files

### 4. GitHub MCP Server

**Package**: `@modelcontextprotocol/server-github` (official Anthropic MCP)
**Install**: `claude mcp add github -- npx -y @modelcontextprotocol/server-github`
**Requires**: `GITHUB_PERSONAL_ACCESS_TOKEN` env var
**Scope**: User-level (personal token, not committed to repo)

---

## File Inventory

| File | Action |
|------|--------|
| `.claude/settings.json` | Modified — hookify rules added |
| `.claude/agents/security-reviewer.md` | Created |
| `.claude/skills/run-tests.md` | Created |
| GitHub MCP | Installed via CLI |

---

## Success Criteria

- Editing any `.sh` file triggers ShellCheck + shfmt output automatically
- Editing any `.py` file triggers Ruff + mypy output automatically
- `/run-tests all` runs all 4 test suites and reports results
- `security-reviewer` agent appears in agent list and activates on relevant files
- `gh mcp list` shows the GitHub server connected
