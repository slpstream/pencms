# Adding and Managing Themes in PenCMS

PenCMS themes are native Twig packages under `frontend-php/src/blog/themes/{theme-id}/`. Use this page for scaffold, switch, and validate. For layers, dual-duty skins, shortcodes, OG, and the compliance checklist, read **[`pencms-theme-development.md`](pencms-theme-development.md)**.

---

## 1. Scaffold a new theme

```bash
php frontend-php/cli-tools/theme-scaffold.php my-custom-theme
```

Creates `frontend-php/src/blog/themes/my-custom-theme/` with mandatory directories, templates, partials, a baseline `theme.json`, and starter stylesheets.

> [!NOTE]
> **Theme Mode Policy:** PenCMS themes should be **single-mode by default** with no mode toggle. Dark mode is **not first-class** and must not be included unless explicitly requested by the user when building the theme. Traven Editor operates strictly in single default mode. See [`pencms-theme-development.md`](pencms-theme-development.md) §6 for details.

---

## 2. Directory sketch

```text
frontend-php/src/blog/themes/my-custom-theme/
├── theme.json
├── screenshot.webp      # Admin Settings → Themes card preview (16:10); optional but recommended
├── assets/css/          # skin-{id}.css (content) + styles.css (chrome)
├── assets/js/           # theme.js (mobile drawer, sturdy dropdown hover grace)
├── assets/fonts/
├── assets/images/
├── partials/            # _head, _header, _navbar (Primary), _sidebar-secondary (Secondary), _footer (Footer)
└── templates/           # index, post, page, search (mandatory); archive / overrides optional
```

Admin theme cards look for a root-level `screenshot.webp` (not a `theme.json` field). Capture or refresh install themes with [`frontend-php/cli-tools/capture-theme-screenshots.mjs`](../../frontend-php/cli-tools/capture-theme-screenshots.mjs) against a local `php -S` front (`PENCMS_BASE_URL`).

> [!IMPORTANT]
> **Mandatory 3-Slot Menu Contract:** Every PenCMS theme **must** implement and render all three menu slots (`primary`, `secondary`, and `footer`), each supporting 2-level nesting (Parent + Child). Themes have creative freedom over positioning (e.g. top navbar, left/right sidebar, bottom navbar, footer group), but all 3 slots must be wired and render when configured in `admin-settings-navigation.php`. Dropdown menus must use a sturdy, gapless hover bridge and grace delay (no flimsy hovering).

> [!NOTE]
> **Vanilla CSS vs Tailwind (directory / dual-duty):**
> Prefer **plain vanilla CSS** for `assets/css/skin-{id}.css` + chrome when you control the theme in-house — that is how `starter`, `editorial`, `academic`, `colorful`, `dark`, and `modern` stay pixel-aligned between TravenEditor and published HTML. Independent designers may use Tailwind (or another framework) for chrome, but then they inherit Preflight / reset drift and must put **all dual-duty rules** (and any theme-local `@font-face` for private fonts) **in the skin**, not only in Tailwind-compiled `styles.css`. Registry families load via `publicAsset('fonts/fonts.css')` — see [`pencms-theme-development.md`](pencms-theme-development.md) §6 / §9.

> [!IMPORTANT]
> **PenCMS `[image]` shortcodes (published output):** Traven editor classes (`img.traven-image-shortcode`) are not the same as PHP gallery markup (`.gallery-single` + `.photo-wrapper`). New themes must copy the **§8 *PenCMS `[image]` / `.gallery-single`* CSS blocks** into `assets/css/styles.css` — percentage sizes (30% / 50% / 70%), default centering for non-floated gallery blocks, and classic-markdown figure rules. Use `starter` as the reference implementation. Fullbleed stays theme-specific; do not skip the rest of the image matrix.

> [!WARNING]
> **Video players (required in every skin):** `.traven-video-container` needs `position: relative` + `aspect-ratio: 16 / 9`, and the inner `iframe`/`video` must be `position: absolute; width/height: 100%`. `max-width: 100%` alone leaves a black letterbox with a tiny YouTube thumbnail. Put this in `skin-{id}.css` even if chrome uses Tailwind. Details: [`pencms-theme-development.md`](pencms-theme-development.md) §8 — *Pitfall: video iframe*.

> [!WARNING]
> **Fullbleed video height:** Align/size classes land on `figure.traven-video-figure`, while 16:9 height belongs on `.traven-video-container` via `aspect-ratio`. Never add `padding-bottom: calc(100vw * 9 / 16)` to a rule that also matches the figure — that doubles the block height and leaves a huge gap under the caption. Details: [`pencms-theme-development.md`](pencms-theme-development.md) §8 — *Pitfall: fullbleed video*.

> [!WARNING]
> **Fullbleed + sidebars:** Do not use `width: 100vw` / `calc(50% - 50vw)` when the article column is off-center (2/3 + sidebar, asymmetric grids). Prefer the casper-lite **stage** breakout (negative margins within the column + gutter), or center the column before enabling viewport wall-to-wall. Details: [`pencms-theme-development.md`](pencms-theme-development.md) §8 — *Wider-than-column stage* / *asymmetric sidebar grids*.

Full tree, `theme.json` fields (`supports`, `editor_skin`, `social_preview`), and template resolution: [`pencms-theme-development.md`](pencms-theme-development.md) §4–§5.


---

## 3. Switch active theme

1. Open `pencms/backend-python/config.ini` (or your install’s config).
2. Update the `[theme]` block:

```ini
[theme]
active = my-custom-theme
directory = ../frontend-php/src/blog/themes
```

---

## 4. Validate

```bash
php frontend-php/cli-tools/theme-validate.php my-custom-theme
```

Checks structure plus dual-duty / OG contract: content `skin-*.css`, `traven-preview` on post/page templates, complete `social_preview`, `editor_skin` (warn), OG font / `defaulthero` warnings. Errors exit 1; warnings exit 0. Full scoring still uses [`pencms-theme-development.md`](pencms-theme-development.md) §15.

---

## 5. Export and import theme packages

Zip upload, install-from-URL, Download `.zip`, and Save as installed theme
ship with Core Theme Settings (requires `write:theme`). Scaffold +
`theme-validate.php` stay Core.

**Import (upload):** Admin → Theme Settings → **Import New** → upload a `.zip` with a single `theme.json` at the archive root or inside one top-level folder (`POST /api/themes/install`).

**Import (URL):** Admin → Theme Settings → **Import New** → **Install from URL** accepts:

- Direct HTTPS links to a `.zip` theme archive
- Public GitHub HTTPS repository URLs (for example `https://github.com/user/pencms-theme.git` or `/tree/branch`)
- Public GitLab HTTPS repository URLs (for example `https://gitlab.com/group/repo` or `/-/tree/branch`)

PenCMS downloads the archive server-side (`POST /api/themes/install-from-url`), then runs the same validation and install flow as zip upload. Private repositories and non-HTTPS URLs are not supported in v1. Download size is limited to 25 MB; uncompressed contents are limited to 100 MB and 2000 files, matching zip upload.

**Export (distribution):** Admin → Theme Settings → **Export** packages the **current site look** as a shareable installable base:

- Source: site custom fork (`content/sites/{id}/theme/`) when active, otherwise the effective install theme.
- **Style Settings** are baked into `theme.json` defaults and a marked block in `assets/css/skin-*.css` (so a fresh install matches the tuned look without site overrides).
- Registry fonts used in Style Settings are copied into `assets/fonts/` with local `@font-face` rules.
- Fork metadata (`parent`, `origin`, `customized_at`) is stripped; you choose a new **slug**, **name**, and **author**.

Actions:

| Action | API |
|---|---|
| Download packaged `.zip` | `POST /api/sites/{site_id}/theme/package-zip` |
| Save as installed theme on this PenCMS | `POST /api/sites/{site_id}/theme/package-install` |
| Download an unmodified install theme | `GET /api/themes/{slug}/export-zip` |

Packaged zips round-trip through **Import New**. Slug rules match install: lowercase `a-z`, `0-9`, hyphens; cannot be `custom` or start with `_`. Requires `write:theme` and a human admin session (agent tokens are rejected).

**Screenshot recapture:** Site packaging (`package-zip` / `package-install`) recaptures `screenshot.webp` from the live site homepage (1280×800) so exported zips do not ship a stale parent-theme preview. Requires the same preview setup as Theme Customize inspect: `PENCMS_PREVIEW_BASE_URL` (or `[Preview] base_url` in `config.ini`), Playwright + Chromium, Pillow, and a reachable PHP front (`php -S` with `PHP_CLI_SERVER_WORKERS>=4` recommended). If capture is unavailable, packaging still succeeds but omits `screenshot.webp` and returns a warning.

Manual capture (install theme cards): [`frontend-php/cli-tools/capture-theme-screenshots.mjs`](../../frontend-php/cli-tools/capture-theme-screenshots.mjs) supports `--out path/to/screenshot.webp` and `--live-site` (no `config.ini` / `sites.yaml` mutation).

---

## 6. Next reading

| Topic | Doc |
|---|---|
| Complete theme blueprint (layers A/B/C, dual-duty, shortcodes, OG, checklist) | [`pencms-theme-development.md`](pencms-theme-development.md) |
| Operator-tunable style tokens (`style` block in `theme.json`) | [`pencms-theme-development.md`](pencms-theme-development.md) §4.2 |
| PenCMS `[image]` / `.gallery-single` (sizes, centering, classic markdown) | [`pencms-theme-development.md`](pencms-theme-development.md) §8 — *PenCMS `[image]` / `.gallery-single`* |
| Fullbleed on published pages (centered-column prerequisite, sidebar grids) | [`pencms-theme-development.md`](pencms-theme-development.md) §8 — *Fullbleed on published pages* |
| Fullbleed **stage** recipe (asymmetric sidebars / casper-lite) | [`pencms-theme-development.md`](pencms-theme-development.md) §8 — *Wider-than-column stage* |
| Fullbleed **video** double-height gap (`padding-bottom` vs `aspect-ratio`) | [`pencms-theme-development.md`](pencms-theme-development.md) §8 — *Pitfall: fullbleed video* |
| Video iframe must fill 16:9 container (absolute stretch) | [`pencms-theme-development.md`](pencms-theme-development.md) §8 — *Pitfall: video iframe* |
| Shortcode attrs / emitted HTML / matrices | [`traven-shortcodes.md`](traven-shortcodes.md) |
| Dual-scope CSS selector bible | [`traven-theme-development.md`](traven-theme-development.md) |
| `social_preview` field contract | [`dev/theme-social-preview.md`](dev/theme-social-preview.md) |
| Expand/embed host wiring | [`editor-link-suggest-and-expand.md`](editor-link-suggest-and-expand.md) |
