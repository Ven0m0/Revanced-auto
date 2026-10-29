# ReVanced-auto

![GitHub repo size](https://img.shields.io/github/repo-size/Ven0m0/Revanced-auto)

ReVanced-auto builds patched Android APKs from a TOML config: resolve compatible app versions, download stock APKs, apply Morphe CLI + Morphe-compatible patch bundles, re-sign the result, and write artifacts to `build/`.

## Requirements

- Python **3.15** (`requires-python = ">=3.15,<3.16"`)
- Java **21+**, an OpenJDK build such as Temurin (`mise install` provides Temurin 25). Oracle JDK and GraalVM reject the
  unsigned BouncyCastle provider bundled in the Morphe CLI, so patching fails with
  `JCE cannot authenticate the provider BC` / `Invalid password for keystore entry`, even with correct passwords.
- `uv`
- Google Chrome, only for apps whose APKMirror pages sit behind a Cloudflare challenge (currently Discord). It runs
  headed, so a headless Linux machine needs `xvfb-run`. Other apps never start it.
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
# Optional: only needed when you sign with your own keystore (see "Signing and build flow").
# Prefer a secure secret source over typing passwords into shell history.
# export KEYSTORE_PASSWORD='...'
# export KEYSTORE_ENTRY_PASSWORD='...'

uv run python -m scripts.cli check-env
uv run python -m scripts.cli check --config config.toml
uv run python -m scripts.cli build --config config.toml --parallel 1
```

The CLI builds every app with `enabled = true` in `config.toml`. To rebuild when nothing changed, reset the version tracker first:

```bash
uv run python -m scripts.cli version-tracker reset --config config.toml
```

Useful variants:

```bash
uv run python -m scripts.cli build --config config.toml --parallel 2
uv run python -m scripts.cli build --config config.toml --parallel 1 --clean
uv run python -m scripts.cli build --config config.toml --parallel 1 --no-cache
uv run python -m scripts.cli version-tracker check --config config.toml
uv run python -m scripts.cli cache stats
```

## Morphe setup guide

This repo ships with **Morphe** as the default patcher (`MorpheApp/morphe-patches` + `MorpheApp/morphe-cli`). The sample `config.toml` enables nine apps (see [Configuration](#configuration)).

### Build with Morphe

Setup is the same as above. The keystore passwords default to the tracked `assets/ks.keystore`'s, so they are only
needed for your own keystore.

```bash
# Sanity check (does not download APKs)
uv run python -m scripts.cli check --config config.toml

# Build all enabled apps
uv run python -m scripts.cli build --config config.toml --parallel 2
```

To force a specific CLI profile, set `cli-profile` in `config.toml`. Valid values:

- `"auto"` (default) — detect from the CLI JAR's `--help` output
- `"morphe-cli"`
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
uv run python -m scripts.cli build --config config.toml --parallel N [--clean] [--no-cache]
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

The shipped `config.toml` uses top-level global settings plus one `[Section]` per app. The full key reference is
[`docs/CONFIG.md`](./docs/CONFIG.md). Each enabled app needs at least one download source, tried in this order until one works:

- `apkmirror-dlurl`
- `archive-dlurl`
- `apkpure-dlurl`
- `github-dlurl` (e.g. `"https://github.com/owner/repo"`; end the URL with `/<asset>.apk` to pin a release asset by name, e.g. `".../releases/latest/download/BraveMonoarm64.apk"`)
- `aptoide-dlurl`
- `apkmonk-dlurl`
- `uptodown-dlurl` (currently unusable: the version-list pages the scraper reads return 404)

Global settings:

- `parallel-jobs` (`0` means 2)
- `patches-version`, `cli-version` (`latest`, `dev` or a tag)
- `patches-source` (defaults to `MorpheApp/morphe-patches`)
- `cli-source` (defaults to `MorpheApp/morphe-cli`)
- `cli-profile` (defaults to `"auto"`; detects `morphe-cli` or `adobo-cli` from `--help`)
- `arch` (default architecture, applied to every app that does not set its own `arch`)
- `riplib`
- `keystore-path`, `keystore-alias` (default `assets/ks.keystore` and `morphe`)

Per-app settings worth knowing:

- `app-name`, `rv-brand` — output name and brand label. These are per-app only; global values are ignored.
- `patches` — array of patch names to enable
- `exclude-patches` — array of patch names to disable
- `exclusive` — when `true`, only the names in `patches` are enabled; every other patch stays off
- `patch-options."Patch Name"` — a sub-table of `key = "value"` options passed to a specific patch
- `package-name` — package id used to look up patch-compatible versions when it cannot be derived from a download URL (for example APKMirror-only apps; `Reddit-Morphed` uses `com.reddit.frontpage`)
- `version` — `auto` (default) picks the newest version compatible with the patches, `latest` the newest store version, `beta` the newest including beta/alpha, or pin an exact version
- `patches-source`, `cli-source`, `arch` — override the global values

The sample config enables `TikTok`, `YouTube-Morphed`, `Music-Morphed`, `Reddit-Morphed`, `Brave`, `SDMaid`, `SoundCloud`, `GoogleMaps`, and `Discord`. `GooglePhotos`, `Instagram-Piko`, `Twitter-Piko` and `X-Piko` are included as disabled examples; flip `enabled = true` to use them. The Piko sections are disabled because Piko supports only one old app version each that the scrapers cannot reach.

### Patch sources

`patches-source` (and `cli-source`) accepts a GitHub repo slug like `owner/repo`. A list of repo slugs is also accepted; later entries override earlier ones when patches conflict. Every bundle runs on the Morphe CLI. [`docs/PATCHES.md`](./docs/PATCHES.md) lists the bundles the sample config uses. The common ones:

- **Morphe (default)** — `MorpheApp/morphe-patches` + `MorpheApp/morphe-cli`.
- **Adobo** — `jkennethcarino/adobo`, extra patches on top of Morphe.
- **Piko** (Twitter/X, Instagram) — `crimera/piko`.
- **External bundles** — `brosssh/revanced-external-bundles` resolves a patch JAR via the community aggregator's GraphQL API (https://revanced-external-bundles.brosssh.com). Use `external-bundles:<bundle_type>` to pin a specific bundle type; the bare repo slug falls back to selecting by the app's package id.

Config docs and generator:

- [`docs/CONFIG.md`](./docs/CONFIG.md) — config reference
- [`docs/README.md`](./docs/README.md) — docs index
- [`docs/index.html`](./docs/index.html) — local docs landing page
- [`docs/generator.html`](./docs/generator.html) — local config generator
- [`CHANGELOG.md`](./CHANGELOG.md) — changelog

## Plugin hooks

Plugins in `scripts/plugins/` are auto-discovered. Each plugin module must expose:

```python
def handle_hook(ctx, stage: str) -> None: ...
```

Stages: `pre_pipeline`, `post_pipeline`.

## Signing and build flow

- The keystore is `keystore-path` from `config.toml`, or `assets/ks.keystore` when unset; the alias is `keystore-alias` (default `morphe`).
- `KEYSTORE_PASSWORD` defaults to `Morphe`, which opens the tracked `assets/ks.keystore`. `KEYSTORE_ENTRY_PASSWORD` defaults to the keystore password. Set both for your own keystore (CI passes them from secrets).
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

For YouTube and YouTube Music builds, expect to install MicroG-RE on-device. The release notes link it once; you can also get it directly from <https://github.com/morpheapp/microg-RE/releases/latest>.

## Outputs

- `build/` — final APKs and per-app Markdown summaries
- `temp/` — temporary files and the default directory of the `cache` subcommands
- `.cache/` — downloaded CLI/patch jars (`.cache/prebuilts/`) and converted keystores (`.cache/keystore/`)
- `.github/last_built_versions.json` — saved version-tracker state
- `build.md` — combined build notes/changelog

The `cache` subcommands use `temp/` by default with a TTL of `86400` seconds (24 hours). Expired entries are reused only until cleanup or replacement. Set `CACHE_DIR` to move the cache; it applies to both locations above.

## Troubleshooting

- Run `uv run python -m scripts.cli check-env` first.
- If `python -m scripts.cli ...` cannot import dependencies, run it through `uv run` or activate the `uv` environment first.
- If version checks keep skipping builds, inspect or reset `.github/last_built_versions.json` with `uv run python -m scripts.cli version-tracker show --config config.toml` or `... reset --config config.toml`.
- If downloads fail, set `GITHUB_TOKEN` (GitHub API rate limits) and check that the app's other sources work.
- If APKMirror answers `403` / "Just a moment...", the page is behind a Cloudflare challenge. The scraper then needs Chrome (see Requirements); the final file download is plain HTTP.
- If signing fails, check the Java build first (Oracle JDK/GraalVM cause `Invalid password for keystore entry` even with the right passwords), then the keystore env vars and `keystore-path`.
- `DEBUG=1` is useful for Python CLI debugging.

Environment variables the scripts read:

- `KEYSTORE_PASSWORD`
- `KEYSTORE_ENTRY_PASSWORD`
- `GITHUB_TOKEN`
- `CACHE_DIR`
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
- [builder-for-morphe](https://github.com/nvbangg/builder-for-morphe) — minimal Python rewrite based on j-hc/uni-apks, for users who want a simpler single-purpose builder.
- [ReVanced](https://github.com/ReVanced) — upstream ReVanced project.
- [ReVanced Extended (RVX)](https://github.com/inotia00/revanced-patches) — community patch fork.
- [revanced-external-bundles](https://revanced-external-bundles.brosssh.com) — community patches aggregator (used by `patches-source = "brosssh/revanced-external-bundles"`).
