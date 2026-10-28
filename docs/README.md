# Documentation

| File | Contents |
| --- | --- |
| [`CONFIG.md`](./CONFIG.md) | Every `config.toml` key, download sources, signing, troubleshooting |
| [`PATCHES.md`](./PATCHES.md) | Patch bundles the sample config uses, and how to combine them |
| [`index.html`](./index.html) | Landing page (published with GitHub Pages) |
| [`generator.html`](./generator.html) | Browser-based `config.toml` generator |
| [`style.css`](./style.css), [`_config.yml`](./_config.yml) | Shared styles and the Pages/Jekyll config |

The project overview and CLI usage are in the [main README](../README.md).

## Configuration generator

[`generator.html`](./generator.html) is a self-contained page (no build step, no server) that writes a
`config.toml` for you:

- Pick apps from the catalog or add a custom one, and set global and per-app options.
- Browse a bundle's patches from its GitHub repo, then filter and select them.
- Watch the TOML preview update live, then download or copy it (`Ctrl+S` downloads).
- **Import** an existing `config.toml` to edit it. The importer reads the keys the generator writes; other keys
  are dropped, so check the result before replacing a hand-edited file.

The theme (dark/light) is stored in `localStorage` and shared by both pages.

## Publishing

`.github/workflows/pages.yml` publishes `docs/` to GitHub Pages on every push to `main` that touches it.

## External links

- [Morphe](https://morphe.software), [Morphe patches](https://morphe-patches.software), [Morphe documentation](https://github.com/MorpheApp/morphe-documentation)
- [Awesome for Morphe](https://github.com/nvbangg/awesome-for-morphe), [Patch Explorer](https://patch-explorer.web.app/)
