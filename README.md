# ReVanced-auto

![GitHub repo size](https://img.shields.io/github/repo-size/Ven0m0/Revanced-auto)

ReVanced-auto builds patched Android APKs from a TOML config: resolve compatible app versions, download stock APKs, apply ReVanced/RVX-compatible CLI + patches, re-sign the result, and write artifacts to `build/`.

## Requirements

- Python **3.14+**
- Java **21+**
- `uv`, `zip`, `unzip`
- Optional but useful: `zipalign`, `optipng`

This repo uses `uv` for dependency management and is not distributed as a standalone Python package.

## Setup

```bash
git clone <repo-url>
cd Revanced-auto
mise install
uv sync --locked --all-groups
uv run python -m scripts.cli check-env
```

`check-env` verifies required tools, Java, downloads the required `bin/` jars when missing, checks optional helpers and assets, and validates `config.toml` syntax.

## Quick start

Prefer the Python CLI. After `uv sync`, use `uv run ...` for one-off commands, or activate the `uv` environment first if you are working in an interactive shell session.

```bash
# Prefer a secure secret source over typing passwords into shell history.
export KEYSTORE_PASSWORD='...'
export KEYSTORE_ENTRY_PASSWORD='...'

uv run python -m scripts.cli check-env
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

## Morphe setup guide

This repo ships with **Morphe** as the default patcher (`MorpheApp/morphe-patches` + `MorpheApp/morphe-cli`). `YouTube-Morphed` and `Music-Morphed` are enabled out of the box in `config.toml`.

### Prerequisites

- Java **21+** (Morphe CLI is built and tested on Java 21 LTS)
- Python **3.14+**
- `uv` for dependency management (or `mise` to provision the toolchain)

### First-time setup

```bash
git clone <repo-url>
cd Revanced-auto
mise install            # optional: provisions Python 3.14 + Java 21 via mise
uv sync --locked --all-groups
uv run python -m scripts.cli check-env   # verifies tools, downloads bin/* jars, validates config.toml
export KEYSTORE_PASSWORD='...'
export KEYSTORE_ENTRY_PASSWORD='...'
```

### Build with Morphe

```bash
# Sanity check (does not download APKs)
uv run python -m scripts.cli check --config config.toml

# Build all enabled apps (YouTube-Morphed + Music-Morphed by default)
uv run python -m scripts.cli build --config config.toml --build-mode apk --parallel 2
```

To force a specific CLI profile, set `cli-profile` in `config.toml` (or pass it on the command line where supported). Valid values:

- `"auto"` (default) — detect from the CLI JAR's `--help` output
- `"morphe-cli"`
- `"revanced-cli-v5"`
- `"revanced-cli-v6"`
- `"adobo-cli"` (Adobo patches run on Morphe CLI)

### Morphe resources

- [Official Morphe Website](https://morphe.software)
- [Morphe Patches site](https://morphe-patches.software)
- [Morphe Documentation](https://github.com/MorpheApp/morphe-documentation)
- [Awesome for Morphe](https://github.com/nvbangg/awesome-for-morphe) — curated list of Morphe tools, patch indexes, and community resources
- [Patch Explorer](https://patch-explorer.web.app/) — browse all Morphe-supported apps and patches
- [Morphe Patch Tracker](https://github.com/MorpheApp/morphe-patches/releases) — latest patches release
- [Morphe CLI releases](https://github.com/MorpheApp/morphe-cli/releases) — latest CLI release

### Troubleshooting Morphe

- **CLI detection picks the wrong profile** — set `cli-profile = "morphe-cli"` in `config.toml` to force it.
- **`patch --help` flags differ from what the docs say** — Morphe CLI tracks upstream; pin `cli-version = "vX.Y.Z"` to lock behavior.
- **Build succeeds but patches are not applied** — confirm `patches-source` resolves to a published release and `patches-version` matches the CLI's expected bundle shape.

## Key commands

```bash
uv run python -m scripts.cli build --config config.toml --build-mode {apk,module,both} --parallel N [--clean] [--no-cache]
uv run python -m scripts.cli check --config config.toml
uv run python -m scripts.cli version-tracker {check|save|show|reset} --config config.toml
uv run python -m scripts.cli cache init
uv run python -m scripts.cli cache stats
uv run python -m scripts.cli cache cleanup [--force]
uv run python -m scripts.cli cache clean [--pattern '.*\.apk']
uv run python -m scripts.cli lint [--fix]
uv run python -m pytest tests -v
```

## Configuration

The shipped `config.toml` uses top-level global settings plus per-app sections such as `[YouTube-Morphed]` or `[Reddit-Morphed]`. Each enabled app needs at least one download source:

- `apkmirror-dlurl`
- `uptodown-dlurl`
- `archive-dlurl`
- `apkpure-dlurl`
- `aptoide-dlurl`
- `apkmonk-dlurl`
- `github-dlurl` (e.g. `"https://github.com/owner/repo"`)

Common global settings include:

- `parallel-jobs`
- `build-mode`
- `patches-version`
- `cli-version`
- `patches-source` (defaults to `MorpheApp/morphe-patches`)
- `cli-source` (defaults to `MorpheApp/morphe-cli`)
- `cli-profile` (defaults to `"auto"`; detects `revanced-cli-v5`, `revanced-cli-v6`, `morphe-cli`, or `adobo-cli` from `--help`)
- `arch`
- `riplib`

Per-app settings worth knowing:

- `patches` — explicit list of patch names to include for that app (patches not listed are excluded)
- `patch-options."Patch Name"` — a sub-table of `key = "value"` options passed to a specific patch
- `exclusive` — when `true`, only the app's own `patches` list applies; global default patches are not merged in

The sample config enables `TikTok`, `YouTube-Morphed`, `Music-Morphed`, `Reddit-Morphed`, `Brave`, and `SDMaid`. Other sections (`Spotify`, `GooglePhotos`, `Instagram-Piko`, `Twitter-Piko`) are included as disabled examples — flip `enabled = true` to use them.

### Patch sources

`patches-source` (and `cli-source`) accepts a GitHub repo slug like `owner/repo`. A list of repo slugs is also accepted; later entries override earlier ones when patches conflict. Common choices:

- **Morphe (current default)** — `MorpheApp/morphe-patches` + `MorpheApp/morphe-cli`. Active app sections are `YouTube-Morphed` and `Music-Morphed`.
- **ReVanced** — `ReVanced/revanced-patches` + `ReVanced/revanced-cli` (upstream).
- **ReVanced Extended (RVX)** — `anddea/revanced-patches` + `inotia00/revanced-cli`.
- **Piko** (Twitter/X) — `crimera/piko`.
- **Patcheddit** (Reddit) — `wchill/patcheddit`.
- **External bundles** — `brosssh/revanced-external-bundles` resolves a patch JAR via the community aggregator's GraphQL API (https://revanced-external-bundles.brosssh.com). Use `external-bundles:<bundle_type>` to pin a specific bundle type; the bare repo slug falls back to selecting by the app's package id.
- **Adobo** — `jkennethcarino/adobo` is a patches collection that runs on top of Morphe CLI. Set `patches-source = "jkennethcarino/adobo"` (and keep `cli-source = "MorpheApp/morphe-cli"`).

Config docs and generators:

- [`docs/CONFIG.md`](./docs/CONFIG.md) — config reference
- [`docs/README.md`](./docs/README.md) — docs index
- [`docs/index.html`](./docs/index.html) — local docs landing page
- [`docs/generator.html`](./docs/generator.html) — local config generator
- [`CHANGELOG.md`](./CHANGELOG.md) — release history (maintained by release-please)
- Hosted generator used by this repo's config format: <https://j-hc.github.io/rvmm-config-gen/>

## Plugin hooks

Plugins in `scripts/plugins/` are auto-discovered. Each plugin module must expose:

```python
def handle_hook(ctx, stage: str) -> None: ...
```

Stages: `pre_pipeline`, `post_pipeline`.

## Signing and build flow

- Builds require `KEYSTORE_PASSWORD` and `KEYSTORE_ENTRY_PASSWORD`.
- Default signing values come from the shell path: `KEYSTORE_PATH=assets/ks.keystore`, `KEYSTORE_ALIAS=jhc`, `KEYSTORE_SIGNER=jhc`.
- Stock APK signature checks use `assets/sig.txt` when entries are available.
- Final APKs are re-signed with `bin/apksigner.jar` using **v1 + v2 only**; **v3/v4 are intentionally disabled** for compatibility and predictable signing behavior. The jar is downloaded on demand when missing.
- Keystores are auto-converted to BKS (cached under `.cache/keystore/`) before patching, since Morphe's patcher only accepts BKS; a PKCS12/JKS keystore such as `assets/ks.keystore` converts transparently on first use.

Normal flow:

1. Load `config.toml`.
2. Compare current config state with `.github/last_built_versions.json`.
3. Skip the build if nothing tracked changed.
4. If `--clean` is set, remove `temp/`, `build/`, `logs/`, and `build.md`.
5. Resolve compatible versions (`version = "auto"`), download stock APKs, and fetch CLI/patch prebuilts.
6. Patch, sign, and write final artifacts to `build/`.
7. Save the new version state after a successful build.

For YouTube and YouTube Music builds, expect to install a compatible GmsCore/MicroG provider on-device. The build appends provider links to `build.md`; if you need them directly, see:

- <https://github.com/ReVanced/GmsCore/releases/latest>
- <https://github.com/MorpheApp/MicroG-RE/releases/latest>
- <https://github.com/YT-Advanced/GmsCore/releases/latest>

## Outputs

- `build/` — final APKs, module ZIPs, and per-app Markdown summaries
- `temp/` — temporary files and default cache directory
- `.github/last_built_versions.json` — saved version-tracker state
- `build.md` — combined build notes/changelog

Cache commands use `temp/` by default with a TTL of `86400` seconds (24 hours). Expired entries are reused only until cleanup or replacement. Set `CACHE_DIR` to override the cache location.

## Troubleshooting

- Run `uv run python -m scripts.cli check-env` first.
- If `python -m scripts.cli ...` cannot import dependencies, run it through `uv run` or activate the `uv` environment first.
- If version checks keep skipping builds, inspect or reset `.github/last_built_versions.json` with `uv run python -m scripts.cli version-tracker show --config config.toml` or `... reset --config config.toml`.
- If downloads fail, set `GITHUB_TOKEN` and/or tune retry env vars.
- If signing fails, verify keystore env vars and file paths.
- `DEBUG=1` is useful for Python CLI debugging.

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

## Docs

- [`docs/CONFIG.md`](./docs/CONFIG.md)
- [`docs/README.md`](./docs/README.md)
- [`docs/PATCHES.md`](./docs/PATCHES.md) — curated patch sources and Morphe indexes
- [`AGENTS.md`](./AGENTS.md)

## Related projects

- [Morphe](https://morphe.software) — patches and CLI that drive this repo's default build.
- [Morphe Patches](https://morphe-patches.software) — index of Morphe-supported apps and patches.
- [awesome-for-morphe](https://github.com/nvbangg/awesome-for-morphe) — curated list of Morphe tools, patch indexes, and community resources.
- [builder-for-morphe](https://github.com/nvbangg/builder-for-morphe) — minimal Python rewrite based on j-hc/uni-apks. Uses the same `config.toml` shape as this repo; recommended for users who want a simpler single-purpose builder.
- [ReVanced](https://github.com/ReVanced) — upstream ReVanced project.
- [ReVanced Extended (RVX)](https://github.com/inotia00/revanced-patches) — community patch fork.
- [revanced-external-bundles](https://revanced-external-bundles.brosssh.com) — community patches aggregator (used by `patches-source = "brosssh/revanced-external-bundles"`).
- [j-hc/rvmm-config-gen](https://j-hc.github.io/rvmm-config-gen/) — web config generator compatible with this repo's TOML format.
