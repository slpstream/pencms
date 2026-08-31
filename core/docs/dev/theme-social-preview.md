# Theme Social / OG contract (`social_preview`)

Canonical contract for theme authors and agents shipping Social Previews and Open Graph image defaults.

Operator how-to: [`../seo-settings.md`](../seo-settings.md). Theme blueprint (incl. condensed OG section): [`../pencms-theme-development.md`](../pencms-theme-development.md). Scaffold / switch / validate: [`../theme-adding.md`](../theme-adding.md).

---

## Why this exists

Every theme must ship **complete** Social / OG-image defaults so a site works with **zero** visits to Settings → SEO → Social Previews. Operators only store **sparse overrides** on the site record; empty / null inherits the active theme.

Resolution order (maker + public meta):

1. Per-page frontmatter / content SEO
2. Site Social overrides (`SiteRecord` flat fields)
3. Theme `theme.json` → `"social_preview"`
4. Engine safety defaults (`services.social_preview.ENGINE_DEFAULTS`)

---

## Where it lives

Extend the theme manifest — **not** a sibling `og-image.json`:

```text
frontend-php/src/blog/themes/{theme-id}/
├── theme.json                 # includes top-level "social_preview"
└── assets/
    ├── fonts/                 # TTF/OTF for Pillow (woff2 alone is not enough)
    └── images/
        ├── defaulthero.jpg    # generator fallback hero (recommended)
        └── watermark.png      # full 1200×630 transparent overlay (optional)
```

Platform engine font fallback (when the theme has no usable TTF):  
`frontend-php/fonts/CourierPrime-Bold.ttf`

---

## Required `social_preview` block

Ship a **complete** object. Use `null` only where “no asset / no meta fallback” is intentional.

```json
"social_preview": {
  "og_accent_color": "#C12929",
  "og_vignette_color": "#FF8000",
  "og_text_color": "#FFFFFF",
  "og_bar_color": "#000000",
  "og_font": "CourierPrime-Bold",
  "og_fonts": {
    "CourierPrime-Bold": "assets/fonts/CourierPrime-Bold.ttf"
  },
  "og_headline_style": "redacted",
  "og_text_case": "upper",
  "og_grade_preset": "noir",
  "og_accent_bar": true,
  "og_watermark": "assets/images/watermark.png",
  "og_default_hero": "assets/images/defaulthero.jpg",
  "og_default_image": null,
  "og_fallback_title": "ARCHIVAL RECORD",
  "og_title_fallback": null,
  "og_description_fallback": null,
  "twitter_card": "summary_large_image"
}
```

### Field reference

| Key | Type | Notes |
|---|---|---|
| `og_accent_color` | hex string | Slanted accent bar / brand accent |
| `og_vignette_color` | hex string | Grade vignette tint |
| `og_text_color` / `og_bar_color` | hex string | Headline fill / redacted bar |
| `og_font` | string | Font id selected from `og_fonts` (or engine fallback id) |
| `og_fonts` | object | Map of id → theme-relative **TTF/OTF** path. Empty `{}` → engine fallback |
| `og_headline_style` | enum | `redacted` \| `shadow` \| `plain` \| `left` \| `left_redacted` \| `center` \| `center_redacted` \| `outline` \| `banner` \| `boxed` \| `underline` \| `caption` \| `poster` |
| `og_text_case` | enum | `upper` \| `title` \| `as_is` |
| `og_grade_preset` | enum | `noir` \| `clean` \| `none` \| `vibrant` \| `warm` \| `cool` \| `fade` \| `high_contrast` \| `sepia` \| `mono` \| `dusk` \| `night` \| `paper` (named looks only; no raw floats in admin) |
| `og_accent_bar` | bool | Bottom slant bar |
| `og_watermark_enabled` | bool | Optional. Composite the watermark PNG. Engine default `true`. Omit from `theme.json` to inherit. |
| `og_watermark` | path \| null | Theme-relative PNG. Full-canvas 1200×630 is the inherit default; not required when `og_watermark_layout` is `corner`. |
| `og_watermark_source` | enum \| omit | Optional. `theme` \| `logo` \| `custom`. Omit to inherit path-based resolution (site upload, else theme file). `logo` uses the site raster logo at render time (not a copy). |
| `og_watermark_layout` | enum \| omit | Optional. `full_canvas` (engine default) \| `corner`. `logo` source always uses corner. |
| `og_watermark_corner` | enum \| omit | Optional. `tl` \| `tr` \| `bl` \| `br`. Engine default `br`. Corner layout only. |
| `og_watermark_scale` | enum \| omit | Optional. `sm` \| `md` \| `lg`. Engine default `md`. Corner layout only. |
| `og_default_hero` | path \| null | Generator fallback when a post has no hero |
| `og_default_image` | path \| null | Optional theme-supplied static site-wide `og:image` |
| `og_fallback_title` | string | Maker title when page has no title |
| `og_title_fallback` / `og_description_fallback` | string \| null | Meta tag fallbacks when page lacks OG fields |
| `twitter_card` | string | e.g. `summary_large_image` |

### Two image jobs (do not collapse)

| Job | Key | Consumer |
|---|---|---|
| Generator fallback hero | `og_default_hero` | `og-image-maker.py` when the post has no featured image |
| Static default share image | `og_default_image` | Public `og:image` when no per-page / generated slug JPG applies |

Site uploads store logical paths under the site’s `assets/images/` (`images/og-default.*`, `images/og-defaulthero.*`, `images/og-watermark.*`) and override these keys sparsely.

---

## Fonts (Pillow reality)

- **Pillow needs local TTF/OTF files.** Theme-bundled webfonts that are only `.woff2` do **not** count as `og_fonts` entries.
- The admin Font dropdown also lists the **core font registry** (`public/assets/fonts/fonts.json`). The renderer converts vendored `.woff2` to TTF on disk (temp cache) at generate time — still no CDN fetch.
- Registry catalog ids are `{family}-{weight}` (bold preferred), e.g. `inter-700`.
- List every theme-private OG-usable face under `og_fonts` with a path under `assets/fonts/`.
- If the theme has no TTF yet, set `"og_fonts": {}` and keep `og_font` as an id the engine can resolve (e.g. `CourierPrime-Bold`) so generation still works.
- Do **not** point at live `fonts.googleapis.com` URLs. A product “Google Fonts” offering must be **vendored files**, not CDN fetches at generate time.
- System font paths (`/usr/share/fonts/...`) are silent engine fallbacks only — never expose them in admin UI.

`supports.custom_fonts` remains advisory for web UI fonts; OG fonts are governed by `social_preview.og_fonts` plus the engine registry catalog.

---

## Twig / public meta expectations

Themes emit `og:*` and `twitter:*` in `_head` / `_header` (not via `ThemeEngine::injectSeoMeta`, which only injects robots + verification).

Prefer presentation globals over hardcoded fallbacks:

| Global | Use |
|---|---|
| `twitter_card` | `<meta name="twitter:card" content="{{ twitter_card \| default('summary_large_image') }}">` |
| `og_title_fallback` | After page `og_title`, before `page_title` / `sitename` |
| `og_description_fallback` | After page `og_description`, before site `meta_description` |
| `og_default_image` | After page `og_image`, before any hard-coded collage / og-default path |

Static builds still prefer `{site_url}/images/og/{slug}.jpg` when `theme.isStatic()` and `slug` is set.

Also declare optional page variables in `theme.json` → `variables` when the theme reads them: `og_title`, `og_description`, `og_image`, `meta_description`.

---

## Checklist for a new theme

1. Add a complete `"social_preview"` block to `theme.json` (copy a keeper such as `starter`, or a thin variant such as `clean` + `plain`).
2. Ship `assets/images/defaulthero.jpg` (and optional `watermark.png` at 1200×630).
3. Ship at least one **TTF/OTF** under `assets/fonts/` and list it in `og_fonts`, **or** rely on the engine CourierPrime fallback with empty `og_fonts` (shared kit: `themes/_asset-kits/cold-war-og/`).
4. Wire `_head` / `_header` to use `twitter_card`, `og_*_fallback`, and `og_default_image`.
5. Smoke: create a site on this theme with **empty** Social tab → publish / run `og-image-maker.py --site=<id>` → confirm image look and public meta.

Reference keepers: `starter`, `editorial`, `casper-lite` (`theme.json` → `social_preview`).  
Shared OG assets (not a theme): `frontend-php/src/blog/themes/_asset-kits/cold-war-og/`.  
Archived Cold War / docs / terminal presets: `themes/_deprecated/{default,docs-public,traven-docs,1337,org-1337,org-traven-docs}/`.

---

## Code map

| Concern | Path |
|---|---|
| Python merge / engine defaults | `backend-python/app/services/social_preview.py` |
| Shared Pillow renderer | `backend-python/app/services/og_image.py` (`render_og_image`; admin preview + CLI) |
| Sparse site fields + API | `site_service.py`, `routers/sites.py` (`social_preview_defaults` on payload; `POST /api/sites/{id}/og-preview`) |
| Uploads | `routers/storage.py` — `POST /storage/og-default`, `og-defaulthero`, `og-watermark` |
| Image generator (batch CLI) | `frontend-php/cli-tools/og-image-maker.py` |
| PHP presentation merge | `frontend-php/src/core/SiteRegistry.php` → `resolveSocialPreview()` / `resolvePresentation()` |
| Twig globals | `ThemeEngine` — `twitter_card`, `og_title_fallback`, `og_description_fallback`, `og_default_image` |
| Admin | `admin-settings-seo.php`, `settings-seo.js` |

---

## Out of scope for themes (engine / admin only)

- Canvas `1200×630`, JPEG quality, timeouts
- Raw saturation / contrast / sharpness floats
- Pixel padding / slant math
- Live-as-you-type WYSIWYG OG canvas in admin (Generate preview uses the shared Pillow renderer)
