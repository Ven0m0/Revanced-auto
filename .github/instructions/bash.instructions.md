---
applyTo: "**/*.sh"
---

# Bash Standards

## Header

Every script must start with:
```bash
#!/usr/bin/env bash
set -euo pipefail
```

## Repo Conventions

- Load shared helpers via `source utils.sh` — never source `scripts/lib/*.sh` directly
- Use repo logging helpers (`log_info`, `log_warn`, `log_debug`, `pr`, `epr`, `abort`) instead of raw `echo`/`printf` for user-facing output
- Use `req` / `gh_req` for network access instead of raw `curl`/`wget` in runtime logic

## Style Rules

- Quote all variable expansions: `"${var}"`, `"$@"`, `"${array[@]}"`
- Use `mapfile -t arr < <(cmd)` for array population
- Use `VAR=$((VAR + 1))` for arithmetic (not `let` or `expr`)
- Never use `eval`
- Prefer `[[ ]]` over `[ ]` for conditionals

## Validation

- Run `bash -n script.sh` on every changed `.sh` file before committing
- Run `./scripts/lint.sh` to check ShellCheck + shfmt + shellharden

## Forbidden

- `eval` — never under any circumstance
- Raw `curl`/`wget` in build/runtime logic — use `req`/`gh_req` wrappers
- Direct sourcing of `scripts/lib/*.sh` — use `source utils.sh`
- Unquoted expansions that may glob or split
