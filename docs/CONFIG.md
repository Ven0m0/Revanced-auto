# Configuration reference

Builds are driven by one TOML file (default `config.toml`). Top-level keys are global defaults; every
`[Section]` is one app. Keys use kebab-case (`patches-source`).

```toml
[Some-App]
apkmirror-dlurl = "https://www.apkmirror.com/apk/inc/app/"
package-name = "com.example.app"   # APKMirror/GitHub URLs carry no package id
```

An enabled app needs at least one `*-dlurl`. Everything else is optional.

## Global keys

| Key | Default | Meaning |
| --- | --- | --- |
| `parallel-jobs` | `0` | Concurrent builds. `0` means the built-in default of 2. |
| `arch` | `all` | Default architecture for apps without their own. See [Architecture](#architecture). |
| `riplib` | `true` | Strip native libraries of other ABIs. |
| `patches-source` | `MorpheApp/morphe-patches` | Patch bundle(s): one `owner/repo`, or a list that is merged. |
| `cli-source` | `MorpheApp/morphe-cli` | Patcher CLI repo. |
| `patches-version` / `cli-version` | `latest` | `latest`, `dev`, or a release tag. |
| `cli-profile` | `auto` | CLI flag style: `auto`, `morphe-cli`, `adobo-cli`. `auto` reads the jar's `--help`. |
| `keystore-path` | `assets/ks.keystore` | Signing keystore (BKS, PKCS12 or JKS). |
| `keystore-alias` | `morphe` | Entry alias inside the keystore. |

## App keys

| Key | Meaning |
| --- | --- |
| `enabled` | Build this app. Default `true`. |
| `app-name` | Output name. Default is the section name. |
| `rv-brand` | Brand label for the build (default `revanced`). Per-app only; a global value is ignored. |
| `version` | `auto` (newest patch-compatible), `latest` (newest stable), `beta`, or an exact version. |
| `package-name` | Package id used to look up patch-compatible versions. Required when no URL contains it. |
| `arch` | Overrides the global architecture. |
| `patches-source` / `cli-source` | Override the global sources. A list of sources is merged; later entries win on duplicate patch names. |
| `patches` | Array of patch names to enable. |
| `exclude-patches` | Array of patch names to disable. |
| `exclusive` | `true` enables only the names in `patches`; everything else stays off. |
| `<source>-dlurl` | Where to get the stock APK. See [Download sources](#download-sources). |

```toml
[Reddit]
patches-source = ["MorpheApp/morphe-patches", "BlazeFTL/FTL-Patches"]
exclusive = true
patches = ["Hide ads", "Remove Languages"]

# Patch options: one table per patch. Values are passed to the CLI verbatim as -Okey=value,
# so string options need their own quotes and lists use JSON syntax.
[Reddit.patch-options."Custom branding name for Reddit"]
appName = "\"Reddit Morphe\""

[Reddit.patch-options."Remove Languages"]
keepLanguages = "[\"en\"]"
```

With several bundles, each patch name is matched to the bundle that provides it, so the build lists every
bundle's patches first and fails if it cannot. A name in `patches` that no bundle lists is logged as a warning.

### Architecture

`arm64-v8a`, `arm-v7a` (`armeabi-v7a` is accepted as an alias), `both` (builds `arm64-v8a` and `arm-v7a`) or `all` (same as `both`).

## Download sources

Set any of these per app. All configured sources are tried in this order until one resolves a version
and downloads:

1. `apkmirror-dlurl` - app page, e.g. `https://www.apkmirror.com/apk/google-inc/youtube`
2. `archive-dlurl` - archive.org item
3. `apkpure-dlurl`
4. `github-dlurl` - `https://github.com/owner/repo`; end it with `/<asset>.apk` to pin a release asset
5. `aptoide-dlurl`
6. `apkmonk-dlurl`
7. `uptodown-dlurl`

Split bundles (APKM/XAPK) are merged into one APK before patching.

Notes:

- **Cloudflare:** APKMirror challenges some apps (Discord) on every page. The scraper then drives a real
  Chrome through [nodriver](https://github.com/ultrafunkamsterdam/nodriver). That needs Chrome installed and a
  display (use `xvfb-run` on a headless Linux box); headless Chrome is blocked. The final file download is
  plain HTTP.
- **Uptodown:** as of 2026-10-28 the version-list pages the scraper reads return 404, so Uptodown can no
  longer resolve versions. Prefer another source.

## Signing

Output APKs are re-signed with `apksigner`. Keystores are converted to BKS for the patcher automatically.
Passwords come from the environment:

| Variable | Default |
| --- | --- |
| `KEYSTORE_PASSWORD` | `Morphe` |
| `KEYSTORE_ENTRY_PASSWORD` | the keystore password |

Other environment variables: `GITHUB_TOKEN` (API rate limits), `CACHE_DIR` (default `.cache`).

## Troubleshooting

- **`Signing failed: Invalid password for keystore entry`** with the right passwords: the Java on `PATH`
  is Oracle JDK or GraalVM, which reject the BouncyCastle provider bundled in the Morphe CLI. Use Temurin
  (`mise install` provides it).
- **`HTTP 403` / "Just a moment..." from APKMirror:** see the Cloudflare note above.
- **Wrong CLI flags:** set `cli-profile` explicitly instead of `auto`.

Validate a config without building: `uv run python -m scripts.cli check --config config.toml`.
