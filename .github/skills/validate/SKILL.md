---
name: validate
description: Run the narrowest ReVanced-auto validation for the files you changed.
allowed-tools: 'Read, Bash, Grep, Glob'
---

# Validate

Run only the repo checks that apply to the changed files.

## Triggers

Use this skill before reporting completion on ReVanced-auto changes.

## Steps

1. Identify the changed files and group them by type: Python, shell, workflows/YAML/TOML/JSON, or guidance docs.

2. Run the narrowest matching validation:

   **Python (`**/*.py`)**

   ```bash
   uv run ruff format --check <paths>
   uv run ruff check <paths>
   uv run python -m pytest <relevant-test-targets> -v
   ```

   Use the repo test mapping from `AGENTS.md` when picking pytest targets.

   **Shell (`**/*.sh`)**

   ```bash
   bash -n <paths>
   shellcheck <paths>
   ```

   Run `./scripts/lint.sh` as an additional repo check when the shell change is broad.

   **GitHub workflows (`.github/workflows/*.yml`)**

   ```bash
   actionlint <paths>
   ```

   **Other YAML / TOML / JSON changes**

   Run the relevant part of `./scripts/lint.sh` when the required tools are available in the environment.

   **Guidance docs (`.github/copilot-instructions.md`, `.github/instructions/*.instructions.md`, `.github/skills/*/SKILL.md`)**

   There is no dedicated markdown linter in this repo. Verify that referenced commands and paths exist, and validate any touched workflows separately with `actionlint`.

3. Fix issues in the changed files only. Report unrelated pre-existing failures instead of broadening the change.

4. Re-run the affected check before reporting success.

## Invariants

- Never remove or skip a check to make it pass.
- Do not modify test files to suppress failures unless the test itself is wrong.
- Report pre-existing failures that are unrelated to your changes.
