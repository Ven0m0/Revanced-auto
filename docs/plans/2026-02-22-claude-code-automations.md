# Claude Code Automations Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add four Claude Code automations: two hookify lint rules, a security-reviewer subagent, and a run-tests skill.

**Architecture:** Hookify rules live in `~/.claude/settings.json` (user-level, so they fire across all projects); the subagent and skill are project-scoped under `.claude/agents/` and `.claude/skills/`. GitHub MCP is already installed (plugin enabled + token in env — skip it).

**Tech Stack:** Claude Code hooks (PostToolUse), hookify plugin, ShellCheck, shfmt, Ruff, MyPy (strict)

---

## Status

- [x] GitHub MCP — already installed via `github@claude-plugins-official` plugin with token in env
- [ ] Task 1: Hookify rule — shell lint
- [ ] Task 2: Hookify rule — Python lint
- [ ] Task 3: Security reviewer subagent
- [ ] Task 4: Run-tests skill

---

## Task 1: Hookify rule — shell script auto-lint

**Files:**
- Modify: `~/.claude/settings.json` (user-level, via hookify plugin)

**What it does:** After any Edit or Write to a `.sh` file, run ShellCheck + shfmt and surface any failures.

**Step 1: Invoke the hookify skill**

```
Use the hookify:hookify skill with this input:
"When I edit a .sh file, run shellcheck and shfmt on it"
```

Hookify will generate a rule. When prompted for specifics, provide:
- **Trigger**: PostToolUse on Edit or Write
- **File filter**: `*.sh`
- **Command**: `shellcheck --color=always "$CLAUDE_TOOL_INPUT_FILE" && shfmt -d -i 2 -bn -ci -sr "$CLAUDE_TOOL_INPUT_FILE"`

**Step 2: Verify rule was written**

```bash
cat ~/.claude/settings.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d.get('hooks', {}), indent=2))"
```

Expected: A PostToolUse entry targeting Edit/Write with a shellcheck command.

**Step 3: Smoke-test the rule**

Edit one line of `utils.sh` (e.g., add a comment), save, and watch for ShellCheck output in the Claude Code terminal. If you see `In utils.sh line N:` or `shfmt: ...` output, it's working.

Expected: Either clean output (no issues found) or ShellCheck findings listed.

**Step 4: Commit**

```bash
cd /home/ven0m0/projects/Revanced-auto
git add -p  # review; nothing to add here — hookify edits ~/.claude/settings.json not the repo
```

No repo commit needed (user-level config). Note it in git log as done.

---

## Task 2: Hookify rule — Python auto-lint

**Files:**
- Modify: `~/.claude/settings.json` (user-level, via hookify plugin)

**What it does:** After any Edit or Write to a `.py` file, run Ruff check + mypy strict.

**Step 1: Invoke the hookify skill**

```
Use the hookify:hookify skill with this input:
"When I edit a .py file, run ruff check and mypy --strict on it"
```

When prompted for specifics:
- **Trigger**: PostToolUse on Edit or Write
- **File filter**: `*.py`
- **Command**: `ruff check "$CLAUDE_TOOL_INPUT_FILE" && mypy --strict "$CLAUDE_TOOL_INPUT_FILE"`

**Step 2: Verify rule was written**

```bash
cat ~/.claude/settings.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d.get('hooks', {}), indent=2))"
```

Expected: Second PostToolUse entry targeting `*.py` with ruff + mypy.

**Step 3: Smoke-test the rule**

Edit `scripts/toml_get.py` (add or remove a blank line), save. Expect ruff + mypy output in the terminal (likely clean, since the file is already compliant).

**Step 4: No repo commit needed**

User-level config. Move on.

---

## Task 3: Security reviewer subagent

**Files:**
- Create: `.claude/agents/security-reviewer.md`

**What it does:** A read-only subagent specialized in catching the security issues that have historically hit this repo: path traversal (zip-slip, user-controlled filenames), insecure curl patterns, unquoted expansions, and `eval` usage.

**Step 1: Create the agents directory**

```bash
mkdir -p /home/ven0m0/projects/Revanced-auto/.claude/agents
```

**Step 2: Write the subagent file**

Create `.claude/agents/security-reviewer.md` with this exact content:

```markdown
---
name: security-reviewer
description: Security review specialist for this Bash/Python APK patching system. Invoke when editing download.sh, network.sh, patching.sh, or any code that handles user-controlled paths, archive extraction, or external network requests. Proactively checks for path traversal, insecure curl, command injection, and credential leaks.
color: red
tools: Read, Glob, Grep
---

You are a security reviewer for a Bash automation system that downloads and patches Android APKs.
This repo has had path traversal fixes (zip-slip in archive extraction) and insecure curl usage
(piping to shell). Your job is to catch these before they merge.

## What to Check

### Path Traversal
- Archive extraction: is the extracted filename sanitized before use as a path?
- User-controlled input used in file paths (e.g., package names from APKMirror responses)
- Variables derived from network responses used in `cp`, `mv`, `mkdir`, or redirection targets

### Insecure Network Patterns
- `curl ... | bash` or `curl ... | sh` — absolutely forbidden
- `curl` without `--fail` — silent failures hide errors
- Raw `curl`/`wget` instead of `req` function (bypasses retry + error handling)
- Unvalidated redirect following

### Command Injection
- Unquoted variable expansions in commands: `cp $file dest` instead of `cp "${file}" dest`
- Variables from external sources used in command arguments without sanitization
- `eval` usage (forbidden per AGENTS.md)

### Credential Leaks
- Secrets hardcoded in scripts (tokens, passwords, API keys)
- Secrets echoed to logs or written to temp files
- Env vars printed in debug output

## How to Report

For each finding, state:
1. **File and line number**
2. **Vulnerability type**
3. **Exact vulnerable code**
4. **Suggested fix**

If nothing is found, say: "No security issues found in the reviewed code."

## Reference

AGENTS.md rules: no `eval`, always quote `"${var}"`, use `req` not raw curl, never pipe curl to shell.
```

**Step 3: Verify the file syntax**

```bash
head -10 /home/ven0m0/projects/Revanced-auto/.claude/agents/security-reviewer.md
```

Expected: YAML frontmatter with `name`, `description`, `color`, `tools` fields.

**Step 4: Smoke-test the subagent**

In a Claude Code session in this repo, ask: "Use the security-reviewer agent to check scripts/lib/download.sh"

Expected: The agent runs, reads download.sh with Read tool, and reports findings or "No security issues found."

**Step 5: Commit**

```bash
cd /home/ven0m0/projects/Revanced-auto
git add .claude/agents/security-reviewer.md
git commit -m "feat: add security-reviewer subagent for Claude Code

Reviews shell scripts for path traversal, insecure curl, command
injection, and credential leaks. Read-only agent using Grep/Read.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Run-tests skill

**Files:**
- Create: `.claude/skills/run-tests.md`

**What it does:** A user-invocable slash command `/run-tests [suite]` that knows where all the scattered test scripts live and how to run them.

**Step 1: Confirm which test files exist**

```bash
ls /home/ven0m0/projects/Revanced-auto/tests/
```

Note any `.sh` files found — the plan below lists the currently known ones.

**Step 2: Create the skills directory**

```bash
mkdir -p /home/ven0m0/projects/Revanced-auto/.claude/skills
```

**Step 3: Write the skill file**

Create `.claude/skills/run-tests.md` with this content (update the test list if Step 1 revealed others):

```markdown
---
name: run-tests
description: Run the project test suite. Usage: /run-tests [suite]. Available suites: apkmirror, multi-source, helpers, zip-slip, benchmark, all. Runs syntax check on all shell files too.
disable-model-invocation: true
---

Run tests for this Revanced-auto project. The tests are individual scripts — there is no unified test runner.

## Available Suites

| Suite name | Script | Notes |
|------------|--------|-------|
| `apkmirror` | `./tests/test_apkmirror_search.sh` | 6 cases, standalone |
| `multi-source` | `./tests/test-multi-source.sh` | 7 cases, needs source utils.sh |
| `helpers` | `./tests/test_helpers_format_version.sh` | standalone |
| `zip-slip` | `./tests/test_zip_slip.sh` | standalone |
| `benchmark` | `./tests/benchmark_download.sh` | performance, standalone |
| `all` | Run all of the above, then syntax check | see below |

## Running a Single Suite

```bash
cd /path/to/revanced-auto
bash tests/<script>.sh
```

## Running All Suites

```bash
cd /path/to/revanced-auto
bash tests/test_apkmirror_search.sh
bash tests/test-multi-source.sh
bash tests/test_helpers_format_version.sh
bash tests/test_zip_slip.sh
bash tests/benchmark_download.sh
```

Then run syntax check on all shell scripts:

```bash
bash -n build.sh && bash -n utils.sh && bash -n extras.sh && bash -n check-env.sh && bash -n scripts/lib/*.sh
echo "All syntax checks passed"
```

## Interpreting Results

- Tests print PASS/FAIL per case. A non-zero exit code means failure.
- `benchmark_download.sh` prints timing stats — no pass/fail, just data.
- Syntax check (`bash -n`) produces no output on success; errors include line numbers.
```

**Step 4: Verify the frontmatter**

```bash
head -8 /home/ven0m0/projects/Revanced-auto/.claude/skills/run-tests.md
```

Expected: `---` block with `name: run-tests`, `description: ...`, `disable-model-invocation: true`.

**Step 5: Smoke-test the skill**

In Claude Code, type `/run-tests apkmirror`. Claude should run `bash tests/test_apkmirror_search.sh` and report the output.

**Step 6: Commit**

```bash
cd /home/ven0m0/projects/Revanced-auto
git add .claude/skills/run-tests.md
git commit -m "feat: add run-tests skill for Claude Code

Slash command /run-tests [suite] maps suite names to the scattered
test scripts. Includes syntax check step for all shell files.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Verification Checklist

After all tasks complete:

```bash
# 1. Check hookify rules are in settings
cat ~/.claude/settings.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d.get('hooks', {}), indent=2))"
# Expected: PostToolUse entries for .sh and .py files

# 2. Check agent file exists and has valid frontmatter
head -6 /home/ven0m0/projects/Revanced-auto/.claude/agents/security-reviewer.md
# Expected: YAML frontmatter with name, description, color, tools

# 3. Check skill file exists and has valid frontmatter
head -6 /home/ven0m0/projects/Revanced-auto/.claude/skills/run-tests.md
# Expected: YAML frontmatter with name, description, disable-model-invocation

# 4. Confirm git log
git -C /home/ven0m0/projects/Revanced-auto log --oneline -5
# Expected: commits for security-reviewer and run-tests

# 5. GitHub MCP (already done)
# github@claude-plugins-official is enabled and GITHUB_PERSONAL_ACCESS_TOKEN is set
```
