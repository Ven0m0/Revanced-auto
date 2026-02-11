# ReVanced Builder Documentation
Welcome to the ReVanced Builder documentation and tools directory.
## Site Structure
| Page                                 | Description                                                       |
| ------------------------------------ | ----------------------------------------------------------------- |
| [`index.html`](./index.html)         | Landing page with feature overview, app showcase, and quick start |
| [`generator.html`](./generator.html) | Configuration generator with app catalog and patch selector       |
| [`style.css`](./style.css)           | Shared design system (theme, nav, components)                     |
## Configuration Generator
**Location**: [`generator.html`](./generator.html)
A self-contained web application for creating `config.toml` files without manual editing.
**Features**:
- **App Catalog**: Pre-configured profiles for 8 popular apps (YouTube, Music, Spotify, Reddit, X/Twitter, TikTok, Instagram, Google Photos) with pre-filled download URLs and settings
- Interactive form-based interface with global and per-app settings
- Live TOML preview panel (sticky sidebar on desktop)
- Visual patch selector that fetches patches from any GitHub repository
- Patch search, filtering, and bulk select/deselect
- Import existing `config.toml` files to edit them visually
- Download or copy generated configuration with one click
- Example configurations to get started quickly
- Dark/light theme toggle (persisted in localStorage, shared across pages)
- Keyboard shortcut: `Ctrl+S` to download
- Fully responsive layout with mobile hamburger navigation
- Accessible: skip link, ARIA attributes, keyboard navigation
- Print-friendly: hides controls and shows config only
## Quick Start
1. Open the [landing page](./index.html) or go directly to the [generator](./generator.html)
2. Configure global settings (patches source, CLI source, architecture, etc.)
3. **Select an app from the catalog** to add it with pre-filled settings, or click **Custom App** for manual entry
4. Fill in or adjust app details: name, version, download URLs
5. Click **Browse & Select Patches** to visually select patches
6. Review the live preview on the right
7. **Download** or **Copy** the generated `config.toml`
To edit an existing config, click **Import** in the header and select your `.toml` file.
## Shared Design System
Both pages share `style.css` which provides:
- Dark/light theme via CSS custom properties and `data-theme` attribute
- Responsive navigation bar with hamburger menu on mobile (< 768px)
- Consistent card, button, form, and typography styles
- Toast notification system
- Print stylesheet
- Accessibility: skip links, focus rings, screen reader utilities
Theme preference is stored in `localStorage` and synced across pages.
## Navigation
All pages include a shared navigation bar:
- **Home** — Landing page with project overview
- **Generator** — Configuration generator with app catalog
- **Config Docs** — Links to CONFIG.md on GitHub
- **GitHub** — Repository link
- **Theme Toggle** — Dark/light mode switch
On mobile (< 768px), the navigation collapses into a hamburger menu.
## Configuration Options
**Global Settings**:
- `parallel-jobs` - Number of simultaneous builds
- `compression-level` - ZIP compression (0-9)
- `patches-source` - Default GitHub repo for patches
- `cli-source` - ReVanced CLI source
- `arch` - Default architecture (arm64-v8a, armeabi-v7a, both)
- `riplib` - Strip unnecessary libraries
- `enable-aapt2-optimize` - Resource optimization
**Per-App Settings**:
- `enabled` - Enable/disable app building
- `app-name` - Display name
- `version` - auto, latest, or specific version
- `patches-source` / `cli-source` - Override global sources
- Download URLs (APKMirror, Uptodown, Archive.org)
- Patch Selection - Visual browser with search/filter
- `excluded-patches` - Patches to skip (manual or auto-generated)
- `included-patches` - Exclusive patch list
## Additional Documentation
- [Main README](../README.md) - Project overview
- [Configuration Reference](../CONFIG.md) - Detailed config documentation
- [Advanced Features](./FEATURES.md) - Changelog, cache, dependency checker
- [External Links](./LINKS.md) - Other patch repositories
## Contributing
When adding documentation:
1. Keep it concise and actionable
2. Include code examples
3. Update this index
4. Test all links
## External Links
- [ReVanced Project](https://github.com/ReVanced)
- [ReVanced Extended (RVX)](https://github.com/inotia00/revanced-patches)
- [GitHub Pages Documentation](https://docs.github.com/en/pages)
