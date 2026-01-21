# Linting and Formatting Guide

This project uses comprehensive linting and formatting tools to maintain code quality and consistency across all file types.

## Quick Start

```bash
# Check all files
make lint

# Auto-fix all issues
make format

# Install all tools
make install-tools

# Set up pre-commit hooks (recommended)
make setup-pre-commit
```

## Tools by File Type

### Python (.py)
- **Tool**: [Ruff](https://docs.astral.sh/ruff/)
- **Purpose**: Fast Python linter and formatter (replaces black, isort, flake8, etc.)
- **Config**: `pyproject.toml`
- **Install**: `pip install ruff`
- **Usage**:
  ```bash
  ruff check .              # lint
  ruff check --fix .        # fix
  ruff format .             # format
  ```

### Shell Scripts (.sh)
- **Tools**:
  - [ShellCheck](https://www.shellcheck.net/) - Static analysis
  - [shfmt](https://github.com/mvdan/sh) - Formatter
  - [shellharden](https://github.com/anordal/shellharden) - Hardening
- **Config**: `.shellcheckrc`, `.editorconfig`
- **Install**:
  ```bash
  # ShellCheck (Ubuntu/Debian)
  sudo apt-get install shellcheck

  # shfmt
  go install mvdan.cc/sh/v3/cmd/shfmt@latest

  # shellharden
  cargo install shellharden
  ```
- **Usage**:
  ```bash
  shellcheck *.sh           # lint
  shfmt -w -i 2 *.sh        # format
  shellharden --replace *.sh # harden
  ```

### YAML (.yml, .yaml)
- **Tools**:
  - [yamllint](https://yamllint.readthedocs.io/) - Linter
  - [yamlfmt](https://github.com/google/yamlfmt) - Formatter
- **Config**: `.yamllint.yml`, `.yamlfmt`
- **Install**:
  ```bash
  pip install yamllint
  go install github.com/google/yamlfmt/cmd/yamlfmt@latest
  ```
- **Usage**:
  ```bash
  yamllint .                # lint
  yamlfmt -w .              # format
  ```

### TOML (.toml)
- **Tool**: [Taplo](https://taplo.tamasfe.dev/)
- **Purpose**: TOML linter and formatter
- **Config**: `.taplo.toml`
- **Install**: `cargo install taplo-cli --locked`
- **Usage**:
  ```bash
  taplo format              # format
  taplo lint                # lint
  ```

### JSON/HTML/JS/TS/CSS
- **Tool**: [Biome](https://biomejs.dev/)
- **Purpose**: Fast formatter and linter for web files
- **Config**: `biome.json`
- **Install**: `npm install -g @biomejs/biome`
- **Usage**:
  ```bash
  biome check .             # lint
  biome check --write .     # fix
  ```

## Configuration Files

All configuration files are in the project root:

```
.
├── pyproject.toml              # Ruff (Python)
├── .shellcheckrc               # ShellCheck
├── .editorconfig               # Editor settings (all file types)
├── .yamllint.yml               # yamllint
├── .yamlfmt                    # yamlfmt
├── .taplo.toml                 # Taplo (TOML)
├── biome.json                  # Biome (JSON/HTML/JS/TS/CSS)
└── .pre-commit-config.yaml     # Pre-commit hooks
```

## Pre-commit Hooks

Pre-commit hooks automatically run linters before each commit.

### Setup

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
make setup-pre-commit

# Or manually
pre-commit install
```

### Usage

```bash
# Hooks run automatically on git commit

# Run manually on all files
pre-commit run --all-files

# Run specific hook
pre-commit run ruff --all-files

# Skip hooks (not recommended)
git commit --no-verify
```

## CI/CD Integration

The project has GitHub Actions workflows for automated linting:

- **`.github/workflows/lint.yml`** - Comprehensive linting for all file types
- **`.github/workflows/shellcheck.yml`** - Shell script specific checks

These run on:
- Push to main/master
- Pull requests
- Manual trigger (workflow_dispatch)

## Editor Integration

### VS Code

Install extensions:
- [Ruff](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff)
- [ShellCheck](https://marketplace.visualstudio.com/items?itemName=timonwong.shellcheck)
- [YAML](https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml)
- [Biome](https://marketplace.visualstudio.com/items?itemName=biomejs.biome)

The `.editorconfig` file ensures consistent formatting across editors.

### Other Editors

- **Vim/Neovim**: Use ALE or nvim-lspconfig with respective LSPs
- **Emacs**: Use flycheck or lsp-mode
- **Sublime Text**: Install SublimeLinter with respective plugins

## Troubleshooting

### Tool not found

If you get "command not found" errors:

```bash
# Install all tools
make install-tools

# Or install individually (see tool-specific sections above)
```

### Pre-commit hooks failing

```bash
# Update hooks
pre-commit autoupdate

# Clean and reinstall
pre-commit clean
pre-commit install
```

### False positives

For tool-specific false positives, you can:

1. **Add inline ignores** (use sparingly):
   ```python
   # Python (Ruff)
   foo = bar  # noqa: F841
   ```
   ```bash
   # Shell (ShellCheck)
   # shellcheck disable=SC2034
   foo=bar
   ```

2. **Update config files** to adjust rules globally

3. **Exclude files** via config or `.gitignore`

## Best Practices

1. **Run locally first**: Use `make format` before committing
2. **Enable pre-commit hooks**: Catch issues early
3. **Don't disable checks without reason**: If a tool flags something, it's usually important
4. **Keep configs updated**: Tools evolve, configs should too
5. **CI is the source of truth**: Local checks should match CI

## Getting Help

- **Tool Documentation**:
  - [Ruff Docs](https://docs.astral.sh/ruff/)
  - [ShellCheck Wiki](https://www.shellcheck.net/wiki/)
  - [Biome Docs](https://biomejs.dev/)
  - [Taplo Docs](https://taplo.tamasfe.dev/)

- **Project Issues**: Check existing issues or create new ones on GitHub

## Performance

All tools are chosen for speed:
- **Ruff**: 10-100x faster than traditional Python linters
- **Biome**: Faster than Prettier/ESLint
- **shfmt**: Fast Go-based formatter
- **Taplo**: Native Rust performance

Running `make lint` on the entire codebase typically takes < 5 seconds.
