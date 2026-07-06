# Patch sources and indexes

ReVanced-auto resolves patches and CLIs from GitHub releases. A `patches-source` (and matching `cli-source`) is a `owner/repo` slug; multiple sources can be combined as a list and later entries override earlier ones on patch conflicts.

## Official Morphe

- **Patches repo:** <https://github.com/MorpheApp/morphe-patches>
- **CLI repo:** <https://github.com/MorpheApp/morphe-cli>
- **Patches site:** <https://morphe-patches.software>
- **Releases:** <https://github.com/MorpheApp/morphe-patches/releases>
- **CLI releases:** <https://github.com/MorpheApp/morphe-cli/releases>

This is the **default** in `config.toml`.

## ReVanced (upstream)

- **Patches repo:** <https://github.com/ReVanced/revanced-patches>
- **CLI repo:** <https://github.com/ReVanced/revanced-cli>

## ReVanced Extended (RVX)

- **Patches repo:** <https://github.com/anddea/revanced-patches>
- **CLI repo:** <https://github.com/inotia00/revanced-cli>
- Use sample sections `YouTube-Extended` / `Music-Extended` (disabled by default).

## Piko (Twitter/X)

- **Patches repo:** <https://github.com/crimera/piko>
- Runs on the ReVanced or Morphe CLI.

## Patcheddit (Reddit)

- **Patches repo:** <https://github.com/wchill/patcheddit>
- Runs on the ReVanced or Morphe CLI.

## Adobo (Morphe-compatible patches)

- **Patches repo:** <https://github.com/jkennethcarino/adobo>
- Set `patches-source = "jkennethcarino/adobo"` and keep `cli-source = "MorpheApp/morphe-cli"`.
- Profile: `cli-profile = "adobo-cli"`.

## External bundles aggregator

- **Aggregator:** <https://revanced-external-bundles.brosssh.com>
- **Source repo:** <https://github.com/brosssh/revanced-external-bundles>
- Resolves a patch JAR via the community aggregator's GraphQL API.
- Use the bare repo slug (matched by app package id) or pin a specific bundle:
  - `patches-source = "brosssh/revanced-external-bundles"`
  - `patches-source = "external-bundles:revanced-patches"`

## Browse patches / Morphe patch index

- [Awesome for Morphe](https://github.com/nvbangg/awesome-for-morphe) — curated list of Morphe tools, patch indexes, and community resources.
- [Patch Explorer](https://patch-explorer.web.app/) — browse all Morphe-supported apps and patches.
- [Community Patch Space Explorer](https://lighthouse3140.github.io/) — explore community patch spaces (ReVanced Extended, etc.).
- [Morphe Patch Tracker](https://github.com/MorpheApp/morphe-patches/releases) — official Morphe patch releases feed.

## Config examples

```toml
# Morphe (default)
patches-source = "MorpheApp/morphe-patches"
cli-source     = "MorpheApp/morphe-cli"
cli-profile    = "auto"

# ReVanced upstream
patches-source = "ReVanced/revanced-patches"
cli-source     = "ReVanced/revanced-cli"
cli-profile    = "auto"

# Adobo (Morphe-compatible)
patches-source = "jkennethcarino/adobo"
cli-source     = "MorpheApp/morphe-cli"
cli-profile    = "adobo-cli"

# External bundles (resolved by package id)
patches-source = "brosssh/revanced-external-bundles"

# External bundles (explicit bundle type)
patches-source = "external-bundles:revanced-patches"

# Layered: Morphe base + Adobo overrides
patches-source = [
  "MorpheApp/morphe-patches",
  "jkennethcarino/adobo",
]
```
