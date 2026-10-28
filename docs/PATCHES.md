# Patch sources

A `patches-source` (and its `cli-source`) is a GitHub `owner/repo`. A list merges several bundles; later
entries win on duplicate patch names. All bundles below run on the Morphe CLI (`cli-source =
"MorpheApp/morphe-cli"`). The CLI has two flag profiles, `morphe-cli` and `adobo-cli`; see `cli-profile` in
[CONFIG.md](./CONFIG.md).

## Bundles used by the sample `config.toml`

| Repo | Used for |
| --- | --- |
| [`MorpheApp/morphe-patches`](https://github.com/MorpheApp/morphe-patches) | Default bundle: YouTube, YouTube Music, Reddit. Site: <https://morphe-patches.software> |
| [`jkennethcarino/adobo`](https://github.com/jkennethcarino/adobo) | Extra YouTube and Reddit patches |
| [`BlazeFTL/FTL-Patches`](https://github.com/BlazeFTL/FTL-Patches) | Universal APK-size, ads and analytics cleanup |
| [`icysymmetra/tiktok-patches-for-morphe`](https://github.com/icysymmetra/tiktok-patches-for-morphe) | TikTok |
| [`rushiranpise/morphe-patches`](https://github.com/rushiranpise/morphe-patches) | Reddit, SD Maid |
| [`dh6k/morphe-patches`](https://github.com/dh6k/morphe-patches) | Brave and universal patches |
| [`kveld9/kveld-morphe-patches`](https://github.com/kveld9/kveld-morphe-patches) | Brave and Discord size/privacy cleanup |
| [`kondratjev/morphe-patches`](https://github.com/kondratjev/morphe-patches) | SoundCloud |
| [`bearinmindcat/morphe-patches`](https://github.com/bearinmindcat/morphe-patches) | Google Maps |
| [`VenusIsJaded/Venus-Patches`](https://github.com/VenusIsJaded/Venus-Patches) | Discord client mods |
| [`jrddupont/discord-patches`](https://github.com/jrddupont/discord-patches) | Discord |
| [`crimera/piko`](https://github.com/crimera/piko) | X / Twitter and Instagram sections |

## External bundles aggregator

[`brosssh/revanced-external-bundles`](https://github.com/brosssh/revanced-external-bundles) resolves a
patch jar through the community aggregator at <https://revanced-external-bundles.brosssh.com>:

```toml
patches-source = "brosssh/revanced-external-bundles"       # matched by the app's package id
patches-source = "external-bundles:revanced-patches"       # explicit bundle type
```

## Combining bundles

Each patch is applied from the bundle that lists it, so one app can mix bundles. Keep `patches` lists to
names that exist in at least one bundle:

```toml
[Discord]
patches-source = ["VenusIsJaded/Venus-Patches", "kveld9/kveld-morphe-patches", "jrddupont/discord-patches"]
cli-source = "MorpheApp/morphe-cli"
exclusive = true
patches = ["Custom themes", "Shrink PNG Images", "Pin app to built-in bundle"]
```

## Finding patches

- [Patch Explorer](https://patch-explorer.web.app/) - browse Morphe-supported apps and patches
- [Awesome for Morphe](https://github.com/nvbangg/awesome-for-morphe) - curated tools and bundles
- [Morphe patch releases](https://github.com/MorpheApp/morphe-patches/releases)
- The [generator](./generator.html) can list the patches of any bundle repo
