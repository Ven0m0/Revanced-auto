---
name: copilot-init
description: Refresh ReVanced-auto Copilot bootstrap assets so agents can set up Python, Java, Android, and repo tooling from the repository itself.
allowed-tools: 'Read, Write, Edit, Glob, Grep, Bash'
---

# Copilot init

Refresh the Copilot bootstrap files for ReVanced-auto. Keep `AGENTS.md` as the canonical long-form guide, keep `.github/copilot-instructions.md` short, and only update assets that are stale or inaccurate.

## Goal

- Ensure `.github/workflows/copilot-setup-steps.yml` matches the real setup path:
  - Java 21+
  - Android SDK build-tools 34.0.0
  - `mise install`
  - `uv sync --locked --all-groups`
  - pinned `bin/*.jar` bootstrap via `utils.sh`
- Keep `.github/copilot-instructions.md` aligned with `AGENTS.md` without duplicating it.
- Keep `.github/instructions/*.instructions.md` and `.github/skills/*/SKILL.md` repo-specific and concise.

## Audit first

- Read `AGENTS.md`, `.github/copilot-instructions.md`, `pyproject.toml`, `mise.toml`, `scripts/lint.sh`, and `check-env.sh`.
- Inspect existing `.github/workflows/*.yml`, `.github/instructions/*.instructions.md`, and `.github/skills/*/SKILL.md`.
- Prefer current code and config over README prose when commands disagree.

## Repository invariants

- Primary interface is `python -m scripts.cli`; `build.sh` is legacy compatibility only.
- Python is `uv`-managed and targets 3.13+.
- Runtime setup also needs Java 21+, Android SDK support, and the pinned jar bootstrap in `bin/`.
- Reuse existing workflows and guidance when they already cover the repo.

## Update scope

- Prefer updating:
  - `.github/workflows/copilot-setup-steps.yml`
  - `.github/copilot-instructions.md`
  - `.github/skills/*/SKILL.md`
- Only touch `.github/instructions/*.instructions.md` when a repo-specific rule is missing or incorrect.
- Do not introduce workflows for languages or tools the repo does not use.

## Validation

- Verify every referenced command and path exists in the repo.
- For workflow changes, run `actionlint` on the edited workflow.
- For guidance-only changes, do not claim code or runtime validation you did not run.
