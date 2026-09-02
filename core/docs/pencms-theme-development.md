# PenCMS Theme Development Guide

Comprehensive blueprint for building **complete** PenCMS site themes: Twig chrome, dual-duty Traven content skins, shortcode coverage, and Social / OG defaults.

**Quick-start only** (scaffold, switch, validate): [`theme-adding.md`](theme-adding.md).  
**Printable scorecard** (keep in sync with §15): scratch copy under `gitignore/theme-compliance-checklist.md`.

---

## Out of scope for this guide

- Implementing **new** Traven engine shortcodes (grammar, widgets, compiler) — that lives in Traven core.
- Ghost-import / Handlebars themes — PenCMS ships **native Twig only**.
- Designing marketing landing pages unrelated to post/page rendering.
- Rewriting Traven’s dual-scope selector bible — **link and adapt**; do not fork a second incomplete copy. See [`traven-theme-development.md`](dev/traven-theme-development.md).

---

## 1. Purpose & audience

### Who this is for

- Theme designers / front-end engineers building PenCMS site themes.
- Authors who want the **editor skin** to match the **published theme** (dual-duty).
- Agents / humans scoring themes against the compliance checklist (§15).

### How this relates to other docs

| Doc | Role vs this guide |
|---|---|
| [`theme-adding.md`](theme-adding.md) | Quick-start: scaffold, switch, validate. Points here for everything else. |
| [`traven-theme-development.md`](dev/traven-theme-development.md) | Canonical dual-scope CSS / editor skin guide. This guide **composes** it for PenCMS packaging. |
| [`traven-shortcodes.md`](traven-shortcodes.md) | Shortcode inventory (attrs, emitted HTML, classes, align×size matrices). Theme guide links; does not invent attrs. |
| [`dev/theme-social-preview.md`](dev/theme-social-preview.md) | Canonical OG / `social_preview` contract. Condensed checklist here; full field table stays there. |
| [`seo-settings.md`](seo-settings.md) | Operator-facing Social Previews UI. |
| [`editor-link-suggest-and-expand.md`](editor-link-suggest-and-expand.md) | Expand/embed runtime wiring details. |

### Promise of a “complete” PenCMS theme

A theme that only styles chrome (header, cards, grid) is **incomplete**. Complete themes:

1. Style Traven shortcodes under `.traven-preview` (editor + published).
2. Style PenCMS PHP `[image]` output (`.gallery-single`, `.classic-markdown`) on the published site in `styles.css` (§8).
3. Ship dual-duty content CSS usable in the admin editor (`.cm-editor` + preview).
4. Ship Social / OG defaults via `theme.json` → `social_preview`.

Keeper examples: `starter` and `editorial` are the strongest baselines. `casper-lite` is kept and remediated (chrome OK today; historically missing `traven-preview` + content skin) — do not treat chrome-only prose as complete.

---

## 2. Mental model — three layers

```text
┌─────────────────────────────────────────────────────────────┐
│  LAYER C — Social / OG assets                               │
│  theme.json → social_preview · TTF/OTF · defaulthero · mark │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  LAYER B — Content skin (dual-duty)                         │
│  assets/css/skin-{id}.css                                   │
│  scopes: .cm-editor (WYSIWYM) + .traven-preview (HTML)      │
│  shortcodes, alerts, prose, dark mode                       │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  LAYER A — Site chrome                                      │
│  Twig templates/partials · assets/css/styles.css · theme.js │
│  header, nav, index cards, sidebars, FOUC (not loaded in    │
│  editor as the content stylesheet)                          │
└─────────────────────────────────────────────────────────────┘
```

**Key rules**

- Layer B is the **single source of truth** for content appearance in the editor and on the published post.
- Layer A must not be the only place that styles shortcodes / pullquotes / image size·align.
- Layer C is required for zero-config Social Previews ([`dev/theme-social-preview.md`](dev/theme-social-preview.md)).

---

## 3. Quick start

**Scaffold and validate**

```bash
php frontend-php/cli-tools/theme-scaffold.php my-custom-theme
php frontend-php/cli-tools/theme-validate.php my-custom-theme
```

Themes land under `frontend-php/src/blog/themes/{theme-id}/`. Switch the active theme in `config.ini` (see [`theme-adding.md`](theme-adding.md)).

**Minimal viable complete theme**

1. Valid `theme.json` with `supports`, `variables`, complete `social_preview`, and `editor_skin` id.
2. Mandatory templates + partials (§4).
3. `assets/css/skin-{id}.css` covering dual scopes + Traven shortcode matrix (§6–§8).
4. `assets/css/styles.css` for chrome **and** PenCMS PHP gallery / classic-markdown published rules (§8 *PenCMS `[image]` / `.gallery-single`*).
5. Post/page bodies wrap HTML in `class="article-content traven-preview"`.
6. Link the core font registry (`publicAsset('fonts/fonts.css')`) for Style Settings / registry fonts; keep theme-local woff2/`@font-face` only for private identity faces. Ship at least one OG-usable TTF/OTF under `assets/fonts/` **or** explicit empty `og_fonts` → engine fallback.
7. `assets/images/defaulthero.jpg` when `supports.hero_image` is true.

**CSS load order (published site)**

1. Shared font registry (`publicAsset('fonts/fonts.css')`) when the theme uses registry families (Style Settings or identity fonts from the registry).
2. Content skin (`skin-{id}.css`) — or theme-owned base + overlay (e.g. `skin-starter.css` then `skin-editorial.css`).
3. Chrome (`styles.css`).
4. Optional vendor helpers (e.g. expand-embed.css) as documented in §12.

---

## 4. Directory structure & `theme.json` manifest

### Directory tree

```text
frontend-php/src/blog/themes/{theme-id}/
├── theme.json
├── assets/
│   ├── css/
│   │   ├── skin-{id}.css      # Layer B — mandatory for complete themes
│   │   └── styles.css         # Layer A chrome
│   ├── js/
│   │   └── theme.js
│   ├── fonts/                 # woff2 (+ TTF/OTF for OG)
│   └── images/                # defaulthero.jpg, watermark.png, …
├── partials/
│   ├── _head.html.twig
│   ├── _header.html.twig
│   ├── _footer.html.twig
│   ├── _navbar.html.twig
│   ├── _social-links.html.twig  # optional — site social profiles (see §4.1)
│   └── _sidebar-*.html.twig   # optional
└── templates/
    ├── index.html.twig        # mandatory
    ├── post.html.twig         # mandatory
    ├── page.html.twig         # mandatory
    ├── search.html.twig       # mandatory (static publish → search/index.html)
    ├── archive.html.twig      # optional
    ├── post-{category}.html.twig
    ├── archive-{category}.html.twig
    └── page-{slug}.html.twig
```

Partial files use Sass-style underscored names (e.g. `_navbar.html.twig`). When importing, omit the underscore and extension:

```twig
{{ theme.partial('navbar') | raw }}
```

If any mandatory template or partial is missing, the validator fails and the engine throws a `RuntimeException` naming the file.

### 4.1 Site social profile links (`social_links`)

Operators configure profile URLs in **Site Settings → Social Media Links**. ThemeEngine exposes them as the Twig global `social_links` (array of `{ platform, url, label? }`). Empty or unset means render nothing — never hardcode placeholder GitHub/Twitter URLs.

**Opt-in partial:** add `partials/_social-links.html.twig` and include it where the design fits (footer, header, sidebar):

```twig
{{ theme.partial('social-links') | raw }}
```

Ship matching CSS in `styles.css` (`.footer-social`, `.footer-social-link`, etc.). The partial is **not** mandatory; unwired themes simply do not display site social links.

**Reference implementations** (copy the variant that matches your chrome):

| Style | Themes | Notes |
|---|---|---|
| Text labels | `starter`, `casper-lite` | Minimal `.footer-social a` text row |
| SVG icons | `modern`, `solaris` | `.footer-social-link` + per-platform SVGs; custom links use a globe icon |
| Sidebar widget (text) | `toolbox` | Reuses `.secondary-nav-widget` panel in the sidebar column |
| Sidebar widget (icons) | `folio` | `.sidebar-widget` + `.sidebar-social-link` icon row in post sidebar |

New scaffolds emit the text variant and wire the footer by default. Icon themes should copy from `solaris` or `modern` and adjust colors to your palette.

**Twig sandbox:** use allowed filters only (`title`, not `capitalize`). See `frontend-php/src/core/TwigSandboxPolicy.php`.

### 4.2 `style` block — operator-tunable design tokens **[R] for new themes**

PenCMS exposes a theme's CSS custom properties as editable knobs in **Admin Settings → Theme → Style Settings**. Add a top-level `style` object to `theme.json`. The admin reads this schema, renders color pickers and dropdowns, and persists per-site overrides in `data/sites.yaml`. The engine then injects a `<style id="pen-style-overrides">` block into the page `<head>`.

**Policy:** Every **new** theme must ship a working `style` block (chrome colors + typography selects) so operators can tune the look without editing CSS. All current keepers already expose Style Settings. Omitting `style` is acceptable only for legacy/archived themes under migration — not for new work.

Overrides are stored per theme id; if the site switches themes, the old overrides are inert until an operator saves new values for the new theme.

#### Schema

Prefer **chrome knobs** (`--color-*`, `--font-*`) that both `styles.css` and `skin-{id}.css` define on `:root`, then **alias** `--traven-*` (and theme-private aliases) from those knobs. Do not maintain two independent palettes.

```json
"style": {
  "dark_scope": { "selector": "html.cm-wysiwym-dark, html[data-theme=\"dark\"]" },
  "groups": [
    {
      "id": "colors",
      "label": "Color Palette",
      "fields": [
        {
          "id": "bg",
          "label": "Background",
          "type": "color",
          "var": "--color-bg",
          "default": "#ffffff",
          "dark_default": "#0f172a"
        },
        {
          "id": "accent",
          "label": "Accent / Links",
          "type": "color",
          "var": "--color-accent",
          "default": "#0f172a",
          "dark_default": "#38bdf8"
        }
      ]
    },
    {
      "id": "typography",
      "label": "Typography",
      "fields": [
        {
          "id": "font-body",
          "label": "Body Font",
          "type": "select",
          "var": "--font-body",
          "default": "'Newsreader', Georgia, serif",
          "options": [
            { "value": "", "label": "Theme default" },
            { "value": "'Newsreader', Georgia, serif", "label": "Newsreader" },
            { "value": "Georgia, 'Times New Roman', serif", "label": "Georgia" }
          ]
        }
      ]
    }
  ]
}
```

#### Field rules

| Field | Required | Description |
|---|---|---|
| `id` | yes | Unique within the theme. Used as the override key. |
| `label` | yes | Display label in the admin Style Settings pane. |
| `type` | yes | `color` or `select`. |
| `var` | yes | CSS custom property name the override is assigned to. |
| `default` | yes | Fallback value when the operator has not overridden this field. |
| `dark_default` | for dark-capable themes | For `color` fields only. Required on every paired color when the theme ships dark mode. |
| `options` | for `select` | Array of `{ "value": string, "label": string }`. Use `""` value for "theme default". For font fields (`id` starting with `font` or `var` containing `font`), the admin API and ThemeEngine merge every stack from `public/assets/fonts/fonts.json` at runtime — list Theme default, identity/private faces, and any system stacks; you do not need to paste the full registry. |

#### Dark scope

Required when the theme ships a dark mode (toggle and/or class/attribute FOUC). When omitted, the admin may still show dark inputs for fields with `dark_default`, but the engine has no rule to scope them under.

- `selector`: emitted verbatim as the dark rule's selector. Must match your theme's **actual FOUC / toggle mechanism** — e.g. `html.cm-wysiwym-dark`, or `html.cm-wysiwym-dark, html[data-theme="dark"]` when the FOUC script sets both. Selector lists are allowed. Dark-first themes that use a light class (e.g. `html.theme-light`) still put **dark** overrides under the dark selector (`html.cm-wysiwym-dark`).
- `media`: `(prefers-color-scheme: dark)`. The engine emits `@media (prefers-color-scheme: dark) { :root { … } }` with dark overrides. Only correct for themes that follow the OS and have **no** manual toggle — if a toggle exists, use `selector`.

Chrome (`styles.css`) and skin must both flip the **same chrome tokens** under that scope. A skin-only dark palette with light-only chrome tokens is a defect (nav/body stay light while content goes dark).

Match this to however your theme implements dark mode. See §6.

#### How overrides are applied

Only non-empty values are persisted. The engine injects a `<style id="pen-style-overrides">` block at the **end** of the page `<head>`, and every declaration carries `!important`. Values are validated server-side:

- `color` must be a valid CSS color (hex, `rgb()`, `rgba()`, `hsl()`, `hsla()`).
- `select` must match one of the declared `options` (after the runtime font-registry merge for font fields).

The generated CSS uses the CSS variable declared in `var`. For example, setting `bg` to `#f5f5f5` produces:

```css
:root {
  --color-bg: #f5f5f5 !important;
}
```

And with `dark_scope.selector` set to `html.cm-wysiwym-dark`:

```css
html.cm-wysiwym-dark {
  --color-bg: #0f172a !important;
}
```

**Paired light/dark colors must both be explicit.** Light overrides land on `:root { … !important }`, which also matches dark mode. If an operator changes only the light picker, the API / admin JS / ThemeEngine **pin** that field's `dark_default` (or the saved dark value) under `dark_scope` so the light color cannot leak into dark mode. Do not rely on "omit dark = inherit theme CSS" once a light companion is customized — the `:root !important` light rule would win.

`!important` is deliberate: themes may re-declare the same tokens under higher-specificity layers (e.g. `html[data-theme="light"]` / `html[data-theme="dark"]` blocks), and an operator's explicit choice must win over all of them. Do not mirror this with `!important` in your own theme defaults — keep defaults plain so overrides stay effective.

#### Best practices

- Only expose variables your theme actually consumes and that are safe for operators to change.
- Define chrome knobs on `:root` in **both** `styles.css` and `skin-{id}.css`; alias `--traven-*` from them.
- Gradients, washes, sale flags, and progress bars that belong to accent/panel/bg must track tokens (`var(...)` or `color-mix(in srgb, var(--token) …)`), not frozen rgba hex copies.
- Use `dark_default` on every paired color when the theme ships dark mode; omit dark inputs for light-only themes.
- **Every non-system font family offered in a `select` option must resolve via the core font registry** (`frontend-php/public/assets/fonts/` — `fonts.json` + `fonts.css` + woff2). Link the shared sheet in `_head` with `{{ publicAsset('fonts/fonts.css') }}` (admin editor loads the same sheet automatically). System stacks (Georgia, `ui-monospace`, …) need no files. Private/identity webfonts may still live under the theme's `assets/fonts/` with local `@font-face` in `skin-{id}.css`; `theme-validate.php` accepts those as an exception. Prefer registry families over copying woff2 into every theme.
- Font dropdowns are **registry-merged at runtime**. Keep `theme.json` options short: Theme default, optional identity stacks, optional system stacks.
- Smoke-test Style Settings before calling the theme done: change accent + background in light (and dark if present); confirm chrome and content update; confirm dark does not inherit a light-only change.

### Example manifest shape

```json
{
  "type": "native",
  "name": "My Custom Theme",
  "version": "1.0.0",
  "author": "Your Name",
  "license": "MIT",
  "description": "A modern responsive theme for PenCMS.",
  "editor_skin": "my-custom-theme",
  "editor_skin_base": [],
  "supports": {
    "toc": true,
    "hero_image": true,
    "composite": true,
    "seo_meta": true,
    "custom_fonts": false,
    "sidebars": true,
    "markdown_alternate": true
  },
  "variables": {
    "hero_title": { "type": "string", "required": true },
    "posts": { "type": "array", "required": false },
    "dossiers": { "type": "array", "required": false },
    "hero_image": { "type": "string", "required": false },
    "deck": { "type": "html", "required": false },
    "trumpet": { "type": "string", "required": false },
    "date": { "type": "string", "required": false },
    "author": { "type": "string", "required": false },
    "dateline": { "type": "string", "required": false },
    "page_title": { "type": "string", "required": false },
    "tagline": { "type": "string", "required": false },
    "og_title": { "type": "string", "required": false },
    "og_description": { "type": "string", "required": false },
    "og_image": { "type": "string", "required": false },
    "meta_description": { "type": "string", "required": false }
  },
  "style": {
    "dark_scope": { "selector": ".cm-wysiwym-dark" },
    "groups": [
      {
        "id": "colors",
        "label": "Color Palette",
        "fields": [
          {
            "id": "bg",
            "label": "Background",
            "type": "color",
            "var": "--traven-bg",
            "default": "#ffffff",
            "dark_default": "#0f172a"
          },
          {
            "id": "accent",
            "label": "Accent",
            "type": "color",
            "var": "--traven-caret",
            "default": "#0f172a"
          }
        ]
      },
      {
        "id": "typography",
        "label": "Typography",
        "fields": [
          {
            "id": "font-body",
            "label": "Body Font",
            "type": "select",
            "var": "--traven-font-body",
            "default": "'Roboto', sans-serif",
            "options": [
              { "value": "", "label": "Theme default" },
              { "value": "'Inter', sans-serif", "label": "Inter" },
              { "value": "'Courier Prime', monospace", "label": "Courier Prime" }
            ]
          }
        ]
      }
    ]
  },
  "social_preview": {
    "og_accent_color": "#2563EB",
    "og_vignette_color": "#64748B",
    "og_text_color": "#FFFFFF",
    "og_bar_color": "#0F172A",
    "og_font": "CourierPrime-Bold",
    "og_fonts": {},
    "og_headline_style": "plain",
    "og_text_case": "title",
    "og_grade_preset": "clean",
    "og_accent_bar": true,
    "og_watermark": null,
    "og_default_hero": "assets/images/defaulthero.jpg",
    "og_default_image": null,
    "og_fallback_title": "Untitled",
    "og_title_fallback": null,
    "og_description_fallback": null,
    "twitter_card": "summary_large_image"
  }
}
```

`variables` keys are a data contract for listing vs post vs SEO fields the theme expects Twig to receive. Keep them aligned with what templates actually read.

---

## 5. Template hierarchy & data contract

### Resolution tables

| Template context | Renders | Resolution hierarchy |
|---|---|---|
| Single post | Article or composite dossier | `post-{category}.html.twig` → `post.html.twig` |
| Static page | Independent static page | `page-{slug}.html.twig` → `page.html.twig` |
| Category list | List of articles in a category | `archive-{category}.html.twig` → `archive.html.twig` → `index.html.twig` |
| Home / index | Main publication feed | `index.html.twig` (no overrides) |

`post.html.twig`, `index.html.twig`, `page.html.twig`, and `search.html.twig` are **mandatory**. `archive.html.twig` is optional (falls back to `index.html.twig`). Static publish always renders `search` → `search/index.html`; without the search template the build fatals.

**Category comes from frontmatter `category:`, not URL alone.** See §13.

### Mandatory markup contract

```twig
<div class="article-content traven-preview">
  {{ post.content_html | raw }}
</div>
```

- Both classes are required on post and page body wrappers (and on category/slug overrides that render body HTML).
- Missing `traven-preview` means shortcode / skin rules do not apply — the historical `casper-lite` / chrome-only failure mode.
- Optional: also put `traven-preview` on `<body>` (starter pattern) when you want category theme tokens on the document root. Prefer the content wrapper for shortcode fidelity; use `body` only when chrome tokens need the same host class.

### Theme helpers

| Twig helper / function | Description |
|---|---|
| `{{ theme.asset('css/styles.css') }}` | Paths for files shipping **with the theme** (`/assets`). Handles CDNs and static builds. |
| `{{ theme.contentAsset(hero_image) }}` | Paths for dynamic content assets (uploaded images). |
| `{{ theme.partial('navbar') }}` | Includes a reusable partial. |
| `{{ theme.linkCss('css/skin-….css') \| raw }}` | Stylesheet `<link>` for a theme CSS file. |
| `{{ theme.inlineCss('css/skin-….css') \| raw }}` | Inlines CSS inside `<style>`, rewriting local image/font URLs. |
| `{{ theme.getLogoUrl() }}` | Site logo URL from config + theme/shared assets. |
| `{{ theme.isStatic() }}` | `true` during a static SSG build. |
| `{{ contentUrl(dossier) }}` | Resolves an exact localized content URL or the real default-language fallback URL. Never concatenate `/<lang>/` in Twig. |
| `{{ archiveUrl(category) }}` | Resolves the current language's canonical archive URL. |
| `{{ theme.partial('language-switcher') \| raw }}` | Optional shared language switcher. It renders only when the current detail has at least two exact published versions. |
| `{{ theme.partial('faqs') \| raw }}` | Optional Q&A block placement on post/page templates. **Recommended:** place inside the reading column (e.g. `.content-column`, `.post-prose`) after article body and before comments. Suppresses engine auto-injection. The global partial emits structure and class hooks (`.pen-qa`, `.pen-qa-heading`, `dl`/`dt`/`dd`) only — **no theme chrome**. Style it in theme CSS the same way you style `*-discussion` for comments (folio is the reference). |
| `{{ theme.partial('comment-thread') \| raw }}` | Published-comment list when Site Settings **Reader comments** is on (default off). Engine returns empty when the site flag is off. Global fallback is `@global/_comment-thread.html.twig`. |
| `{{ theme.partial('feedback-form', { kind: 'comment', parent_slug: slug is defined ? slug : '' }) \| raw }}` | Comment form when the site flag is on; `kind: contact` is a separate contact form and is **not** this flag. Global fallback is `@global/_feedback-form.html.twig`. |
| `loadThemeConfig('category_colors.json')` | Loads JSON: first `pencms-data/<filename>`, then theme root. |

### Globals & collisions

Available in all templates and partials:

- `sitename`, `tagline`, `site_url`, `base_path`, `category` (slug or `null`).
- `social_links`: site-scoped profile URLs from Site Settings (§4.1). Each entry: `platform`, `url`, optional `label` (for `custom`).
- `authors`: site-scoped contributor bios from `content/sites/{site_id}/authors.yaml` (sorted by `sort_order`). Fields include `slug`, `name`, `bio`, `website`, `avatar`, `email`, `role`, `sort_order`.
- `author` (profile object): site-default sidebar / profile — first entry in `authors` by `sort_order`, else first `data/users` UserPublic fallback (`display_name`, `bio`, `website`, `avatar`).

**Name collision:** Post/page frontmatter may expose a free-text byline string as `author`, which shadows the global profile object in post templates (`By {{ author }}` prints the string). When you call `theme.partial('sidebar-profile')`, ThemeEngine re-injects a profile **array**: it matches the page byline to `authors[].name` (case-insensitive); unmatched custom bylines get `display_name` only with empty bio and `avatar: null`; pages with no byline keep the site-default profile. **Omit `<img>` when `author.avatar` is empty** — do not fall back to a theme placeholder that 404s. Escape plain-text bios (`|e`). See knowledgebase **C6**.

### i18n render and output contract

ThemeEngine owns the language-sensitive document plumbing in both dynamic preview and static output:

- `strings` is always available and resolves engine defaults → theme `strings.json` → site default-language strings → site target-language strings, per key. Use `{{ strings.search }}` and other dictionary keys for reader chrome instead of hardcoded English. Engine Q&A (`.pen-qa`) uses `strings.faq` or `strings.backgrounder`; opt into the Backgrounder label with `"qa_heading": "backgrounder"` in `theme.json` — do not scrape theme Twig, and do not change the `FAQPage` `@type`. **Place Q&A explicitly** via `{{ theme.partial('faqs') | raw }}` inside the article measure (same column as body text, before discussion). ThemeEngine skips auto-injection when `.pen-qa` is detected in the rendered output. **Fallback only:** if the theme omits the partial, ThemeEngine injects before `</main>` (or `</body>` when there is no `<main>`). That fallback often lands outside inner `.wrap` / `.post-prose` gutters — full-bleed themes will show edge-to-edge FAQ unless the partial is placed in the template. Reader comments are a **site** opt-in (Settings → Site → Reader comments, default off). When off, `comment-thread` and `kind: comment` `feedback-form` render empty even if the template calls them. When on, ThemeEngine injects the pair on post templates if `.pen-comments` / a `kind=comment` form is missing (skip-if-present, then before `</main>`). Contact forms (`kind: contact`) are unchanged. Comment and feedback chrome uses `strings.comments`, `strings.leaveComment`, `strings.contactUs`, `strings.postComment`, `strings.send`, `strings.feedbackName`, `strings.feedbackMessage`, `strings.feedbackOptional`, `strings.feedbackReceived`, `strings.feedbackRateLimited`, and `strings.feedbackSendFailed`.
- Place `comment-thread` then `feedback-form` inside the article measure or a dedicated wrapper when you want layout control. After `</main>` they inherit the next ancestor (often the canvas). Override `.pen-comments` / `.pen-feedback` in theme CSS; do not fork the Twig unless the HTML must change. Theme-local `partials/_comment-thread.html.twig` or `partials/_feedback-form.html.twig` still win over the global fallback. Live `/blog/` comment POSTs stay `/api/v1/feedback` on this origin; baked `dist/` POSTs to `{feedback_relay_url or https://feedback.pencms.org}/submit` when a submission key exists.
- When i18n is active, `site.language`, `site.default_language`, `site.languages`, `site.language_labels`, and `site.i18n_active` describe the current render. Inactive sites retain the legacy context shape, so a reusable theme may use `site.language|default('en')` when it reads `site` directly.
- ThemeEngine replaces the document `<html lang>` and injects the exact published detail-page `<link rel="alternate" hreflang="…">` set into `<head>`. Do not build a second peer-discovery path or emit draft/missing alternates in Twig.
- Listing rows carry their actual `language` and `is_fallback`. Always call `contentUrl(dossier)` so translated rows use `/<lang>/<slug>/` and fallback rows continue to use the default URL. Use `archiveUrl()` for archive links.
- Dynamic public entry points and static generation supply `canonical_url` for default and localized detail, home, search, and archive renders. ThemeEngine injects the canonical link centrally; use the context for OG metadata and do not reconstruct locale paths in Twig.
- `[link]` resolves an exact localized sibling when one is live and otherwise links to the real default URL. `[expand]` / `[embed]` request the exact current locale and silently omit a missing peer rather than mixing body languages; their reader CTA comes from `strings.readMore`.
- Generated reading-time chrome uses `strings.minuteRead`, and datelines use `IntlDateFormatter` for the current locale when PHP Intl is available.
- The shared `language-switcher` partial is progressive enhancement and strictly opt-in. Themes may include it where appropriate; a complete theme is not required to force switcher chrome. SEO alternates remain present without it or without JavaScript.
- Search documents include `lang` only on active multilingual sites. RSS and generated public-site `llms.txt` remain default-language-only; themes must not advertise localized variants that do not exist.

### Index & archive listing

`dossiers` is an array of listing structures. Typical feed loop:

```twig
{% for dossier in dossiers %}
  <article class="post-card">
    <h2><a href="{{ dossier.slug }}">{{ dossier.hero_title | default(dossier.title) }}</a></h2>
    {% if dossier.pinned %}
      <span class="pin-label" aria-label="Pinned">Pinned</span>
    {% endif %}
    <p>{{ dossier.deck | striptags }}</p>
  </article>
{% endfor %}
```

`dossier.pinned` (boolean) comes from frontmatter `pinned: true`. Public listings already sort pinned posts first (then by `date` desc). Themes may show a badge or split pinned/unpinned rails; omitting any pin UI is fine.

### Post & page context

- `hero_title`, `hero_image`, `deck`, `trumpet`, `date`, `dateline`
- `author` (byline string from frontmatter) — distinct from the profile object re-injected in sidebar-profile
- `is_composite`, `page_content` (static page body in `page.html.twig`)
- `posts`: one or more fragments:

```twig
{% for post in posts %}
  <article id="{{ post.id }}">
    {% if post.title is not empty and posts|length > 1 %}
      <h2>{{ post.title }}</h2>
    {% endif %}
    <div class="article-content traven-preview">
      {{ post.content_html | raw }}
    </div>
  </article>
{% endfor %}
```

Tags and metadata live at the **fragment** level (`post.tags`, `post.metadata`), not on the parent page. Always render them inside the fragment loop. `post.metadata` is an array of strings; `post.tags` is an array of objects with `label` and `href`.

### Entry points and rendering flow

```text
Entry point (e.g. post.php)
  └── ThemeEngine::fromConfig('config.ini')
        ├── Reads theme.json metadata
        └── Initializes Twig + helpers
  └── $theme->render($templateName, $data, $key = null)
        ├── Resolves category/slug overrides
        └── Falls back to the base template
```

| Entry point | Render call | Template resolved |
|---|---|---|
| `post.php` | `$theme->render('post', $data)` | `post-{category}` or `post` |
| `index.php` | `$theme->render('index', $data)` | `index` |
| `page.php` | `$theme->render('page', $data, $slug)` | `page-{slug}` or `page` |
| `category.php` | `$theme->render('archive', $data, $category)` | `archive-{category}` → `archive` → `index` |
| Static generators | Same `render` calls | Same resolution |

For `post`, category is read from frontmatter. For `archive` / `page`, the key is passed explicitly as the third argument.

---

## 6. CSS architecture

### Split

| File | Owns | Must not own |
|---|---|---|
| `skin-{id}.css` | Prose, Traven shortcode classes, alerts, dual-scope editor widgets, content dark mode, caption tone | Site header grid, post-card listing chrome |
| `styles.css` | Layout grid, header/nav/footer, cards, sidebars, chrome dark tweaks, **PenCMS PHP shortcode layout** (`.gallery-single`, `.classic-markdown`, size/align on published HTML) | Traven-only shortcode rules with no PenCMS gallery fallback; fullbleed breakout (theme-specific — see §8) |

> [!IMPORTANT]
> **PenCMS `[image]` is not the same markup as Traven `img.traven-image-shortcode`.** Both can appear in content. A complete published theme must style **both** paths until PHP unifies them (see §8 — *PenCMS `[image]` / `.gallery-single`*).

> [!WARNING]
> **Tailwind CSS & framework Preflight gotcha (editor ≠ published):**
> Themes that use CSS-framework resets (Tailwind `@tailwind base` / CDN Preflight, Bootstrap reboot, Normalize, etc.) can look fine on the **published** post page while the **admin WYSIWYM editor** drifts — or the reverse.
>
> PenCMS’s in-house posture is **prefer plain vanilla CSS** for dual-duty themes (`starter`, `editorial`, `academic`, `colorful`, `dark`, `modern`). Independent designers may still ship Tailwind (or any other framework) for chrome; they **must** treat the risks below as required work, not optional polish.
>
> **Why vanilla themes stay in sync:** The admin editor loads only `skin-{id}.css` (plus Traven core). Published pages load that same skin **and** chrome (`styles.css`, Tailwind CDN, etc.). Vanilla themes put dual-duty rules (prose, shortcodes, `@font-face`) in the skin, so both surfaces share one stylesheet. Framework chrome that only exists on the published page never runs in the editor.
>
> **Risks to watch if you use Tailwind (or similar):**
>
> 1. **Preflight / base resets** — Published pages get global rules the editor never sees (e.g. `html`/`body` color like `#0f172a`, unstyled `figcaption` / `mark`). Override content tokens on `.traven-preview` and `.traven-preview p` (`color: var(--traven-text) !important`; `font-weight: 400 !important`) and style captions for **both** Traven (`figcaption.traven-image-caption`) and PenCMS PHP (`.gallery-single .caption`, `.figure-full .caption`, `.classic-markdown-figure .caption`, `figcaption.caption`).
> 2. **`@font-face` must live in the skin** — Admin resolve loads `assets/css/skin-*.css` only. Faces declared solely in chrome `styles.css`, or inside a `<style type="text/tailwindcss">` block, **do not register in the editor**. The skin will name e.g. `"Inter"` and silently fall back to `-apple-system` / system UI while the published page paints the real webfont — same hex/weight, visibly different “ink.” Put self-hosted `@font-face { src: url('../fonts/….woff2') }` at the top of `skin-{id}.css` (see `editorial` / `modern` / remediated `casper-lite`). Keep chrome free to *reference* those families; do not make chrome the only place faces are defined.
> 3. **Do not treat Tailwind Play / `type="text/tailwindcss"` as a font host** — `@font-face` inside deferred Tailwind compilation is unreliable (FOUT / missing faces). Use a real stylesheet `<link>` for the skin (as `_header` does with `theme.linkCss('css/skin-….css')`).
>
> **Quick parity check:** In DevTools, compare computed `font-family`, `font-weight`, and `color` on a body paragraph in `admin-editor.php` vs `post.php`. They must match the skin’s intended stack — not “Inter on publish, system UI in the editor.”

```text
               +-------------------------------------------+
               |                  THEME                    |
               +---------------------+---------------------+
                                     |
             +-----------------------+-----------------------+
             |                                               |
             v                                               v
+--------------------------+                    +--------------------------+
|    skin-{id}.css         |                    |        styles.css        |
+--------------------------+                    +--------------------------+
|  - --traven-* tokens     |                    |  - Grid & layout rules   |
|  - @font-face (required) |                    |  - Header, footer, nav   |
|  - .traven-preview rules |                    |  - Sidebar components    |
|  - Shortcode components  |                    |  - Mobile menu styling   |
|  - GitHub-style alerts   |                    |  - Optional Tailwind chrome |
|  - WYSIWYM editor sync   |                    |  - Chrome dark tweaks    |
+--------------------------+                    +--------------------------+
```

### Tokens

Prefer `--traven-*` CSS variables for colors/fonts so chrome can retint without forking shortcode rules. Use `starter`’s variable set as the baseline override surface — **including the three font stacks** (required for dual-duty canvas + title block; see §7 *Admin editor gotchas*):

```css
:root {
  --traven-font-display: Georgia, Cambria, "Times New Roman", Times, serif;
  --traven-font-body: Georgia, Cambria, "Times New Roman", Times, serif;
  --traven-font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;

  --traven-bg: #0d1117;
  --traven-text: #e6edf3;
  --traven-muted: #8b949e;
  --traven-border: #30363d;
  --traven-caret: #3fb950;
  --traven-code-bg: #07090e;
  --traven-widget-bg: #161b22;
  --traven-widget-border: #30363d;
  --traven-alert-note-border: #58a6ff;
  --traven-alert-note-bg: rgba(88, 166, 255, 0.1);
  --traven-alert-note-text: #58a6ff;
  --traven-alert-tip-border: #3fb950;
  --traven-alert-tip-bg: rgba(63, 185, 80, 0.1);
  --traven-alert-tip-text: #3fb950;
}
```

Mono-only / single-face themes still define all three — point `--traven-font-display`, `--traven-font-body`, and `--traven-font-mono` at the same family.

### Single-mode default policy & optional dark mode

> [!IMPORTANT]
> **PenCMS Theme Mode Policy:**
> - **Single-mode by default:** Most themes on PenCMS should have **only one mode and no way to toggle**. Dark mode is **not first-class**.
> - **Exception, not a requirement:** PenCMS themes can include a dark variant (e.g. `starter`) or be dark-first (e.g. `dark`), but this is the **exception, not the rule**. A dark mode variant should **only** be built if the user specifically asks for it at the time of building the theme, and it is **never** a requirement of the system or a preference in the documentation.
> - **Traven Editor single-mode reality:** Traven Editor was originally planned to have a light/dark toggle, so legacy skins from Traven were built with dark variants. This feature was **abandoned**, however, and the editor currently offers **no dark toggle**. Dark variants in legacy Traven skins are **dead code**.
> - **No admin editor toggle:** Even for themes like `starter` that incorporate a dark mode toggle on the published site, there is **no way inside the Traven Editor (`frontend-php/src/admin/admin-editor.php`) to switch between light and dark while editing**. Adding an editor toggle to admin chrome is **not on the approved roadmap for PenCMS and will not happen**. The editor always operates in one mode: the single default mode of the active theme skin.

If a theme is specifically built with a user-requested dark mode variant, the published frontend may include a toggle. Place a FOUC script in `_head.html.twig` **before** stylesheets:

```html
<script>
    (function() {
        let scheme = null;
        try {
            scheme = localStorage.getItem('color-scheme');
        } catch (e) {}
        if (!scheme) {
            try {
                const match = document.cookie.match(/(^|;)\s*color-scheme\s*=\s*([^;]+)/);
                scheme = match ? match[2] : null;
            } catch (e) {}
        }
        if (scheme === 'dark' || (!scheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            document.documentElement.classList.add('cm-wysiwym-dark');
        } else {
            document.documentElement.classList.remove('cm-wysiwym-dark');
        }
    })();
</script>
```

In `assets/js/theme.js`, toggle `.cm-wysiwym-dark` on click and persist `localStorage` + cookie (only for themes with explicit dark variants):

```javascript
const toggleBtn = document.getElementById('theme-toggle');
if (toggleBtn) {
  toggleBtn.addEventListener('click', () => {
    const isDark = document.documentElement.classList.contains('cm-wysiwym-dark');
    const newTheme = isDark ? 'light' : 'dark';
    document.documentElement.classList.toggle('cm-wysiwym-dark', newTheme === 'dark');
    localStorage.setItem('color-scheme', newTheme);
    document.cookie = "color-scheme=" + newTheme + "; path=/; max-age=31536000; SameSite=Lax";
  });
}
```

### Editor constraints (dual-duty)

- No `float` / vertical `margin` on `.cm-wysiwym-*-container` in editor scope; use auto-margins for align ([`traven-theme-development.md` §5](dev/traven-theme-development.md)).
- Preview scope may use float for left/right images.
- Base `.cm-editor` / `.traven-preview` typography must use `!important` (admin Tailwind + `traven.css` otherwise win) — see §7 *Admin editor gotchas*.
- Define `--traven-font-display`, `--traven-font-body`, and `--traven-font-mono` on `:root`.
- Style `.post-detail-trumpet` / `.post-detail-title` / `.post-detail-deck` once in the skin (admin Title Blocks reuse those classes).

---

## 7. Dual-duty themes (theme ↔ editor skin)

### Definition

A dual-duty theme ships one Layer B CSS file (or a theme-owned base + overlay pair) that styles **both**:

1. Admin TravenEditor (`.cm-editor` + preview pane `.traven-preview`)
2. Published post HTML (`.article-content.traven-preview`)

### Source of truth

```text
themes/{id}/assets/css/skin-{id}.css
        │
        ├─► Published site (_head linkCss)
        └─► Admin editor (resolve from active theme; vendor skins = fallback only)
```

**Do not** maintain copies under `frontend-php/public/assets/vendor/traven/skins/` — that directory was removed after S8.5. Theme-owned `assets/css/skin-*.css` is the only runtime skin source; missing active-theme stacks fall back to `themes/starter`.

### Overlay pattern (locked)

**Theme-owned base + personality overlay.** Example: `editorial` ships both `skin-starter.css` and `skin-editorial.css` inside `themes/editorial/assets/css/` and loads them in that order, then `styles.css`:

```twig
{{ theme.linkCss('css/skin-starter.css') | raw }}
{{ theme.linkCss('css/skin-editorial.css') | raw }}
{{ theme.linkCss('css/styles.css') | raw }}
```

Do **not** rely on cross-theme path sharing (reading another theme’s folder at runtime) as the dual-duty source of truth. Copy or vendor the base skin into the theme that needs it.

Declare the stack in `theme.json`:

```json
{
  "editor_skin": "editorial",
  "editor_skin_base": ["starter"]
}
```

- **`editor_skin`**: personality stem (picker key / default).
- **`editor_skin_base`**: optional ordered base stems loaded before personality.

Admin resolve (S5 + S8.5) loads `/blog/themes/{active}/assets/css/skin-{stem}.css` for that stack and defaults `workspacePrefs.editorSkin` to `editor_skin`. The editor skin **picker lists every installed theme** that has a resolvable theme-owned skin stack (labels from `theme.json` `name`; active theme marked `(active)`). Overlay themes expose one picker key (`editor_skin`) whose `hrefs` include the full base + personality stack. If the active theme’s stack is missing, boot falls back to `themes/starter` (then empty / `traven.css` only) — there is no vendor skins directory. Workspace prefs store `editorSkinThemeId`; when the active site theme changes, the next editor load resets the default skin to the new theme’s `editor_skin`. A user-picked **theme** skin override under the **same** site theme is retained until the theme id changes (unknown / retired keys reset to boot).

### Parity expectations

- Near pixel-perfect for shortcodes, typography, quotes, alerts, media size/align.
- Chrome (nav, cards) will differ — that is expected.
- Skin must remain usable **without** loading `styles.css`.

### Admin editor gotchas (hero title + cascade)

> [!WARNING]
> **Partial skin in `admin-editor.php` (system fonts / unstyled title strip):**
> Loading `skin-{id}.css` is not enough. PenCMS admin chrome keeps [`admin-editor.css`](../../frontend-php/src/admin/css/admin-editor.css) as **thin glue only** (transparent inputs; `h1.post-detail-title textarea` inherits). Title-block personality must live in the **skin**, once, on the same classes published Twig uses.
>
> **Failure mode:** Headings inside CodeMirror look themed, but trumpet / headline / deck stay Inter (or system sans), body text uses a generic mono stack, and `mark` / highlights keep starter yellow. Symptom seen when scaffolding a dual-duty theme that only sets a custom `--fw-font` (or similar) without the `--traven-font-*` triad / `.post-detail-*` rules.
>
> **Required in every dual-duty `skin-{id}.css`:**
>
> 1. **Font tokens on `:root`**
>    ```css
>    :root {
>      --traven-font-display: 'YourDisplay', …;
>      --traven-font-body: 'YourBody', …;
>      --traven-font-mono: 'YourMono', …;
>    }
>    ```
>    Missing vars → generic fallbacks on any rule that references the triad.
>
> 2. **Force the base stacks**
>    ```css
>    .cm-editor,
>    .traven-preview {
>      font-family: var(--traven-font-body) !important;
>      color: var(--traven-text) !important;
>      background-color: var(--traven-bg) !important;
>    }
>    ```
>    Without `!important`, Tailwind Preflight / `traven.css` win in the editor.
>
> 3. **Style trumpet / title / deck once** on `.post-detail-trumpet`, `.post-detail-title`, and `.post-detail-deck` (admin markup in `admin-editor.php` uses these classes inside `.hero-title-block.traven-preview`). Do **not** put type scale in `styles.css` and mirror it again under a separate admin-only selector list. Use `!important` so admin inputs beat Preflight. Leave structural chrome (eyebrow flex, borders, margins) in `styles.css`. See `themes/starter` / `themes/freedomware` / `themes/academic`.
>
>    **Exception — hollow / stroke titles:** `color: transparent` plus `-webkit-text-stroke` or `background-clip: text` makes the native `hero_title` textarea (not CodeMirror) an outline with no caret. Keep the neon on published `h1.post-detail-title`. Override only `.hero-title-block.traven-preview .post-detail-title` (and its `textarea`) with a solid `color`, no stroke/shadow, and an explicit `caret-color`. See `themes/night`.
>
> 4. **Editor marks / widgets** — define `--traven-highlight-bg` (and related tokens) and style `.cm-wysiwym-bold` / `-italic` / `-highlight` / `-inline-code` / headings so the canvas is not half-starter.
>
> **Quick parity check:** On `admin-editor.php`, DevTools → computed `font-family` / size / weight on trumpet, headline, deck, and a body line must match the published post header personality (slight layout drift is OK). Sticky note: [`knowledgebase.md`](dev/knowledgebase.md) **A9**.

### Published chrome gotchas (`<body class="traven-preview">`)

Many PenCMS themes set `traven-preview` on `<body>` so expand-embed and dual-duty tokens apply site-wide. That is valid, but **every skin rule written as `.traven-preview …` also hits header, footer, nav, and post chrome** — not only `.article-content`.

| Symptom | Cause | Fix |
|---|---|---|
| Sitename / nav links underlined | `.traven-preview a { text-decoration: underline }` in the skin | Scope prose links to `.article-content a` (or add chrome exceptions) |
| Huge gap above post `hero_title` | `.traven-preview h1 { margin-top: 2em }` applies to `.post-detail-title` | Reset chrome headings (`.post-detail-header .post-detail-title { margin-top: 0 }`) and use **higher specificity** for the intended title size |
| Footer/header tables pick up article table borders | `.traven-preview table { … }` in the skin | Scope to `.article-content table`, `th`, `td` |
| `sub` / `sup` render as full-size baseline text | Aggressive reset uses `font: inherit` on `*` | Re-declare `sub, sup { font-size: 75%; position: relative; … }` in `styles.css` after the reset |
| Header, main, footer columns misaligned width | `display: flex` + `align-items: center` on `body` lets siblings shrink to content | One shared column track: `body { display: grid; grid-template-columns: minmax(0, 80ch); justify-content: center }` and `width: 100%` on `.site-header`, `.main-container`, `.site-footer` |
| Dark-mode toggle text disappears on hover | `background: currentColor; color: var(--fw-bg)` while tokens do not invert on `html.cm-wysiwym-dark` | Set explicit `html.cm-wysiwym-dark body { color; background }` in chrome; hover with `background: var(--fw-color); color: var(--fw-bg)` |

**Prefer scoped selectors** for typography, links, and tables:

```css
/* Good — prose only */
.article-content h1 { … }
.article-content a:link { … }
.article-content table { … }

/* Risky on PenCMS when body is .traven-preview */
.traven-preview h1 { … }
.traven-preview a { … }
.traven-preview table { … }
```

Reference: `themes/freedomware` (`styles.css` grid shell + chrome resets; `skin-freedomware.css` scoped tables). Sticky notes: [`knowledgebase.md`](dev/knowledgebase.md) **A10–A13**.

---

## 8. Shortcode styling guide

**Inventory of classes and attributes:** [`traven-shortcodes.md`](traven-shortcodes.md).  
**Dual-scope selectors and float rules:** [`traven-theme-development.md`](dev/traven-theme-development.md) §3 and §6.

### Canonical layout attributes

| Attribute | Values |
|---|---|
| `align` | `left` \| `right` \| `center` \| `fullbleed` |
| `size` | `small` \| `medium` \| `large` \| `full` |

- Theme-only extras (`xsmall`, `xlarge`) are **non-canonical** — optional extensions; never required for compliance.
- Fullbleed is an **alignment**, not a size. `size="full"` is column-width 100%; `align="fullbleed"` is a stronger breakout whose exact look is **theme-defined** (viewport wall-to-wall, wider stage, etc. — PenCMS does not prescribe one). See **Fullbleed on published pages** below.
- Emitted as classes: `.align-{value}`, `.size-{value}`, and (PenCMS PHP only) `.img--{value}` duplicate on the same node.

**Published size scale (PenCMS `.gallery-single` / `.figure-full`)** — use **percentages of the article column**, not mixed fixed pixels + percentages. Keeper themes (`starter`, `editorial`, `academic`, `colorful`, `dark`, `modern`) share this scale:

| `size` | Width | Notes |
|---|---|---|
| `xsmall` (optional) | 20% | Theme extension only |
| `small` | 30% | Must be visibly smaller than `medium` |
| `medium` | 50% | Default when `size` omitted in `[image]` |
| `large` | 70% | Must stay narrower than `full` / fullbleed |
| `full` / `xlarge` | 100% | Column width — not viewport breakout |

**Why percentages:** A fixed `small` (e.g. 280px) plus `medium` at 50% collides on typical reading columns (~560px wide → 50% = 280px). Small images then look identical to medium regardless of alignment — a failure mode fixed across all keeper themes in 2026.

Traven editor preview widgets may still use fixed pixel widths on `.cm-wysiwym-image-shortcode-container` for WYSIWYM chrome; **published** `.gallery-single` rules belong in `styles.css` (and overlay `skin-starter.css` copies when used).

### PenCMS `[image]` / `.gallery-single` (published HTML)

PenCMS PHP (`ShortcodeProcessor`) emits **gallery wrappers**, not Traven `figure.traven-image-figure` nodes. Style this path in **`styles.css`** (and mirror generic `.size-*` / align utilities in the content skin for editor parity).

#### Emitted markup

```html
<div class="gallery-single align-center inline-image-center img--medium size-medium">
  <div class="photo-wrapper">
    <img src="…" alt="…">
  </div>
  <span class="caption">Optional caption</span>
</div>
```

| Piece | Detail |
|---|---|
| Outer block | `.gallery-single` (always) |
| Size classes | **Both** `.img--{size}` and `.size-{size}` on the **outer** div |
| Align classes | Only when `align="…"` is set: `.align-{align}` **and** `.inline-image-{align}` |
| Inner frame | `.photo-wrapper` → `img` (img is always `width: 100%` of the wrapper) |
| Caption | `span.caption` (not `figcaption`) |

`[figure]` uses `.figure-full` with the same size/align class pattern when attrs are present.

#### Required CSS blocks (`styles.css`)

Every new theme must ship **all** of the following in `assets/css/styles.css` (copy from `starter` as the baseline):

1. **Container** — `.gallery-single`, `.figure-full`: flex column, vertical margin, `clear: both`.
2. **Default centering** — center the outer block unless floated left/right (see pitfall below).
3. **`.photo-wrapper`** — overflow, border/frame per theme personality; `img { width: 100%; height: auto; }`.
4. **Classic markdown** — `img.classic-markdown`, `.classic-markdown-figure`, nested margin reset.
5. **Sizes** — percentage widths on `.gallery-single.img--*`, `.gallery-single.size-*`, `.figure-full…`, plus bare `.img--*` / `.size-*` fallbacks.
6. **Align** — `.align-left` / `.inline-image-left`, `.align-right` / `.inline-image-right`, `.align-center` / `.inline-image-center` (float + auto margins).
7. **Mobile** — `@media (max-width: 640px)`: sizes → `width: 100%`, floats cleared.

Do **not** put fullbleed breakout rules in this block if your theme already has a dedicated fullbleed section — keep fullbleed styling separate and tested (§8 *Fullbleed on published pages*).

#### Centering pitfall — `align` is optional

`align="center"` is **not** added unless the author sets `align` on the shortcode. A “centered small” image may be emitted as:

```html
<div class="gallery-single img--small size-small">…</div>
```

with **no** `.align-center`. Relying only on `.align-center { margin: auto }` leaves small images left-flush.

**Required pattern** — default-center non-floated gallery blocks:

```css
.gallery-single.inline-image-center,
.gallery-single.align-center,
.gallery-single:not(.align-left):not(.align-right):not(.inline-image-left):not(.inline-image-right):not(.align-fullbleed) {
  float: none;
  margin-left: auto;
  margin-right: auto;
}
```

Also include `.inline-image-center` alongside `.align-center` in align utility rules.

#### Size pitfall — scope the outer block, not the `img`

Width constraints must apply to **`.gallery-single` / `.figure-full`**, not only to `img` or `.photo-wrapper`. The inner `img` should fill the wrapper (`width: 100%`). If the outer block stays `width: 100%` of the column, every size looks like `full`.

Use scoped selectors for specificity over stale skin utilities:

```css
.gallery-single.img--small, .gallery-single.size-small,
.figure-full.img--small, .figure-full.size-small {
  width: 30%;
  max-width: 100%;
}
```

#### Overlay themes (`editor_skin_base`)

Themes that load `skin-starter.css` then `skin-editorial.css` (or similar) ship a **theme-local copy** of `skin-starter.css`. That copy must stay in sync with published rules:

- Generic `.size-small` / `.size-medium` / `.size-large` → percentages (not legacy `180px` / `340px` / `620px`).
- `.traven-preview` gallery centering rules for `.gallery-single` (same default-center pattern).
- Personality overlay (`skin-editorial.css`) may restyle `.photo-wrapper` (borders, tilt) but **must not drop** size widths — re-declare `.gallery-single.img--*` sizes in the overlay if personality rules share the same section.

#### Classic markdown captioned figures

```html
<figure class="classic-markdown-figure">
  <img class="classic-markdown" src="…" alt="…">
  <figcaption class="caption">…</figcaption>
</figure>
```

Match shortcode caption typography on `.classic-markdown-figure .caption` / `figcaption.caption`. Put vertical margin on `.classic-markdown-figure`, not on the nested `img` (`.classic-markdown-figure img.classic-markdown { margin: 0 auto; }`).

#### QA — image size matrix (published)

On `demo-markdown` or equivalent fixture, confirm **on the published post page**:

- [ ] `size="small"` is visibly narrower than `size="medium"` at desktop width
- [ ] `size="large"` is wider than medium but narrower than `size="full"`
- [ ] Centered small **without** `align="center"` in source is horizontally centered
- [ ] Left/right floats still wrap text; centered and default blocks do not float
- [ ] At ≤640px, sized images go full column width

### Fullbleed on published pages

**PenCMS does not mandate one look for `align="fullbleed"`.** The engine only emits the class; how wide, how tall, and whether the image is cropped is entirely up to the theme designer. Wall-to-wall viewport breakout is one valid choice — not the required one.

Whatever you choose, verify it on the **published** post template (not only in the admin editor preview), and make sure `size="full"` and `align="fullbleed"` remain distinguishable *for your interpretation*.

#### `size="full"` vs `align="fullbleed"`

| | Meaning |
|---|---|
| `size="full"` | 100% of the **content / reading column** |
| `align="fullbleed"` | Stronger than column-full — theme-defined breakout (viewport, wider stage, main shell, …) |

#### Valid approaches (examples)

Themes in this repo already disagree on purpose — both are fine:

| Approach | Intent | Example |
|---|---|---|
| **Viewport wall-to-wall** | Image reaches the left and right edges of the browser. Often paired with a height cap / letterbox crop so square sources do not dominate the page. | `editorial` — `100vw` + `calc(50% - 50vw)`, optional `aspect-ratio` + `object-fit: cover` |
| **Wider-than-column stage** | Image breaks out past the reading column on both sides but stops short of the viewport edges (margins / shell remain). Source aspect ratio and full height are preserved — no crop. | `casper-lite`-style Ghost/Casper “wide” treatment — fuller than `size="full"`, not edge-to-edge |

Other themes may invent further variants (max-width stage, break out to `.main-container` only, etc.). Compliance cares that fullbleed is **intentional and consistent**, not that it matches editorial.

#### Classic viewport breakout (CSS only) — *if* you choose wall-to-wall

```css
.gallery-single.align-fullbleed,
.traven-preview figure.traven-image-figure.align-fullbleed {
  width: 100vw;
  max-width: 100vw;
  margin-left: calc(50% - 50vw);
  margin-right: calc(50% - 50vw);
  float: none;
  clear: both;
}
```

(`calc(-50vw + 50%)` is the same expression.)

**Hard prerequisite for this recipe only:** the element’s containing block (usually the article column) must be **horizontally centered in the viewport**. The `50%` term is half the **parent width**, not “distance to the viewport edge.” If the parent is off-center, the image overshoots one side, leaves a gutter on the other, and often creates horizontal overflow that makes the whole page look pulled left.

If you are *not* doing wall-to-wall (e.g. casper-lite-style stage width), skip `100vw` entirely and size the breakout with a theme max-width / negative margins relative to your shell instead.

#### Wider-than-column stage recipe (casper-lite) — *if* you skip wall-to-wall

Use this when the post template has an **asymmetric** reading column (e.g. `lg:grid-cols-3` with content `lg:col-span-2` + sidebar `lg:col-span-1`). Negative margins relative to the column are enough to look “wider than full”; they do not need `100vw`.

```css
/* Break out past the reading column; stay clear of the sidebar gutter */
.traven-preview .align-fullbleed {
  width: calc(100% + 2rem) !important;
  max-width: none !important;
  margin-left: -1rem !important;
  margin-right: -1rem !important;
  border-radius: 0 !important;
  float: none !important;
  clear: both !important;
}

@media (min-width: 640px) {
  .traven-preview .align-fullbleed {
    width: calc(100% + 4rem) !important;
    margin-left: -2rem !important;
    margin-right: -2rem !important;
  }
}

@media (min-width: 1024px) {
  /* Match your grid gap (e.g. gap-12 = 3rem) so the right edge stays in the gutter */
  .traven-preview .align-fullbleed {
    width: calc(100% + 3rem) !important;
    margin-left: -1.5rem !important;
    margin-right: -1.5rem !important;
  }
}
```

Reference: [`frontend-php/src/blog/themes/casper-lite/assets/css/skin-casper-lite.css`](../../frontend-php/src/blog/themes/casper-lite/assets/css/skin-casper-lite.css). Optional chrome safety: `overflow-x: clip` on `.site-main` (see casper-lite `styles.css`).

Applies to **images, video, and audio** that share `.align-fullbleed` — keep one recipe for all media so fullbleed looks consistent.

#### Pitfall: asymmetric sidebar grids (editorial + casper-lite lesson)

This failed on `editorial` above `1024px` when the post grid was `2.5fr 6fr 3.5fr` (narrow left nav, wider right sidebar). The article column was no longer centered, so the skin’s `.traven-preview .align-fullbleed` **viewport** breakout looked flush-left with a right gutter. Below that breakpoint (single column) it looked fine — same CSS, different geometry.

The same math failed on `casper-lite` posts (`lg:grid-cols-3`, content 2/3 + sidebar 1/3): fullbleed video pinned to the left viewport edge and underlapped the sidebar. Fix: drop `100vw` and use the **stage recipe** above (or center the column if you insist on viewport wall-to-wall).

**Fix when you use the viewport recipe (CSS only — do not reach for JS):**

1. Make the article column centered when you enable viewport breakout (e.g. post grid `3fr 6fr 3fr`), **or**
2. Scope breakout to layouts where the column *is* centered, and keep a safer fullbleed elsewhere, **or**
3. Choose a non-viewport interpretation of fullbleed and skip `100vw` entirely (preferred for sidebar layouts — see casper-lite).

Reference chrome: [`frontend-php/src/blog/themes/editorial/assets/css/styles.css`](../../frontend-php/src/blog/themes/editorial/assets/css/styles.css) (`.layout-grid-post` + scoped `.gallery-single.align-fullbleed` rules).

#### Pitfall: skin preview rules also hit the published site

Complete themes put `traven-preview` on the post/page body wrapper (and often on `<body>`). That is correct for dual-duty typography, but it means **Layer B** rules like `.traven-preview .align-fullbleed { width: 100vw; … }` run on the live site inside **Layer A** chrome (sidebars, grids, paddings).

- Override or scope those rules in `styles.css` (chrome) for public layouts that are not a centered preview pane.
- If `<body class="traven-preview">`, do **not** let `.traven-preview { padding: … }` pad the whole page — that shifts the “centered” column and breaks viewport-breakout math. Editorial zeros body padding: `body.traven-preview { padding: 0 !important; }`.

#### Pitfall: `100vw` and horizontal scroll

`100vw` includes the scrollbar gutter on some engines. A viewport breakout can create a few pixels of overflow; `html { overflow-x: clip; }` is a cheap safety net so chrome that uses `margin: 0 auto` does not look shifted. Irrelevant if your fullbleed never uses `100vw`.

#### Pitfall: `overflow-x: hidden` on the article shell clips viewport fullbleed

If `.main-container` (or any ancestor of `.article-content`) sets `overflow-x: hidden`, elements that use `100vw` + `calc(50% - 50vw)` **break out in layout but get cropped** — images peek past the column then truncate on the sides; video pins to the left edge with the right side cut off.

**Fix:**

- `overflow-x: visible` on the main column wrapper (see `themes/freedomware` `.main-container`).
- `html { overflow-x: clip; }` as a safety net against scrollbar jitter (does not clip descendants the same way `overflow-x: hidden` on an ancestor does).

#### Pitfall: padding-only breakout (`calc(100% + 16ch)`, negative padding margins)

Extending fullbleed only by the theme’s horizontal **padding** (e.g. `width: calc(100% + 16ch); margin-left: -8ch` when the column uses `2ch` side padding) is **not** viewport fullbleed — it looks timid and still clips when a parent hides overflow. Use the `100vw` recipe (or the stage recipe) from above, and apply it to **all** fullbleed media in **`styles.css`**: `.gallery-single.align-fullbleed`, `figure.traven-image-figure.align-fullbleed`, `figure.traven-video-figure.align-fullbleed`, `figure.traven-audio-figure.align-fullbleed`, `.traven-video-container.align-fullbleed`, `.traven-audio-container.align-fullbleed`.

#### Pitfall: mobile media query resets fullbleed back to column width

A common mistake is a `@media (max-width: 640px)` block that sets `.align-fullbleed { width: 100%; margin-left: 0; margin-right: 0 }` for floated images — that **disables** viewport breakout on phones. Floats can go full column width at small breakpoints; **do not** zero out fullbleed viewport margins unless you intentionally abandon wall-to-wall on mobile.

#### Pitfall: `width: 100%` fullbleed rules on video/audio (skin-only)

Setting `.traven-video-figure.align-fullbleed { width: 100% }` in the skin without viewport margins does nothing beyond column-full. Published breakout belongs in **`styles.css`** (chrome) with the same selectors as gallery fullbleed.

#### Pitfall: 16:9 letterbox — crop vs stretch

| `object-fit` | Effect |
|---|---|
| **`cover`** | **Crop** — preserves aspect ratio; trims overflow (preferred for hero + fullbleed bands) |
| `contain` | Letterbox — full image visible, empty bands |
| `fill` | **Stretch / distort** — avoid unless intentional |

For hero and fullbleed images:

1. Put `aspect-ratio: 16 / 9` on the **crop box** (`.post-hero-image-wrapper`, `.photo-wrapper`, or the bare `img` when there is no wrapper).
2. Put `object-fit: cover; object-position: center` on the **`img`**.
3. Do **not** put `aspect-ratio` on a `figure` that also contains a `figcaption` — the caption gets squeezed into the 16:9 box. Crop the image node only; caption stays below.

```css
.post-hero-image-wrapper,
.gallery-single.align-fullbleed .photo-wrapper {
  aspect-ratio: 16 / 9;
  overflow: hidden;
}
.post-hero-image-wrapper img,
.gallery-single.align-fullbleed .photo-wrapper img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
}
```

For standalone `img.traven-image-shortcode.align-fullbleed`, apply `aspect-ratio` + `object-fit: cover` on the `img` with `height: auto`.

#### Pitfall: fullbleed video — do not use `padding-bottom` for 16:9 on the figure

Published `[video]` / `[youtube]` markup puts **align/size on the figure**, not on the inner player box:

```html
<figure class="traven-video-figure align-fullbleed size-full">
  <div class="traven-video-container"><!-- iframe or <video> --></div>
  <figcaption class="traven-video-caption">…</figcaption>
</figure>
```

Themes normally give `.traven-video-container` modern height via `aspect-ratio: 16 / 9` (with the iframe `position: absolute; inset: 0`).

**Do not** also put the old padding hack on a selector that matches the figure:

```css
/* WRONG — padding applies to figure.align-fullbleed → empty gap ≈ video height under the caption */
.traven-preview .traven-video-container.align-fullbleed,
.traven-preview figure.traven-video-figure.align-fullbleed {
  width: 100vw !important;
  margin-left: calc(-50vw + 50%) !important;
  margin-right: calc(-50vw + 50%) !important;
  padding-bottom: calc(100vw * 9 / 16) !important; /* doubles height */
}
```

Symptom: fullbleed width looks correct, but there is a huge white gap below the video (roughly one more 16:9 band). Cause: container height from `aspect-ratio` **plus** figure `padding-bottom`.

```css
/* RIGHT — break out width/margins on the figure; keep height on the container only */
.traven-preview figure.traven-video-figure.align-fullbleed {
  width: 100vw !important; /* or use the stage recipe if the column is off-center */
  max-width: 100vw !important;
  margin-left: calc(-50vw + 50%) !important;
  margin-right: calc(-50vw + 50%) !important;
  padding-bottom: 0 !important;
  height: auto !important;
}
.traven-preview .traven-video-container {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  overflow: hidden;
}
.traven-preview .traven-video-container iframe,
.traven-preview .traven-video-container video {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border: 0;
}
```

Same trap applies if you share one rule for `.traven-video-container.align-fullbleed` and `figure.traven-video-figure.align-fullbleed`: in real HTML only the figure has the class, so figure-only properties (especially `padding-bottom`) are the dangerous ones.

#### Pitfall: video iframe must fill the 16:9 container

YouTube/Vimeo iframes have a small intrinsic size when the shortcode omits `width`/`height` attributes. Giving `.traven-video-container` only `aspect-ratio: 16 / 9` + `background: #000` creates a correctly sized **black box**, but the player sits as a thumbnail at the top-center unless the iframe is absolutely stretched.

**Required baseline** (copy into every theme skin — vanilla or Tailwind chrome does not replace this):

```css
.traven-preview .traven-video-container {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  overflow: hidden;
  background-color: #000000;
}

.traven-preview .traven-video-container iframe,
.traven-preview .traven-video-container video {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: 0;
  display: block;
}
```

**Wrong** (looks fine until you embed YouTube):

```css
.traven-preview .traven-video-container {
  aspect-ratio: 16 / 9;
  width: 100%;
  background-color: #000;
}
.traven-preview .traven-video-container iframe {
  display: block;
  max-width: 100%; /* does NOT stretch height — iframe stays ~300×150 */
  margin: 0 auto;
}
```

Symptom: large black letterbox with a small YouTube chrome centered at the top, for every size (full, fullbleed, medium, large). Fixed in keeper skins `starter`, `academic`, and `casper-lite`; already correct in `editorial` / `modern` / `dark` / `colorful`.

Put these rules in `skin-{id}.css` (dual-duty). Tailwind themes still need this vanilla block in the skin — utility classes on Twig chrome do not style shortcode HTML emitted inside `.traven-preview`.

#### Markup to style

PenCMS PHP may emit gallery wrappers alongside Traven classes. Style **both** until unified:

- Traven: `figure.traven-image-figure.align-fullbleed`, `img.traven-image-shortcode.align-fullbleed`
- PenCMS gallery: `.gallery-single.align-fullbleed` (often with `.photo-wrapper` + `.caption`)

#### Height: crop or preserve — also a theme choice

Viewport-wide images at native aspect ratio can become very tall (e.g. square sources). Themes **may** crop; they are **not required** to.

- **Crop / letterbox** (editorial, freedomware): fixed `aspect-ratio: 16 / 9` on the **wrapper** + `object-fit: cover` on the **`img`** — crops without stretching. See §8 *Pitfall: 16:9 letterbox — crop vs stretch* above.
- **Preserve source** (casper-lite-style): `width` drives layout, `height: auto`, no `object-fit: cover` on fullbleed — the full photograph stays visible even if the block is tall.

```css
/* Optional editorial-style crop — not a contract requirement */
.gallery-single.align-fullbleed .photo-wrapper {
  aspect-ratio: 16 / 9;
  max-height: 500px; /* match .post-detail-hero-image if you have one */
}
.gallery-single.align-fullbleed .photo-wrapper img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
}
```

#### QA before calling fullbleed done

- [ ] Compare `size="full"` vs `align="fullbleed"` on the same asset — fullbleed must be visibly “more” than column-full for *your* design
- [ ] If using viewport `100vw` math: resize across the sidebar / multi-column breakpoint (often `1024px`) — left-flush + right gutter is the classic failure mode
- [ ] If the post template has an asymmetric sidebar: prefer the **stage** recipe (or prove the column is centered before using `100vw`)
- [ ] Confirm no unintended horizontal scrollbar; page chrome (header/footer) still looks centered
- [ ] Confirm editor preview still acceptable (skin rules) after any chrome overrides
- [ ] Height policy is deliberate: cropped letterbox **or** full source height — check square, portrait, and wide landscape sources either way
- [ ] Fullbleed **video**: no empty gap under the player/caption equal to another video height (no `padding-bottom: calc(100vw * 9 / 16)` on `figure.traven-video-figure.align-fullbleed`)
- [ ] **Video players fill their box** at every size/align: iframe/video is `position: absolute; width/height: 100%` inside a `position: relative` + `aspect-ratio: 16 / 9` container — no black letterbox with a tiny YouTube thumbnail

### What every complete theme must style

| Shortcode / surface | Preview targets (contract) | Notes |
|---|---|---|
| `[image]` | `img.traven-image-shortcode`, `figure.traven-image-figure`, `figcaption.traven-image-caption` | Full 4×4 align×size; **also** PenCMS PHP `.gallery-single` + `.photo-wrapper` + `span.caption` (§8) |
| Legacy `![alt](src)` | sensible default `img` | No layout attrs |
| `[video]` / `[youtube]` | `.traven-video-container`, `figure.traven-video-figure`, captions | Same align×size matrix; **required** absolute fill inside 16:9 container (§8 *Pitfall: video iframe*) |
| `[audio]` | `.traven-audio-container`, figure + caption | Same matrix |
| `[figure]` | `.traven-figure`, `.traven-figure-caption` | Pair tag; legacy PHP may emit `.figure-full` |
| Blockquote | `.traven-component-blockquote` (+ footer/cite / `.attribution`) | Distinct from pullquote |
| Pullquote | `.traven-component-pullquote` | Heavier / editorial |
| Native `blockquote` | `blockquote:not(.traven-component-pullquote)` | Still readable |
| `[info]` / `[warning]` | `.traven-component-info` / `-warning`, **plus** `.component-header` / `.component-title` | Collapsible uses `<details>` / `<summary class="component-header">`. Titles must be styled (weight / case). Gap under the title is `padding-bottom` on the header **when open**; zero it on `details:not([open])`. Editor: padding only, never vertical `margin` on `.cm-wysiwym-component-shortcode` ([`traven-theme-development.md`](dev/traven-theme-development.md) §4.4 / §6.5) |
| GitHub alerts | `.traven-alert`, `.traven-alert-{note,tip,important,warning,caution}` | Optional `::before` labels |
| `[highlight]` / `==mark==` | `mark` | Light + dark contrast |
| Generic `[component="…"]` | `.traven-component` + name modifier | Sensible default |
| `[expand]` / `[embed]` | `.traven-expand-*`, `.traven-embed*` | Load CSS/JS assets (§12); optional `--traven-expand-*` tokens (§12) |
| Mermaid / KaTeX | fences / `$` / `$$` | Footer auto-render hooks, not skin-only |

### Align × size matrix

Implement all 16 cells for **image**, **video**, and **audio**:

```text
         small   medium   large   full
left       ✓        ✓       ✓      ✓
right      ✓        ✓       ✓      ✓
center     ✓        ✓       ✓      ✓
fullbleed  ✓        ✓       ✓      ✓   (size still applied inside breakout where sensible)
```

Editor vs preview: do **not** float shortcode widgets in the editor; use auto-margins. Floats are fine under `.traven-preview`.

### Example shortcodes

```markdown
[image src="..." alt="..." align="center" size="medium" caption="Optional"]
[video src="https://www.youtube.com/watch?v=…" align="center" size="large"]
[audio src="..." align="center" size="large" caption="…"]
[pullquote]Editorial emphasis.[/pullquote]
[blockquote author="…" source="…"]Attributed quote.[/blockquote]
[info title="Note"]Helpful context.[/info]
> [!WARNING]
> Urgent attention needed.
```

---

## 9. Typography & embedded fonts

### Reader-facing (Layer A/B)

- **Prefer the core font registry** at `frontend-php/public/assets/fonts/`:
  - `fonts.json` — family key → label, CSS `family`/`stack`, license, face files (optional `weight_range` for variable fonts; `promoted_from` notes theme origins)
  - `fonts.css` — shared `@font-face` blocks (sibling-relative `url('./….woff2')`), kept in sync with `fonts.json`
  - woff2 files once (not per theme); TTF only when a family has no theme-local woff2 (e.g. M PLUS 1 Code)
  - Expanded beyond the original starter set by promoting unique families already vendored under `themes/*/assets/fonts/` (Sora, Oswald, Computer Modern, Newsreader, Plus Jakarta Sans, …). Cold-war private aliases (`Main Serif`) stay theme-local; OG TTF/OTF copies remain in themes for social-image rendering.
  - Style Settings font dropdowns merge this registry at runtime (API + ThemeEngine); themes need not duplicate the full list in `theme.json`.
- Link with `{{ publicAsset('fonts/fonts.css') }}` in `_head` **before** the skin. Static builds mirror the directory to `{dist}/assets/fonts/` so the same `publicAsset` URLs work offline. Admin editor loads `/assets/fonts/fonts.css` whenever a theme skin is active.
- Themes may still vendor **private/identity** webfonts under `assets/fonts/` with `@font-face` **in `skin-{id}.css`**. Declaring faces only in chrome `styles.css` or inside `<style type="text/tailwindcss">` breaks editor/preview font parity — see §6 warning.
- Copying a theme directory to another install requires core's font registry (same trade-off as Traven vendor assets under `public/assets/vendor/`).
- PenCMS default posture: **no Google Fonts `@import`** in shipping themes (privacy / offline / no telemetry). CDN fonts are non-compliant for production.

```css
/* Theme-local private face only — registry families use fonts.css */
@font-face {
  font-family: "Theme Body";
  src: url("../fonts/theme-body.woff2") format("woff2");
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}
```

Pair display vs body vs mono deliberately. Check dark-mode contrast for body text and muted labels.

### `supports.custom_fonts`

- `true` when the theme ships/loads custom webfonts for reading.
- Independent of OG fonts.

### OG / Pillow (Layer C)

- Pillow needs **TTF/OTF**, not woff2 alone.
- Map ids in `social_preview.og_fonts`; `og_font` selects one.
- **OG TTFs stay theme-local** under `assets/fonts/` (theme-relative paths). The shared woff2 registry does **not** replace Pillow fonts.
- Empty `og_fonts: {}` → platform CourierPrime engine font (`frontend-php/fonts/CourierPrime-Bold.ttf`). Document that fallback explicitly when you ship an empty map.

---

## 10. Theme-provided media

| Asset | Path | Purpose | Required? |
|---|---|---|---|
| Default hero | `assets/images/defaulthero.jpg` | OG + listing fallback when post has no hero | Yes if `supports.hero_image` |
| Watermark | `assets/images/watermark.png` | Full 1200×630 transparent OG overlay when layout is full-canvas; optional | Optional |
| Logo / brand | via `theme.getLogoUrl()` / shared assets | Header chrome | Site-config dependent |
| Sample content images | not theme-owned | Content media library | N/A |

**Specs**

- Hero: landscape suitable for 1200×630 crop / OG layout.
- Watermark: 1200×630 transparent PNG when using full-canvas layout. Corner layout may use a smaller PNG; optional `og_watermark_layout` / `og_watermark_corner` / `og_watermark_scale` on `social_preview`.
- Paths in `social_preview.og_default_hero` / `og_watermark` are theme-relative (e.g. `assets/images/defaulthero.jpg`).

---

## 11. Social / OG contract (`social_preview`)

Canonical field list, Twig globals, and operator overrides: [`dev/theme-social-preview.md`](dev/theme-social-preview.md). Operator UI: [`seo-settings.md`](seo-settings.md).

### Resolution order

1. Per-page frontmatter / content SEO  
2. Site Social overrides  
3. Theme `social_preview`  
4. Engine defaults  

### Ship a complete object

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

### Theme-author checklist (condensed)

- Colors: `og_accent_color`, `og_vignette_color`, `og_text_color`, `og_bar_color`
- `og_font` + `og_fonts` (TTF/OTF or empty map + engine fallback)
- Enums valid: `og_headline_style` ∈ redacted|shadow|plain|left|left_redacted|center|center_redacted|outline|banner|boxed|underline|caption|poster; `og_text_case` ∈ upper|title|as_is; `og_grade_preset` ∈ noir|clean|none|vibrant|warm|cool|fade|high_contrast|sepia|mono|dusk|night|paper
- `og_accent_bar` boolean; `twitter_card` set
- Default hero exists when `supports.hero_image`; `og_default_hero` / `og_watermark` paths valid or intentionally `null`
- `_head` / `_header` emit `og:*` / `twitter:*` using presentation globals (`twitter_card`, `og_*_fallback`, `og_default_image`)

Operators should only store sparse overrides in Settings → SEO → Social Previews.

---

## 12. Chrome & interaction

### Mandatory 3-Slot Menu Contract & Sturdy Dropdowns

> [!IMPORTANT]
> **Every PenCMS theme MUST support all 3 navigation slots:**
> 1. **Primary Menu (`menu('primary')`)**: Top header navbar, main sidebar, or primary site navigation bar. Must support 2-level nesting (Parent + Child dropdown/accordion) and `target_type: "label"` items.
> 2. **Secondary Menu (`menu('secondary')`)**: Sidebar navigation widget, secondary top/bottom navbar, or contextual site navigation. Must support 2-level nesting.
> 3. **Footer Menu (`menu('footer')`)**: Footer menu groups, multi-column links, or footer navigation bar. Must support 2-level nesting.
>
> **Theme Design Freedom:** Theme authors choose *where* and *how* to lay out each slot (e.g., top header, sidebars, footer columns). However, all 3 slots **must** be implemented in templates/partials so users can manage all 3 slots from `admin-settings-navigation.php`.

#### Sturdy Dropdown Architecture (No Flimsy Hovering)
When rendering dropdowns in primary/secondary navigation:
- **Zero Gap / Hover Bridge:** Never leave an empty margin gap between a parent link and its dropdown. Use transparent padding or an invisible `::before` pseudo-element bridge so hovering toward the menu never drops `:hover`.
- **JS Grace Delay:** Implement a 200ms `mouseleave` timeout in `theme.js` before dismissing `.open` / dropdown classes so swift or diagonal mouse cursor movements to sub-items feel solid and natural.
- **Click & Focus Locking:** Allow clicking parent items to toggle `.open` on mobile and desktop, and include `:focus-within` for keyboard accessibility (`Tab` / `Shift+Tab`).

### Class vocabulary (chrome)

**Layout & navigation**

- `.site-header`, `.header-container`, `.brand-wrapper`
- `.site-logo`, `.site-title`
- `.nav-menu`, `.nav-item`, `.has-children`, `.nav-trigger`, `.nav-dropdown`, `.nav-link`, `.nav-label`
- `.secondary-nav-widget`, `.secondary-nav-list`, `.secondary-nav-children`
- `.footer-menu`, `.footer-menu-group`, `.footer-menu-label`, `.footer-menu-children`, `.footer-menu-link`
- `.mobile-menu-toggle`, `.theme-toggle-btn`
- `.hero-banner`, `.hero-title-text`, `.hero-tagline-text`
- `.main-container`, `.layout-grid`, `.sidebar-column`

**Article listing cards**

- `.post-card`, `.post-card-meta`, `.post-card-category`
- `.post-card-title`, `.post-card-deck`, `.post-card-link`

**Post details**

- `.post-detail-header`, `.post-detail-eyebrow`, `.post-detail-trumpet`
- `.post-detail-title`, `.post-detail-deck`
- `.post-detail-meta`, `.post-detail-byline`
- `.post-detail-hero-image`
- `.post-content-wrapper`, `.post-body`

**Sidebar widgets**

- `.sidebar-widget`, `.sidebar-title`, `.sidebar-list`, `.sidebar-list-item`, `.sidebar-list-link`
- `.profile-card`, `.profile-avatar`, `.profile-name`, `.profile-bio`, `.profile-link`
- `.sticky-widget`

### Footer responsibilities

- Scripts: `theme.js`, Mermaid, KaTeX auto-render as applicable (match `starter` / `editorial`).
- Expand-embed: load `publicAsset('vendor/traven/expand-embed.css')` (or equivalent) and `expand-embed-runtime.js` / `initExpandEmbed`. Details: [`editor-link-suggest-and-expand.md`](editor-link-suggest-and-expand.md).

#### Expand/embed panel styling (optional)

Vendor file `frontend-php/public/assets/vendor/traven/expand-embed.css` ships default reader styling for `[expand]` nutshells and `[embed]` blocks. **Do not fork** that file for routine theme tweaks — override CSS custom properties in `styles.css` or `skin-{id}.css` instead.

**Default:** The expanded panel (`.traven-expand-panel`) uses a **transparent** background so it inherits the article/canvas background where it opens. Border and callout arrow outline use neutral slate defaults.

**When to override:** Use an opaque `--traven-expand-bg` when the panel should read as a distinct card (e.g. on busy or patterned backgrounds). Most themes can rely on the transparent default.

Set tokens on `:root`, `.traven-preview`, or the post body wrapper (same scope as other content rules):

```css
.traven-preview {
  --traven-expand-bg: #ffffff;       /* panel fill (default: transparent) */
  --traven-expand-caret-fill: …;     /* optional: arrow inner; else --traven-expand-bg or --traven-bg */
  --traven-expand-border: #94a3b8;   /* panel border + arrow outline */
  --traven-expand-fg: inherit;       /* panel text */
  --traven-expand-link: #64748b;     /* editor WYSIWYM chip link color */
  --traven-expand-accent: #475569;   /* expand trigger hover / focus */
  --traven-expand-muted: #94a3b8;    /* expand trigger when expanded */
}
```

The callout arrow uses a two-layer CSS triangle. When the panel background is transparent (the default), the inner triangle falls back to `--traven-bg` so the bordered “nub” still reads correctly against the article canvas. Set `--traven-expand-bg` for an opaque card (inner follows it), or `--traven-expand-caret-fill` to target the arrow alone (e.g. non-uniform backgrounds). Contract selectors: `.traven-expand-trigger`, `.traven-expand-panel`, `.traven-expand-panel-arrow`, `.traven-embed*`.

### Accessibility / UX

- Skip-link if used; focus styles on nav; don’t break dark-mode toggle.

---

## 13. Category- and slug-aware theming

A theme can give each category its own look — listing **and** individual posts — via override templates:

```text
templates/
├── post.html.twig
├── post-winter.html.twig
├── archive.html.twig
└── archive-winter.html.twig
```

Filing is via frontmatter:

```yaml
---
title: "Surviving the First Frost"
category: winter
---
```

A post with `category: spring` and no `post-spring.html.twig` falls through to `post.html.twig`. Static pages use slug overrides: `page-{slug}.html.twig` → `page.html.twig`.

**Parity warning:** if `post-winter` exists, consider `archive-winter` (and vice versa). The validator warns on missing pairs.

Prefer CSS tokens / overlays (e.g. `body.theme-{category}`) over duplicating entire skins per category.

---

## 14. Validation & golden fixture

### CLI

```bash
php frontend-php/cli-tools/theme-validate.php {theme-id}
```

The validator checks structure **and** dual-duty / OG contract items:

| Check | Severity |
|---|---|
| Mandatory templates / partials (incl. `search`), valid `theme.json` | error |
| At least one `assets/css/skin-*.css` | error |
| `traven-preview` in `post` / `page` (+ `post-*` / `page-*` overrides) | error |
| Complete `social_preview` keys (+ enum/type sanity) | error |
| `editor_skin` declared | warning |
| `og_fonts` empty or missing/non-TTF·OTF paths (engine fallback note) | warning |
| `supports.hero_image` without `defaulthero.jpg` / `og_default_hero` | warning |
| Category `post-*` ↔ `archive-*` parity | warning |

Exit **1** only on errors; warnings still exit **0**. Scaffold emits dual-duty stubs (skin file, `traven-preview` wrappers, `editor_skin`, complete `social_preview`) matching this guide.

### Golden fixture

- Path: `pencms-data/content/sites/default/demo-markdown/index.md`
- Purpose: one published (or previewable) page exercising Markdown + all shortcodes.
- Includes: full image align × size matrix; representative video/audio/figure/expand coverage (S3).
- QA method: view under each keeper theme; no unstyled shortcode “blobs”; compare editor (dual-duty skin) vs published.

### Scoring

Use §15 (and the printable scratch checklist) scorecard. Target for keepers: pass all Required items; dual-duty Required for `starter` and `editorial`; `casper-lite` at least markup + skin + shortcodes Required after remediation.

---

## 15. Complete theme checklist

Canonical checklist lives in two places that must stay in sync:

1. This section of the public guide
2. Scratch / printable copy: `gitignore/theme-compliance-checklist.md`

Do not invent a third divergent list. When amending items, update both in the same session.

Use this to score keeper themes (`starter`, `editorial`, `casper-lite`) and any new theme before calling it production-ready.

**Legend:** `[R]` Required · `[D]` Required for dual-duty / editor parity · `[O]` Optional / recommended

**Layout contract (engine):** `align` = left|right|center|fullbleed · `size` = small|medium|large|full  
Theme-only extras (`xsmall`, `xlarge`) do **not** count toward Required shortcode coverage.

### Scorecard template

Copy a row per theme. Use `pass` / `fail` / `partial` / `n/a`.

| Theme | Structure | Markup | Skin | Shortcodes | Integrations | Fonts/Media | social_preview | Chrome | Dual-duty | Fixture QA | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| starter | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | OG kit filled (CourierPrime + defaulthero + watermark); dual-scope skin-starter |
| editorial | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | Self-hosted Goudy/Macondo/Victor Mono; overlay + resynced skin-starter; OG kit |
| casper-lite | pass | pass | pass | pass | pass | pass | pass | pass | partial | pass | Remediatiated: traven-preview + skin-casper-lite; editor_skin set; dual-duty not advertised |
| modern | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | S8.1: promoted vendor Teal & Slate skin; self-hosted Saira/Epunda/JetBrains; cold-war-og kit; dual-duty `[D]` |
| academic | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | S8.2: promoted vendor Classic LaTeX Booktabs skin; self-hosted CM Serif/Typewriter + Source Serif 4 + Courier Prime; cold-war-og kit; dual-duty `[D]` |
| colorful | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | S8.3: promoted vendor Vibrant & Colorful skin; self-hosted Atkinson Hyperlegible Next + Fira Code; rust/indigo OG; dual-duty `[D]` |
| dark | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | S8.4: promoted vendor Premium Dark Slate skin; self-hosted Atkinson Hyperlegible Next + Fira Code; dark-first chrome; slate/sky OG; dual-duty `[D]` |
| _{new}_ | | | | | | | | | | | |

**Roll-up rule:** A theme is **complete** when all `[R]` items pass and, if advertised as dual-duty / active-theme editor skin, all `[D]` items pass.

### 15.1 Structure `[R]`

- [ ] `theme.json` exists and parses as JSON
- [ ] `theme.json` has `name`, `type: "native"`, `supports`, `variables`
- [ ] `templates/index.html.twig` exists
- [ ] `templates/post.html.twig` exists
- [ ] `templates/page.html.twig` exists
- [ ] `templates/search.html.twig` exists (static publish → `search/index.html`)
- [ ] `partials/_head.html.twig`, `_header.html.twig`, `_footer.html.twig` exist
- [ ] Primary menu partial (`_navbar.html.twig` or header nav) supports `menu('primary')` with 2-level nesting (Parent + Child) and sturdy gapless dropdown / JS grace delay
- [ ] Secondary menu partial (`_sidebar-secondary.html.twig` or secondary nav) supports `menu('secondary')` with 2-level nesting
- [ ] Footer menu partial (`_footer.html.twig`) supports `menu('footer')` with 2-level nesting
- [ ] `assets/css/styles.css` (or documented chrome stylesheet) exists
- [ ] `assets/css/skin-{id}.css` exists (content skin). Overlay themes may ship base + overlay (e.g. `skin-starter.css` + `skin-editorial.css`) but **at least one** content skin file must load on posts/pages
- [ ] `php frontend-php/cli-tools/theme-validate.php {id}` exits 0 (includes skin / `traven-preview` / `social_preview` checks; warnings allowed)

### 15.2 Markup contract `[R]`

- [ ] Every **post** body wrapper includes both classes: `article-content` and `traven-preview`
- [ ] Every **page** body wrapper includes both classes: `article-content` and `traven-preview`
- [ ] Category/slug override templates (`post-{category}`, `page-{slug}`, …) also use the dual class if they render body HTML
- [ ] No post/page relies on `.article-content` alone for shortcode styling

### 15.3 Content skin — dual scope `[R]` / `[D]`

**Published preview scope `[R]`**

- [ ] `.traven-preview` sets base font, color, background, line-height
- [ ] Headings `h1`–`h6` styled under `.traven-preview`
- [ ] Links, lists, code, pre, tables, `hr`, `mark` styled
- [ ] Dark mode (optional, only if theme includes user-requested dark variant): `.traven-preview.cm-wysiwym-dark` (or equivalent host class) recolors content `[O]`

**Editor scope `[D]` (required for dual-duty)**

- [ ] `.cm-editor` base font/color/background aligned with preview personality
- [ ] `:root` defines `--traven-font-display`, `--traven-font-body`, and `--traven-font-mono` `[D]`
- [ ] Base `.cm-editor` / `.traven-preview` stacks use `font-family` (and typically color/bg) with `!important` so admin Tailwind / `traven.css` do not win `[D]`
- [ ] `.post-detail-trumpet` / `.post-detail-title` / `.post-detail-deck` styled once in the skin for admin + publish (verify in `admin-editor.php`, not only on published post); do not duplicate type in `styles.css` `[D]`
- [ ] If published `.post-detail-title` is hollow (`color: transparent` + stroke / `background-clip: text`), override only `.hero-title-block.traven-preview .post-detail-title` to a solid fill + `caret-color` so the native `hero_title` textarea stays editable `[D]`
- [ ] Editor widget classes for shortcodes styled (`.cm-wysiwym-image-shortcode-container`, `.cm-wysiwym-component-shortcode`, etc.)
- [ ] No float / vertical margin on editor shortcode containers; align via auto-margins
- [ ] Dark mode rules for editor scope (optional, only if theme includes user-requested dark variant) `[O]`
- [ ] Skin remains usable **without** loading `styles.css` (chrome)
- [ ] Framework / Tailwind isolation `[D]` when chrome uses Preflight or similar: body `color` / `font-weight` and captions match between `.cm-editor` and `.traven-preview` (see §6 warning)
- [ ] Custom reader `@font-face` rules live in `skin-{id}.css` (not only in chrome / Tailwind-inlined CSS) so the admin editor resolves the same family as published HTML `[D]`

### 15.4 Shortcodes `[R]`

#### Images

- [ ] `[image]` / `figure.traven-image-figure` / `img.traven-image-shortcode` styled
- [ ] PenCMS PHP path: `.gallery-single`, `.photo-wrapper`, `span.caption` styled in `styles.css` `[R]`
- [ ] Captions: `figcaption.traven-image-caption` styled
- [ ] All **four aligns** work: left, right, center, fullbleed
- [ ] All **four sizes** work: small, medium, large, full
- [ ] **Size scale uses column percentages** (30% / 50% / 70% / 100% for small/medium/large/full) — not mixed fixed `small` px + `%` medium `[R]`
- [ ] Size widths apply to **outer** `.gallery-single` / `.figure-full`, not only inner `img` `[R]`
- [ ] **Default centering** for `.gallery-single` without left/right align (do not require `.align-center` class) `[R]`
- [ ] `.inline-image-center` included wherever `.align-center` is defined `[R]`
- [ ] Overlay themes: theme-local `skin-starter.css` (or base skin) `.size-*` utilities match published percentages `[R]` when `editor_skin_base` is set
- [ ] Fullbleed uses a deliberate breakout past `size="full"` (viewport, wider stage, or other documented design) — not an accidental duplicate of column-full
- [ ] Fullbleed look is intentional for **this** theme (PenCMS does not require wall-to-wall or cropping; `editorial` and `casper-lite`-style stage+full-height are both valid — see §8 Fullbleed)
- [ ] If using the classic `100vw` / `calc(50% - 50vw)` breakout: article column is **centered** at every layout where breakout is enabled (asymmetric sidebar grids will flush-left + right-gutter — see §8 Fullbleed)
- [ ] Fullbleed verified on the **published** post template across the sidebar / multi-column breakpoint (not only in the admin editor)
- [ ] No horizontal scrollbar / page-chrome shift from fullbleed; `body.traven-preview` does not inherit content-skin horizontal padding
- [ ] PenCMS `.gallery-single.align-fullbleed` (if emitted) matches Traven figure/img fullbleed treatment
- [ ] Legacy `![alt](src)` remains readable (sensible default `img` rules)
- [ ] Standard Markdown captioned images (`figure.classic-markdown-figure`) style the caption (`.caption` / `figcaption.caption`) to match the font-size, font-weight, color, and placement of shortcode image captions.
- [ ] Reset margins on the nested image (`.classic-markdown-figure img.classic-markdown { margin: 0 auto; }`) and set vertical margins on the container `.classic-markdown-figure` to prevent excessive caption gap.

#### Video & audio

- [ ] `[video]` / `[youtube]`: container/figure + caption classes styled
- [ ] `[audio]`: container/figure + caption styled
- [ ] Align × size coverage for video (all 4 × 4, or document intentional subset with validator exemption — default expectation is full matrix)
- [ ] Align × size coverage for audio (same)
- [ ] Video iframe/video **fills** `.traven-video-container` (`position: relative` + `aspect-ratio: 16 / 9` on container; absolute `width/height: 100%` on iframe/video) — no black letterbox with a tiny player (see §8 *Pitfall: video iframe*)
- [ ] Fullbleed video: no double-height gap under the player — use `aspect-ratio` on `.traven-video-container`, **not** `padding-bottom: calc(100vw * 9 / 16)` on `figure.traven-video-figure.align-fullbleed` (see §8 Fullbleed pitfall)
- [ ] Fullbleed video on asymmetric post grids: stage breakout or centered-column viewport math — verified above the sidebar breakpoint

#### Figure

- [ ] `[figure]` → `.traven-figure` + `.traven-figure-caption` styled `[R]` (fixture includes figure; also style PenCMS legacy `.figure-full` / `.caption` until PHP matches Traven)

#### Quotes & components

- [ ] Blockquote shortcode → `.traven-component-blockquote` (+ footer/cite) styled distinctly from pullquote
- [ ] Pullquote → `.traven-component-pullquote` styled **heavier / distinct** from blockquote and from native `blockquote`
- [ ] Native Markdown `blockquote` still styled (`blockquote:not(.traven-component-pullquote)` pattern)
- [ ] `[info]` → `.traven-component-info` styled
- [ ] `[warning]` → `.traven-component-warning` styled
- [ ] Info/warning **headers**: `.component-header` / `.component-title` are bold (and/or uppercase). Open state has padding under the title; `details:not([open])` does not. Editor widgets use padding, not vertical margin.
- [ ] Generic `[component="…"]` → `.traven-component` (+ name modifier) has a sensible default `[O]` strongly recommended

#### GitHub alerts

- [ ] `.traven-alert` base
- [ ] `.traven-alert-note` (and INFO alias behavior understood)
- [ ] `.traven-alert-tip`
- [ ] `.traven-alert-important`
- [ ] `.traven-alert-warning`
- [ ] `.traven-alert-caution` (and DANGER alias understood)

#### Highlight

- [ ] `mark` / highlight shortcode readable in base mode (and optional dark mode if built)

### 15.5 PenCMS integrations `[R]`

- [ ] Expand/embed: theme loads expand-embed CSS (e.g. `publicAsset('vendor/traven/expand-embed.css')` or equivalent)
- [ ] Expand/embed: runtime JS initialized (`initExpandEmbed` / documented equivalent)
- [ ] Expand/embed: optional `--traven-expand-*` tokens if nutshell panel needs opaque card styling `[O]` — default transparent; see [`pencms-theme-development.md`](pencms-theme-development.md) §12
- [ ] Mermaid: auto-render hook present if theme advertises diagram support (match starter/editorial footer pattern)
- [ ] KaTeX: auto-render hook present if math is supported in content
- [ ] Composite posts: multi-fragment titles/loop render correctly when `supports.composite`
- [ ] Reader-facing chrome uses `strings.*` for engine-defined labels instead of hardcoded English
- [ ] Listing/detail/archive links use `contentUrl()` / `archiveUrl()` rather than concatenating language prefixes or slug paths
- [ ] Templates retain real `<html>` and `<head>` elements so ThemeEngine can own document language and inject exact published hreflang links; themes do not emit draft/missing peers themselves
- [ ] Optional switcher, when included, uses `theme.partial('language-switcher')`; themes remain valid without switcher chrome `[O]`

### 15.6 Fonts & theme media `[R]` / `[O]`

- [ ] Reader fonts: self-hosted woff2 (or system stack with `supports.custom_fonts: false`) — **no Google Fonts `@import`** in production themes `[R]` for new themes; `[O]` migration for legacy keepers until S6
- [ ] Dual-duty: `@font-face` for reader families is declared in `skin-{id}.css` with `url('../fonts/…')` (editor loads the skin; chrome-only faces cause system-font fallback in WYSIWYM) `[D]` / `[R]` when `supports.custom_fonts: true`
- [ ] OG fonts: at least one TTF/OTF in `social_preview.og_fonts` **or** empty map with documented engine fallback `[R]`
- [ ] `assets/images/defaulthero.jpg` present when `supports.hero_image: true` `[R]`
- [ ] `og_default_hero` points at that asset (or null only if hero support false) `[R]`
- [ ] Watermark PNG 1200×630 optional `[O]`
- [ ] `og_watermark` null or valid theme-relative path `[R]` if key present


### 15.6b Style Settings `[R]` for new themes

- [ ] `theme.json` top-level `style` block with color + typography groups
- [ ] Chrome knobs on `:root` in both `styles.css` and `skin-{id}.css`; `--traven-*` aliased from them
- [ ] `_head` links `publicAsset('fonts/fonts.css')`
- [ ] Font selects short (Theme default + identity + optional system); registry-merged at runtime
- [ ] Dark-capable themes: `dark_scope` matches FOUC; `dark_default` on paired colors; chrome + skin share token flips
- [ ] Accent/panel-tied gradients use `var` / `color-mix` (not hardcoded rgba)
- [ ] Style Settings smoke (accent + bg; light and dark) passes before calling the theme complete

### 15.7 `social_preview` block `[R]`

Complete object present with valid values (see [`dev/theme-social-preview.md`](dev/theme-social-preview.md)):

- [ ] Colors: `og_accent_color`, `og_vignette_color`, `og_text_color`, `og_bar_color`
- [ ] `og_font` + `og_fonts`
- [ ] `og_headline_style` ∈ redacted|shadow|plain|left|left_redacted|center|center_redacted|outline|banner|boxed|underline|caption|poster
- [ ] `og_text_case` ∈ upper|title|as_is
- [ ] `og_grade_preset` ∈ noir|clean|none|vibrant|warm|cool|fade|high_contrast|sepia|mono|dusk|night|paper
- [ ] `og_accent_bar` boolean
- [ ] `og_watermark_enabled` boolean if present (optional)
- [ ] `og_watermark_source` / `og_watermark_layout` / `og_watermark_corner` / `og_watermark_scale` optional enums if present
- [ ] `og_default_hero` / `og_default_image` / fallbacks
- [ ] `twitter_card` (e.g. `summary_large_image`)

### 15.8 Chrome `[R]`

- [ ] Site header + branding render (`_header` / logo helpers)
- [ ] Navbar desktop + mobile toggle
- [ ] FOUC prevention script before stylesheets (only needed if dark mode variant built) `[O]`
- [ ] Theme / color-scheme toggle wired (optional, only if theme explicitly includes user-requested dark variant) `[O]`
- [ ] Footer closes document and loads theme JS
- [ ] Index/archive listing usable (post cards or equivalent)
- [ ] Sidebar partials only referenced if `supports.sidebars` and files exist

### 15.9 Dual-duty packaging `[D]`

- [ ] `theme.json` declares `editor_skin` (or agreed equivalent) matching skin id
- [ ] Skin file path is theme-owned: `assets/css/skin-{id}.css`
- [ ] Admin can load that skin for the active theme from theme assets only (no `vendor/traven/skins/` dependency)
- [ ] Default workspace `editorSkin` follows active theme skin (override still allowed; resets when site theme id changes)
- [ ] Chrome `styles.css` is not required for shortcode fidelity in the editor

### 15.10 Golden fixture QA `[R]`

Fixture: `pencms-data/content/sites/default/demo-markdown/index.md`  
**S3 landed:** full image align×size matrix (16 cells; diagonal captions); video/audio align/size spot-checks; one `[figure]`; one `[expand]` + one `[embed]`.

- [ ] Page opens under the theme without layout collapse
- [ ] Image align × size matrix cells are visually distinct (not all identical widths — especially **small vs medium**)
- [ ] Centered `size="small"` renders centered even when source omits `align="center"`
- [ ] Pullquote clearly heavier than blockquote
- [ ] Info/warning and GitHub alerts show distinct treatments
- [ ] Video + audio embeds sized/aligned sanely
- [ ] Figure + expand/embed render without unstyled blobs
- [ ] Dual-duty: editor with theme skin ≈ published post for the fixture body (chrome ignored)

### Keeper scorecard (post-S6)

| Theme | Likely fails today | Notes |
|---|---|---|
| starter | — | Checklist complete; OG kit + dual-duty skin |
| editorial | — | Checklist complete; self-hosted fonts; dual-duty overlay |
| casper-lite | Dual-duty full parity optional | Markup + skin + shortcodes Required pass; `editor_skin` declared |
| modern | — | S8.1 complete; dual-duty Teal & Slate; self-hosted fonts; OG kit |
| academic | — | S8.2 complete; dual-duty LaTeX Booktabs; self-hosted CM/Source Serif; OG kit |
| colorful | — | S8.3 complete; dual-duty Vibrant & Colorful; self-hosted Atkinson/Fira Code; OG kit |
| dark | — | S8.4 complete; dual-duty Premium Dark Slate; self-hosted Atkinson/Fira Code; dark-first chrome; OG kit |

Weak themes **archived** under `frontend-php/src/blog/themes/_deprecated/` (S7): `default`, `docs-public`, `org-1337`, `org-traven-docs`, `traven-docs`, `1337`. Shared OG kit salvaged to `themes/_asset-kits/cold-war-og/`. New themes from S8+: `modern` (S8.1), `academic` (S8.2), `colorful` (S8.3), `dark` (S8.4).

---

## 16. Appendix

### A. Align × size quick tables

Same 4×4 for image, video, and audio — see §8 and [`traven-shortcodes.md`](traven-shortcodes.md) §14.

|  | `small` | `medium` | `large` | `full` |
|---|---|---|---|---|
| `left` | ✓ | ✓ | ✓ | ✓ |
| `right` | ✓ | ✓ | ✓ | ✓ |
| `center` | ✓ | ✓ | ✓ | ✓ |
| `fullbleed` | ✓ | ✓ | ✓ | ✓ |

### B. Emitted class cheat sheet

Editor widget containers and preview classes: [`traven-shortcodes.md`](traven-shortcodes.md) §15 and [`traven-theme-development.md`](dev/traven-theme-development.md) §3. Do not maintain a third incomplete copy here.

### C. Related docs index

Same table as §1 — start there for role vs this guide.

### D. Migration notes

1. **Add `traven-preview`:** Put `class="article-content traven-preview"` on every post/page body wrapper (and overrides that render HTML). Chrome-only `.article-content` rules are not enough for shortcodes.
2. **Split chrome vs skin:** Move Traven shortcode / prose / alert rules into `assets/css/skin-{id}.css`. Keep listing cards and nav in chrome.
3. **Ship PenCMS gallery rules in `styles.css`:** Add the §8 *PenCMS `[image]` / `.gallery-single`* blocks (sizes as %, default centering, classic markdown, mobile). Do not assume Traven `img.traven-image-shortcode` rules cover `[image]` shortcodes.
4. **Sync overlay base skins:** If using `editor_skin_base: ["starter"]`, update the **theme-local** `skin-starter.css` copy (percent sizes + gallery centering), not only the canonical `starter` theme folder.
5. **Theme-owned skins only:** Treat `themes/{id}/assets/css/skin-*.css` as source of truth. Do not add skins under `public/assets/vendor/traven/skins/` (removed post-S8.5).
6. **Declare `editor_skin`:** Match the personality skin stem in `theme.json`.
7. **Complete `social_preview`:** Copy a filled block from §11 / `dev/theme-social-preview.md`; ship TTF or empty `og_fonts` + engine fallback; add `defaulthero` when heroes are supported.
8. **Ship video fill CSS:** Copy the §8 *Pitfall: video iframe* baseline into `skin-{id}.css` before shipping. Copy fullbleed from a peer theme that matches your layout (viewport/`editorial` only if the column is centered; stage/`casper-lite` for sidebar grids). Never put `padding-bottom: calc(100vw * 9 / 16)` on `figure.traven-video-figure`.

### E. Glossary

| Term | Meaning |
|---|---|
| Chrome | Site chrome — header, nav, cards, sidebars, FOUC (`styles.css` + Twig) |
| Skin | Content Layer B CSS (`skin-{id}.css`) for editor + published prose/shortcodes |
| Dual-duty | One theme-owned skin (or base+overlay) styles both admin editor and published HTML |
| Fullbleed | `align="fullbleed"` — theme-defined breakout past the reading column (**viewport** wall-to-wall *or* **stage** wider-than-column). **Not** the same as `size="full"`. Asymmetric sidebars cannot use naive `100vw` math — see §8 |
| Video fill | Required: `.traven-video-container` is `position: relative` + `aspect-ratio: 16 / 9`; iframe/video absolute `width/height: 100%`. Never `padding-bottom` 16:9 on the figure. See §8 |
| Size full | `size="full"` — 100% of the **content column** |
| Byline author | Frontmatter string `author:` for display credit |
| Profile author | Sidebar / profile object (`display_name`, bio, avatar) — see §5 collision note |
