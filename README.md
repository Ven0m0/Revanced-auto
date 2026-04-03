# ReVanced-auto

ReVanced-auto builds patched Android APKs from a TOML config: resolve compatible app versions, download stock APKs, apply ReVanced/RVX-compatible CLI + patches, re-sign the result, and write artifacts to `build/`.

## Requirements

- Python **3.13+**
- Java **21+**
- `uv`, `jq`, `zip`
- Optional but useful: `curl` or `wget`, `zipalign`, `optipng`

This repo uses `uv` for dependency management and is not distributed as a standalone Python package.

## Setup

```bash
git clone <repo-url>
cd Revanced-auto
mise install
uv sync --locked --all-groups
bash ./check-env.sh
```

`check-env.sh` verifies required tools, Java, downloads the required `bin/` jars when missing, checks optional helpers and assets, and validates `config.toml` syntax.

## Quick start

Prefer the Python CLI. After `uv sync`, use `uv run ...` for one-off commands, or activate the `uv` environment first if you are working in an interactive shell session.

```bash
# Prefer a secure secret source over typing passwords into shell history.
export KEYSTORE_PASSWORD='...'
export KEYSTORE_ENTRY_PASSWORD='...'

bash ./check-env.sh
uv run python -m scripts.cli check --config config.toml
uv run python -m scripts.cli build --config config.toml --build-mode apk --parallel 1
```

The CLI builds every app with `enabled = true` in `config.toml`. To rebuild when nothing changed, reset the version tracker first:

```bash
uv run python -m scripts.cli version-tracker reset --config config.toml
```

Useful variants:

```bash
uv run python -m scripts.cli build --config config.toml --build-mode both --parallel 2
uv run python -m scripts.cli build --config config.toml --build-mode apk --parallel 1 --clean
uv run python -m scripts.cli build --config config.toml --build-mode module --parallel 1 --no-cache
uv run python -m scripts.cli version-tracker check --config config.toml
uv run python -m scripts.cli cache stats
```

Legacy wrapper:

```bash
bash ./build.sh --config config.toml --build-mode apk --parallel 1
bash ./build.sh cache stats
```

`build.sh` is a compatibility wrapper around the same build flow. Prefer `uv run python -m scripts.cli ...` for normal use.

## Key commands

```bash
uv run python -m scripts.cli build --config config.toml --build-mode {apk,module,both} --parallel N [--clean] [--no-cache]
uv run python -m scripts.cli check --config config.toml
uv run python -m scripts.cli version-tracker {check|save|show|reset} --config config.toml
uv run python -m scripts.cli cache init
uv run python -m scripts.cli cache stats
uv run python -m scripts.cli cache cleanup [--force]
uv run python -m scripts.cli cache clean [--pattern '.*\.apk']
uv run bash ./scripts/lint.sh
uv run python -m pytest tests -v
```

## Configuration

The shipped `config.toml` uses top-level global settings plus per-app sections such as `[YouTube-Extended]`. Each enabled app needs at least one download source:

- `apkmirror-dlurl`
- `uptodown-dlurl`
- `archive-dlurl`
- `apkpure-dlurl`
- `aptoide-dlurl`
- `apkmonk-dlurl`

Common global settings include:

- `parallel-jobs`
- `build-mode`
- `patches-version`
- `cli-version`
- `patches-source`
- `cli-source`
- `arch`
- `riplib`
- `enable-aapt2-optimize`
- `aapt2-source`
- `use-custom-aapt2`

The sample config currently enables `Music-Extended` and `YouTube-Extended`; other app sections are included as examples and are disabled by default.

Config docs and generators:

- [`CONFIG.md`](./CONFIG.md) — config reference
- [`docs/README.md`](./docs/README.md) — docs index
- [`docs/FEATURES.md`](./docs/FEATURES.md) — cache, generator, changelog, dependency tooling
- [`docs/index.html`](./docs/index.html) — local docs landing page
- [`docs/generator.html`](./docs/generator.html) — local config generator
- Hosted generator used by this repo's config format: <https://j-hc.github.io/rvmm-config-gen/>

## Signing and build flow

- Builds require `KEYSTORE_PASSWORD` and `KEYSTORE_ENTRY_PASSWORD`.
- Default signing values come from the shell path: `KEYSTORE_PATH=assets/ks.keystore`, `KEYSTORE_ALIAS=jhc`, `KEYSTORE_SIGNER=jhc`.
- Stock APK signature checks use `assets/sig.txt` when entries are available.
- Final APKs are re-signed with `bin/apksigner.jar` using **v1 + v2 only**; **v3/v4 are intentionally disabled** for compatibility and predictable signing behavior. The jar is downloaded on demand when missing.

Normal flow:

1. Load `config.toml`.
2. Compare current config state with `.github/last_built_versions.json`.
3. Skip the build if nothing tracked changed.
4. If `--clean` is set, remove `temp/`, `build/`, `logs/`, and `build.md`.
5. Resolve compatible versions (`version = "auto"`), download stock APKs, and fetch CLI/patch prebuilts.
6. Patch, sign, and write final artifacts to `build/`.
7. Save the new version state after a successful build.

For YouTube and YouTube Music builds, expect to install a compatible GmsCore/MicroG provider on-device. The legacy Bash flow appends provider links to `build.md`; if you need them directly, see:

- <https://github.com/ReVanced/GmsCore/releases/latest>
- <https://github.com/MorpheApp/MicroG-RE/releases/latest>
- <https://github.com/YT-Advanced/GmsCore/releases/latest>

## Outputs

- `build/` — final APKs, module ZIPs, and per-app Markdown summaries
- `temp/` — temporary files and default cache directory
- `.github/last_built_versions.json` — saved version-tracker state
- `build.md` — legacy Bash-flow build notes/changelog

Cache commands use `temp/` by default with a TTL of `86400` seconds (24 hours). Expired entries are reused only until cleanup or replacement; see [`docs/FEATURES.md`](./docs/FEATURES.md) for cache behavior details. Set `CACHE_DIR` to override the cache location.

## Troubleshooting

- Run `bash ./check-env.sh` first.
- If `python -m scripts.cli ...` cannot import dependencies, run it through `uv run` or activate the `uv` environment first.
- If your checkout does not preserve executable bits, invoke shell entry points as `bash ./check-env.sh` and `bash ./build.sh`.
- If version checks keep skipping builds, inspect or reset `.github/last_built_versions.json` with `uv run python -m scripts.cli version-tracker show --config config.toml` or `... reset --config config.toml`.
- If downloads fail, set `GITHUB_TOKEN` and/or tune retry env vars.
- If signing fails, verify keystore env vars and file paths.
- `DEBUG=1` is useful for Python CLI debugging; `LOG_LEVEL=0` is useful for legacy/shared shell logging.

Useful env vars:

- `KEYSTORE_PASSWORD`
- `KEYSTORE_ENTRY_PASSWORD`
- `KEYSTORE_PATH`
- `KEYSTORE_ALIAS`
- `KEYSTORE_SIGNER`
- `GITHUB_TOKEN`
- `CACHE_DIR`
- `MAX_RETRIES`
- `INITIAL_RETRY_DELAY`
- `CONNECTION_TIMEOUT`
- `DEBUG`
- `LOG_LEVEL`
- `BUILD_MODE` (legacy shell flow)

## Docs

- [`CONFIG.md`](./CONFIG.md)
- [`docs/README.md`](./docs/README.md)
- [`docs/FEATURES.md`](./docs/FEATURES.md)
- [`AGENTS.md`](./AGENTS.md)
