# AGENTS.md

Guidance for AI coding agents working in this repository.
Also linked via `CLAUDE.md` and `GEMINI.md` symlinks, and mirrored in `.github/copilot-instructions.md`.

---

## Project

**One-line description**: Automated APK patching system that downloads stock Android APKs and patches
them with ReVanced / RVX using a TOML-driven configuration.

**Primary languages**: Bash 4.0+ (build orchestration), Python 3.13+ (HTML/TOML parsing utilities)

**Frameworks / runtimes**: None (no web framework). Depends on Java 21+, Android SDK build-tools
34.0.0, ReVanced CLI (Java JAR), and standard POSIX utilities (`jq`, `zip`, `curl`).

**Package manager**: `uv` (Python). No Node package manager — Biome, yamlfmt, taplo, shfmt,
shellharden, shellcheck are installed as standalone binaries.

---

## Structure

```
@/                          Project root
├── build.sh                Main entry point — orchestrates full build pipeline
├── utils.sh                Module loader — source this, never individual libs
├── extras.sh               CI/CD helpers (separate-config, combine-logs)
├── check-env.sh            Validate prerequisites (wraps checks.sh)
├── config.toml             App build configuration (TOML, user-editable)
├── pyproject.toml          Python project metadata, Ruff + MyPy config
├── uv.lock                 Locked Python dependencies
├── .python-version         Pinned Python version (3.14 for local dev)
├── .editorconfig           Editor formatting rules (utf-8, LF, 2-space indent)
├── .shellcheckrc           ShellCheck disable list + enable=all
│
├── @/scripts/
│   ├── lint.sh             Unified linter runner (all languages, --fix mode)
│   ├── generate_matrix.sh  Emit GitHub Actions job matrix from config.toml
│   ├── dependency-checker.sh  Check CLI/patches/APK versions for updates
│   ├── release-manager.sh  GitHub release management helpers
│   ├── aapt2-optimize.sh   APK resource optimization via aapt2
│   ├── optimize-assets.sh  PNG/asset compression helpers
│   ├── apkmirror_search.py APKMirror HTML parser (selectolax)
│   ├── html_parser.py      Generic CSS-selector HTML scraper (stdin → stdout)
│   ├── toml_get.py         TOML → JSON converter (stdlib tomllib)
│   └── uptodown_search.py  Uptodown version-list HTML parser
│
├── @/scripts/lib/          Modular Bash libraries (loaded in order by utils.sh)
│   ├── logger.sh           pr / log_info / log_debug / log_warn / epr / abort / log
│   ├── helpers.sh          Version comparison, semver, arch normalization, HTML scraping wrappers
│   ├── config.sh           TOML parsing via toml_get.py (toml_prep / toml_get / toml_get_array_or_string)
│   ├── network.sh          HTTP with exponential backoff (req / gh_req / gh_dl)
│   ├── cache.sh            File-based build cache with TTL (cache_put / cache_is_valid)
│   ├── prebuilts.sh        Download ReVanced CLI + patch bundles from GitHub
│   ├── download.sh         APK acquisition: APKMirror → Uptodown → Archive.org fallback chain
│   ├── patching.sh         patch_apk / build_rv / _determine_version / _download_stock_apk
│   ├── app_processor.sh    Per-app config extraction and build job dispatch
│   └── checks.sh           check_system_tools / check_java_version / check_assets
│
├── @/tests/
│   ├── test_apkmirror_search.sh    Shell-based tests for APKMirror parser (6 cases)
│   ├── test-multi-source.sh        Multi-source config parsing tests (7 cases)
│   ├── test_uptodown_search.py     Python unittest for uptodown_search.py
│   ├── test_helpers_format_version.sh  Shell tests for format_version helper
│   ├── test_workflow_integration.sh    Integration tests
│   ├── test_zip_slip.sh            Security test for zip path traversal
│   ├── security_repro_zip_slip.py  Zip slip reproduction script
│   ├── benchmark_download.sh       Download performance benchmarks
│   ├── config-multi-source-test.toml   Test fixture
│   ├── config-single-source-test.toml  Test fixture
│   └── fixtures/apkmirror_mock.html    HTML test fixture
│
├── @/.github/
│   ├── workflows/build.yml           Reusable build workflow (matrix → release)
│   ├── workflows/build-daily.yml     Daily scheduled build at 06:00 UTC
│   ├── workflows/build-manual.yml    Manual trigger wrapper
│   ├── workflows/build-pr.yml        PR validation (syntax + tests + test build)
│   ├── workflows/lint.yml            Full lint suite on push/PR
│   ├── workflows/dependency-check.yml  Daily dep-version monitor
│   ├── workflows/jules-*.yml         Jules AI agent automation workflows
│   ├── actions/setup-environment/    Composite action: Java 25 + Android SDK + uv + Python
│   ├── dependabot.yml                Dependency update bot config
│   └── renovate.json                 Renovate bot config
│
├── @/bin/                  Bundled binary tools
│   ├── aapt2/               aapt2 cache dir (binaries fetched dynamically from GitHub)
│   ├── apksigner.jar       APK signing tool
│   ├── dexlib2.jar         DEX manipulation library
│   └── paccer.jar          ReVanced CLI helper
│
├── @/assets/
│   ├── ks.keystore         APK signing keystore
│   └── sig.txt             Known-good APK signatures for verification
│
└── @/docs/                 GitHub Pages documentation
    ├── generator.html      Interactive config generator (web UI)
    └── index.html          Project landing page
```

---

## Dev Workflow

### Prerequisites

```bash
# Required runtimes
java -version          # Must be 21+
jq --version           # JSON processing
curl --version         # HTTP client
zip --version          # APK packaging

# Required env vars (set in shell or CI secrets)
export KEYSTORE_PASSWORD="..."
export KEYSTORE_ENTRY_PASSWORD="..."
# Optional:
export KEYSTORE_PATH="assets/ks.keystore"   # default: ks.keystore
export KEYSTORE_ALIAS="jhc"                 # default: jhc
export GITHUB_TOKEN="..."                   # for GitHub API rate limits

# Python setup (use uv)
uv python install 3.14   # matches .python-version
uv sync --locked         # install all deps including dev
```

### Building

```bash
./build.sh config.toml           # Build all enabled apps
./build.sh sep_config.toml       # Build a separated single-app config
./build.sh clean                 # Remove temp/, build/, logs/, build.md
./build.sh cache stats           # Show build cache statistics
./build.sh cache cleanup         # Remove expired cache entries
./check-env.sh                   # Validate prerequisites only

# Generate single-app config for testing
./extras.sh separate-config config.toml Music-Extended sep_config.toml
```

Environment variable overrides:

```bash
BUILD_MODE=dev ./build.sh config.toml   # dev patches (default: stable)
LOG_LEVEL=0 ./build.sh config.toml      # debug output
```

### Linting

```bash
./scripts/lint.sh               # Check mode — all linters
./scripts/lint.sh --fix         # Auto-fix mode — all linters

# Individual linters
uv run ruff check .                       # Python lint (rules: ALL)
uv run ruff format --check .              # Python format check
uv run mypy --strict scripts/*.py         # Python type check (strict)
shellcheck --color=always $(find . -name "*.sh" ! -path "./.git/*")
shfmt -d -i 2 -bn -ci -sr <file.sh>      # Shell format check
taplo format --check                      # TOML format check
taplo lint                                # TOML lint
yamlfmt -dry .                            # YAML format check
biome check .                             # JSON/HTML/JS/CSS checks
```

### Testing

No unified test runner. Run individually:

```bash
./tests/test_apkmirror_search.sh       # APKMirror HTML parser (6 cases, standalone)
./tests/test-multi-source.sh           # Multi-source config parsing (7 cases)
./tests/test_helpers_format_version.sh # format_version helper (standalone)
./tests/test_workflow_integration.sh   # Integration tests
./tests/test_zip_slip.sh               # Zip slip security test
uv run python -m pytest tests/test_uptodown_search.py -v   # Python unit tests
```

### Syntax Checking

Always run after editing any shell script:

```bash
bash -n build.sh utils.sh extras.sh check-env.sh scripts/lib/*.sh scripts/*.sh
```

### Deploy / Release

Releases are automated via GitHub Actions:

1. Daily at 06:00 UTC: `build-daily.yml` checks for upstream updates, triggers `build.yml` if needed.
2. `build.yml` runs a matrix build (one job per app from `scripts/generate_matrix.sh`).
3. Each matrix job uploads APKs as artifacts, then `release` job combines them into a GitHub Release
   tagged `YY.MM.DD` (stable) or `YY.MM.DD-pre` (dev).

Manual trigger: Actions → "Daily Build" → `workflow_dispatch` → choose `stable` or `dev`.

---

## Conventions

### Bash

**Header** — every script must start with:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

**Variable naming**:

| Scope | Style | Example |
|-------|-------|---------|
| Globals / env vars | `UPPER_SNAKE_CASE` | `TEMP_DIR`, `BUILD_DIR` |
| Constants | `readonly UPPER_SNAKE_CASE` | `readonly MAX_RETRIES=4` |
| Internal globals | `__DOUBLE_UNDERSCORE__` | `__TOML__`, `__APKMIRROR_RESP__` |
| Locals | `lower_snake_case` + `local` | `local output_file` |

**Function naming**:

| Type | Style | Example |
|------|-------|---------|
| Public | `snake_case` | `build_rv`, `patch_apk` |
| Private | `_leading_underscore` | `_determine_version` |
| Validators | `check_*` / `validate_*` | `check_prerequisites` |
| Getters | `get_*` | `get_highest_ver` |

**Required patterns**:

```bash
[[ -n "$var" ]]                              # Use [[ ]] not [ ]
echo "${var}"                                # Always quote expansions
result=$(command)                            # $() not backticks
command -v tool >/dev/null 2>&1              # Tool existence check
mapfile -t arr < <(command)                  # Read arrays safely
read -ra arr <<< "$string"                   # Split string to array
```

**Forbidden**:

- `eval` — security risk, never use
- Unquoted variable expansions — `$var` without quotes
- `` `backtick` `` command substitution
- Piping curl directly to shell (`curl | bash`)
- Global variable pollution (always use `local` in functions)
- Direct sourcing of `scripts/lib/*.sh` — always use `source utils.sh`

**Module loading**:

```bash
source utils.sh   # Loads all libs in correct dependency order
```

Never `source scripts/lib/network.sh` directly — dependencies won't be satisfied.

### Python

- **Runtime**: Python 3.13+ (3.14 pinned in `.python-version`)
- **Formatter**: Ruff (`ruff format`) — double quotes, LF endings, 4-space indent
- **Linter**: Ruff with `select = ["ALL"]`. Key ignores: `E501` (line length), `T201` (print OK),
  `BLE001` (broad exception in CLI)
- **Type checker**: MyPy `--strict` — all function signatures must be typed
- **Docstrings**: Google style with `Args:`, `Returns:`, `Raises:` sections on public functions
- **Imports**: sorted by isort (via Ruff). First-party namespace: `scripts`
- **Exit codes**: 0 = success, 1 = general error, 2 = parse/version-check failure

### File Naming

| Type | Convention | Example |
|------|-----------|---------|
| Shell scripts | `kebab-case.sh` | `check-env.sh`, `release-manager.sh` |
| Python scripts | `snake_case.py` | `apkmirror_search.py`, `toml_get.py` |
| Documentation | `UPPERCASE.md` | `AGENTS.md`, `README.md` |
| Test configs | `*-test.toml` | `config-multi-source-test.toml` |

### Error Handling

```bash
abort "Fatal: reason"     # Red message → stderr, exits 1 — use for unrecoverable errors
epr "Non-fatal error"     # Red → stderr, execution continues
log_debug "Detail"        # Gray,   LOG_LEVEL=0 only
log_info "Info"           # Cyan,   LOG_LEVEL<=1 (default)
log_warn "Warning"        # Yellow, LOG_LEVEL<=2
pr "Success message"      # Green — use for progress/success
log "Build note"          # Appends to build.md (surfaced in release body)
```

Set `LOG_LEVEL=0` for verbose debug output.

### Network Requests

```bash
req "https://example.com/file" "output.apk"    # Auto-retry with backoff
gh_req "https://api.github.com/..."            # GitHub API (adds auth header)
gh_dl "https://github.com/.../release.zip"     # GitHub release download
```

`req` retries with delays: 0 s, 2 s, 4 s, 8 s, 16 s then fails. Config: `MAX_RETRIES=4`,
`INITIAL_RETRY_DELAY=2`, `CONNECTION_TIMEOUT=10`. Never call raw `curl`/`wget` directly.

### Config Access

```bash
source utils.sh
toml_prep "config.toml"                            # Load and parse TOML
local val=$(toml_get "$table" "key")               # Read scalar
local arr=$(toml_get_array_or_string "$table" "patches-source")  # String or array
local names=$(toml_get_table_names)                # List all app section names
```

TOML is converted to JSON via `scripts/toml_get.py` (Python `tomllib`). All parsed data lives in
the `__TOML__` global.

### Caching

```bash
if cache_is_valid "key" 3600; then              # Check TTL (seconds)
    cached=$(get_cache_path "key")
else
    # download/compute
    cache_put "key" "$output_file"
fi
```

Cache location: `temp/.cache/`. Always check cache before network requests.

### APK Signing

Signing uses v1+v2 signatures only — v3/v4 are explicitly disabled. Keystore config via env vars
`KEYSTORE_PASSWORD`, `KEYSTORE_ENTRY_PASSWORD`, `KEYSTORE_PATH`, `KEYSTORE_ALIAS`.

---

## Dependencies

### Python (runtime)

| Package | Purpose |
|---------|---------|
| `selectolax` | Fast HTML parsing (CSS selectors) — replaces htmlq binary |
| `requests` | Synchronous HTTP client |
| `httpx[http2]` | Async HTTP client with HTTP/2 support |
| `orjson` | Fast JSON serialization/deserialization |
| `asyncpraw` | Async Reddit API client (for update checks) |
| `uvloop` | Fast asyncio event loop |
| `aiofiles` | Async file I/O |

### Python (dev)

| Package | Purpose |
|---------|---------|
| `ruff>=0.9.0` | Linter + formatter (replaces flake8, isort, black) |
| `mypy>=1.15.0` | Static type checker |

### System / Runtime

| Tool | Version | Purpose |
|------|---------|---------|
| Java (Temurin) | 21+ (25 in CI) | Run ReVanced CLI JAR |
| Android SDK build-tools | 34.0.0 | `aapt2`, `zipalign`, `apksigner` |
| `jq` | any | JSON parsing in shell |
| `zip` / `unzip` | any | APK packaging |
| `curl` | any | HTTP (via `req` wrapper) |
| `uv` | latest | Python package manager |

### Linting tools (CI, installed as binaries)

| Tool | Version | Purpose |
|------|---------|---------|
| ShellCheck | 0.10.0 | Shell static analysis |
| shfmt | 3.10.0 | Shell formatter |
| shellharden | 4.3.1 | Shell hardening checker |
| yamllint | via uv | YAML linter |
| yamlfmt | 0.14.0 | YAML formatter |
| taplo | 0.9.3 | TOML formatter/linter |
| Biome | 2.3.11 | JSON/HTML/JS/CSS formatter/linter |

---

## Common Tasks

### Add a new app to build

1. Open `config.toml`; add a new `[AppName]` section:

   ```toml
   [MyApp]
   enabled = true
   app-name = "My App"
   patches-source = "ReVanced/revanced-patches"
   apkmirror-dlurl = "https://www.apkmirror.com/apk/developer/myapp/"
   ```

2. Consult available patches: `patches-source` accepts a GitHub `owner/repo` string or an array.
3. Run `./check-env.sh` to validate prerequisites.
4. Test: `./extras.sh separate-config config.toml MyApp sep.toml && ./build.sh sep.toml`

### Add a feature to the build pipeline

1. Identify which `scripts/lib/` module owns the concern (download, patching, config, etc.).
2. Read the target module fully; respect existing function naming conventions.
3. Add your function (private `_fn` or public `fn`); use `log_info`/`abort` for messages.
4. Load test: `bash -n scripts/lib/yourmodule.sh`
5. Run `./scripts/lint.sh` to catch style issues.
6. If the feature needs a test, add a test script in `tests/` following the existing patterns.

### Fix a bug in a shell library

1. `bash -n scripts/lib/<file>.sh` — confirm the file currently parses.
2. Edit the specific function using the `Edit` tool.
3. `bash -n scripts/lib/<file>.sh` again.
4. Run related tests: `./tests/test-multi-source.sh` or the relevant test script.
5. `./scripts/lint.sh` — must pass without new errors.

### Add a Python utility script

1. Create `scripts/my_utility.py` following the Google-docstring convention.
2. All public functions must have full type annotations.
3. Use `selectolax` for HTML, stdlib `tomllib` for TOML, `orjson` for JSON.
4. Add a `if __name__ == "__main__"` entry point with `argparse`.
5. Write tests in `tests/test_my_utility.py` using `unittest.TestCase`.
6. Run: `uv run python -m pytest tests/test_my_utility.py -v`
7. `uv run ruff check scripts/my_utility.py && uv run mypy --strict scripts/my_utility.py`

### Update Python dependencies

```bash
uv add package-name             # Add runtime dep
uv add --dev package-name       # Add dev dep
uv lock                         # Regenerate uv.lock
uv sync --locked                # Install updated lock
```

Commit both `pyproject.toml` and `uv.lock` together.

### Update tool versions in CI

Tool versions are pinned in `.github/workflows/lint.yml` (ShellCheck, shfmt, shellharden,
yamlfmt, taplo, Biome) and `.github/actions/setup-environment/action.yml` (Java, Android SDK).
Update the version strings and cache keys together.

---

## CI/CD

### On Pull Request (`build-pr.yml`)

Triggered on PRs to `main`/`master` touching `**.sh`, `**.toml`, `scripts/**`, `.github/workflows/**`.

1. **Syntax validation** — `bash -n` all shell scripts
2. **Automated tests** — `test-multi-source.sh`
3. **Test build** — separates first enabled app config and runs `build.sh` (expected to fail at
   signing without secrets; pipeline validates download + patching steps)
4. **Bot comment** — posts validation summary to the PR

### On PR / Push (`lint.yml`)

Triggered on push to `main`/`master` and all PRs touching code files.

| Job | Tools |
|-----|-------|
| Python | Ruff check + format |
| Shell | ShellCheck + shfmt + shellharden |
| YAML | yamllint + yamlfmt |
| TOML | taplo format + lint |
| Web | Biome check |

All jobs are `continue-on-error: true` — a lint failure does not block the build.

### On Merge to main (`build-daily.yml` + `build.yml`)

- **Daily at 06:00 UTC**: checks if upstream patches/CLI have new versions; skips if no updates.
- **`build.yml`** (reusable, called by daily/manual workflows):
  1. `setup_matrix` — runs `scripts/generate_matrix.sh` to produce per-app matrix
  2. `apk_matrix` — parallel jobs; each separates config, builds, uploads APKs as artifact
  3. `release` — downloads all APK artifacts, combines `build.md` logs, creates GitHub Release
     tagged `YY.MM.DD` (stable) or `YY.MM.DD-pre` (dev)

### Dependency monitoring (`dependency-check.yml`)

Runs daily at 00:00 UTC. Checks ReVanced CLI, patch bundle, and APK versions. Creates a GitHub
issue if updates are detected. Also triggered manually with scope options (`all`, `cli`, `patches`,
`apks`).

### Secrets required

| Secret | Purpose |
|--------|---------|
| `KEYSTORE_PASSWORD` | APK signing keystore password |
| `KEYSTORE_ENTRY_PASSWORD` | Keystore entry password |
| `GITHUB_TOKEN` | Auto-provided; used for API calls and releases |

---

## Tool Preferences

| Concern | Tool | Notes |
|---------|------|-------|
| Python package manager | `uv` | Lock file: `uv.lock`. Use `uv run` to exec scripts. |
| Python formatter | `ruff format` | Double quotes, LF, 4-space indent |
| Python linter | `ruff check` | Rules: ALL; see pyproject.toml for ignores |
| Python type checker | `mypy --strict` | Target Python 3.13 |
| Shell formatter | `shfmt -i 2 -bn -ci -sr` | 2-space indent, binary ops on new line |
| Shell linter | `shellcheck` | Config: `.shellcheckrc` |
| Shell hardener | `shellharden` | Check only in CI, `--replace` with --fix locally |
| YAML formatter | `yamlfmt` | |
| YAML linter | `yamllint` | |
| TOML formatter/linter | `taplo` | |
| JSON/HTML/CSS | `biome` | |
| JSON processing (shell) | `jq` | Never parse JSON with grep/sed |
| TOML parsing (shell) | `scripts/toml_get.py` | Via `toml_prep` / `toml_get` wrappers |
| HTML parsing | `selectolax` (Python) | Scripts in `scripts/*.py` |
| HTTP (shell) | `req` wrapper | Automatic retry, never raw curl |
| Git branches | `feature/desc`, `fix/desc`, `claude/desc-<session-id>` | |

---

## Key Rules for Agents

1. **Always `source utils.sh`** — never source `scripts/lib/*.sh` files directly.
2. **Use logging functions** (`log_info`, `epr`, `abort`) — never raw `echo`/`printf` for
   user-visible messages.
3. **Run `./scripts/lint.sh`** before committing any change.
4. **Run `bash -n <file>`** immediately after editing any shell script.
5. **Use `req` for HTTP** — never raw `curl`/`wget` without the retry wrapper.
6. **Cache aggressively** — call `cache_is_valid` before downloading anything.
7. **Never commit secrets** — use env vars and GitHub secrets.
8. **APK signing is v1+v2 only** — v3/v4 are disabled by design.
9. **Git branch naming**: `feature/description`, `fix/description`, `claude/description-<session-id>`.
10. **Prefer `jq`** for JSON, `toml_get` / Python `tomllib` for TOML, `selectolax` for HTML.
11. **Python version is 3.13+** (3.14 pinned locally) — do not use 3.11/3.12 APIs/syntax.
12. **Type everything** — all Python function signatures must have full type annotations.
13. **`eval` is banned** — find another approach.
14. **Multi-source patches**: `patches-source` can be a string or `["repo1", "repo2"]` array;
    version detection uses union strategy (highest version supported by ≥1 source).
