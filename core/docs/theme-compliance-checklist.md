# PenCMS Theme Compliance Checklist

**Status:** Scratch / printable scorecard  
**Canonical home:** [`pencms-theme-development.md`](pencms-theme-development.md) §15 (keep in sync)  

Use this to score keeper themes (`starter`, `editorial`, `casper-lite`, `modern`, `academic`, `colorful`, `dark`) and any new themes before calling them production-ready.

**Legend:** `[R]` Required · `[D]` Required for dual-duty / editor parity · `[O]` Optional / recommended

**Layout contract (engine):** `align` = left|right|center|fullbleed · `size` = small|medium|large|full  
Theme-only extras (`xsmall`, `xlarge`) do **not** count toward Required shortcode coverage.

---

## Scorecard template

Copy a row per theme. Use `pass` / `fail` / `partial` / `n/a`.

| Theme | Structure | Markup | Skin | Shortcodes | Integrations | Fonts/Media | social_preview | Chrome | Dual-duty | Fixture QA | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| starter | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | OG kit filled; 3-slot nested menus; sturdy dropdowns |
| editorial | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | 3-slot nested menus; sturdy dropdown remediation |
| casper-lite | pass | pass | pass | pass | pass | pass | pass | pass | partial | pass | 3-slot nested menus; sturdy dropdowns |
| modern | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | Teal & Slate skin; 3-slot nested menus |
| academic | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | Classic LaTeX Booktabs skin; 3-slot nested menus |
| colorful | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | Vibrant skin; 3-slot nested menus |
| dark | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | Premium Dark Slate skin; 3-slot nested menus |
| beton | pass | pass | pass | pass | pass | pass | pass | pass | pass | pass | Light-only brutalist long-form; Archivo + IBM Plex Mono; fiche index + offset slab; dual-duty skin-beton.css |
| _{new}_ | | | | | | | | | | | |

**Roll-up rule:** A theme is **complete** when all `[R]` items pass and, if advertised as dual-duty / active-theme editor skin, all `[D]` items pass.

---

## 1. Structure `[R]`

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

---

## 2. Markup contract `[R]`

- [ ] Every **post** body wrapper includes both classes: `article-content` and `traven-preview`
- [ ] Every **page** body wrapper includes both classes: `article-content` and `traven-preview`
- [ ] Category/slug override templates (`post-{category}`, `page-{slug}`, …) also use the dual class if they render body HTML
- [ ] No post/page relies on `.article-content` alone for shortcode styling

### 2b. Published chrome (when `<body>` is `traven-preview`) `[R]` / `[O]`

Skip if the theme never puts `traven-preview` on `<body>` (unusual for PenCMS dual-duty themes).

- [ ] Prose link / heading / table rules scoped to `.article-content` **or** chrome headings/nav explicitly reset (sitename, post title, footer tables) `[O]` strongly recommended — see [`pencms-theme-development.md`](pencms-theme-development.md) §7 *Published chrome gotchas*
- [ ] Post/page chrome title (`.post-detail-title`, `.page-heading`) not picking up `.traven-preview h1` margins from the skin `[O]`
- [ ] `sub` / `sup` readable after CSS reset (explicit rules in `styles.css`) `[O]`
- [ ] `.site-header`, `.main-container`, `.site-footer` share one column width (grid track or equivalent — not independent flex-shrink siblings) `[O]`
- [ ] Chrome dark-mode hover / invert controls use explicit theme tokens, not `currentColor` + a non-inverting `--*-bg` `[O]` when dark mode is supported

---

## 3. Content skin — dual scope `[R]` / `[D]`

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
- [ ] Framework / Tailwind isolation `[D]` when chrome uses Preflight or similar: body `color` / `font-weight` and captions match between `.cm-editor` and `.traven-preview` (see [`pencms-theme-development.md`](pencms-theme-development.md) §6 warning)
- [ ] Custom reader `@font-face` rules live in `skin-{id}.css` (not only in chrome / Tailwind-inlined CSS) so the admin editor resolves the same family as published HTML `[D]`


---

## 4. Shortcodes `[R]`

### 4.1 Images

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
- [ ] Fullbleed look is intentional for **this** theme (PenCMS does not require wall-to-wall or cropping; `editorial` and `casper-lite`-style stage+full-height are both valid — see [`pencms-theme-development.md`](pencms-theme-development.md) §8)
- [ ] If using the classic `100vw` / `calc(50% - 50vw)` breakout: article column is **centered** at every layout where breakout is enabled (asymmetric sidebar grids will flush-left + right-gutter — see [`pencms-theme-development.md`](pencms-theme-development.md) §8)
- [ ] If the post template has an asymmetric sidebar: prefer stage breakout over `100vw`, or document why the column is centered
- [ ] Fullbleed verified on the **published** post template across the sidebar / multi-column breakpoint (not only in the admin editor)
- [ ] Article shell does **not** use `overflow-x: hidden` on `.main-container` (or any fullbleed ancestor) when viewport `100vw` breakout is enabled — use `html { overflow-x: clip }` instead (see [`pencms-theme-development.md`](pencms-theme-development.md) §8)
- [ ] Fullbleed breakout in **`styles.css`** covers gallery **and** Traven video/audio figures/containers (not `width: 100%` skin-only rules)
- [ ] Mobile `@media` rules do **not** reset `.align-fullbleed` to `margin-left: 0; width: 100%` unless wall-to-wall is intentionally disabled on small screens
- [ ] If using 16:9 hero/fullbleed crop: `aspect-ratio` on wrapper (or bare `img`), `object-fit: cover` on `img` — not `object-fit: fill` (see §8 *16:9 letterbox*)
- [ ] No horizontal scrollbar / page-chrome shift from fullbleed; `body.traven-preview` does not inherit content-skin horizontal padding
- [ ] PenCMS `.gallery-single.align-fullbleed` (if emitted) matches Traven figure/img fullbleed treatment
- [ ] Legacy `![alt](src)` remains readable (sensible default `img` rules)
- [ ] Standard Markdown captioned images (`figure.classic-markdown-figure`) style the caption (`.caption` / `figcaption.caption`) to match the font-size, font-weight, color, and placement of shortcode image captions.
- [ ] Reset margins on the nested image (`.classic-markdown-figure img.classic-markdown { margin: 0 auto; }`) and set vertical margins on the container `.classic-markdown-figure` to prevent excessive caption gap.

### 4.2 Video & audio

- [ ] `[video]` / `[youtube]`: container/figure + caption classes styled
- [ ] `[audio]`: container/figure + caption styled
- [ ] Align × size coverage for video (all 4 × 4, or document intentional subset with validator exemption — default expectation is full matrix)
- [ ] Align × size coverage for audio (same)
- [ ] Video iframe/video **fills** `.traven-video-container`: container is `position: relative` + `aspect-ratio: 16 / 9`; iframe/video is `position: absolute; width/height: 100%` — no black letterbox with a tiny YouTube thumbnail (see [`pencms-theme-development.md`](pencms-theme-development.md) §8 — *Pitfall: video iframe*)
- [ ] Fullbleed video: no empty gap ≈ video height under the caption — height from `aspect-ratio` on `.traven-video-container` only; do **not** put `padding-bottom: calc(100vw * 9 / 16)` on `figure.traven-video-figure.align-fullbleed` (see [`pencms-theme-development.md`](pencms-theme-development.md) §8 — *Pitfall: fullbleed video*)
- [ ] Fullbleed on asymmetric post grids (sidebar layouts): use stage breakout **or** prove the column is centered before using `100vw` — verify above the sidebar breakpoint (see [`pencms-theme-development.md`](pencms-theme-development.md) §8 — *Wider-than-column stage* / *asymmetric sidebar grids*)

### 4.3 Figure

- [ ] `[figure]` → `.traven-figure` + `.traven-figure-caption` styled `[R]` (fixture includes figure; also style PenCMS legacy `.figure-full` / `.caption` until PHP matches Traven)

### 4.4 Quotes & components

- [ ] Blockquote shortcode → `.traven-component-blockquote` (+ footer/cite) styled distinctly from pullquote
- [ ] Pullquote → `.traven-component-pullquote` styled **heavier / distinct** from blockquote and from native `blockquote`
- [ ] Native Markdown `blockquote` still styled (`blockquote:not(.traven-component-pullquote)` pattern)
- [ ] `[info]` → `.traven-component-info` styled
- [ ] `[warning]` → `.traven-component-warning` styled
- [ ] Info/warning **headers**: `.component-header` / `.component-title` bold (and/or uppercase); padding under the title when open; none when `details:not([open])`; editor uses padding, not vertical margin ([`pencms-theme-development.md`](pencms-theme-development.md) §8)
- [ ] Generic `[component="…"]` → `.traven-component` (+ name modifier) has a sensible default `[O]` strongly recommended

### 4.5 GitHub alerts

- [ ] `.traven-alert` base
- [ ] `.traven-alert-note` (and INFO alias behavior understood)
- [ ] `.traven-alert-tip`
- [ ] `.traven-alert-important`
- [ ] `.traven-alert-warning`
- [ ] `.traven-alert-caution` (and DANGER alias understood)

### 4.6 Highlight

- [ ] `mark` / highlight shortcode readable in base mode (and optional dark mode if built)

---

## 5. PenCMS integrations `[R]`

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

---

## 6. Fonts & theme media `[R]` / `[O]`

- [ ] Reader fonts: self-hosted woff2 (or system stack with `supports.custom_fonts: false`) — **no Google Fonts `@import`** in production themes `[R]` for new themes; `[O]` migration for legacy keepers until S6
- [ ] Dual-duty fonts: `@font-face` for reader families is in the content skin (admin loads skin only) `[D]` / `[R]` when `supports.custom_fonts: true`
- [ ] OG fonts: at least one TTF/OTF in `social_preview.og_fonts` **or** empty map with documented engine fallback `[R]`
- [ ] `assets/images/defaulthero.jpg` present when `supports.hero_image: true` `[R]`
- [ ] `og_default_hero` points at that asset (or null only if hero support false) `[R]`
- [ ] Watermark PNG optional; 1200×630 when layout is full-canvas `[O]`
- [ ] `og_watermark` null or valid theme-relative path `[R]` if key present

---


## 6b. Style Settings `[R]` for new themes

Canonical detail: [`pencms-theme-development.md`](pencms-theme-development.md) §4.2 / `style` block.

- [ ] `theme.json` includes a top-level `style` block with color + typography groups `[R]`
- [ ] Chrome knobs (`--color-*` / `--font-*` or equivalent) are defined on `:root` in **both** `styles.css` and `skin-{id}.css` `[R]`
- [ ] `--traven-*` (and theme-private aliases) are **aliased from** those chrome knobs — not a second hardcoded palette `[R]`
- [ ] Every exposed `var` is actually consumed by chrome or skin `[R]`
- [ ] `_head` links `{{ publicAsset('fonts/fonts.css') }}` before theme CSS `[R]`
- [ ] Font `select` options are short (Theme default + identity + optional system); registry merge supplies the rest `[R]`
- [ ] If the theme has dark mode: `dark_scope.selector` matches FOUC exactly; paired colors have `dark_default`; chrome **and** skin flip the same tokens `[R]`
- [ ] Gradients / washes / flags that belong to accent or panel track tokens (`var` / `color-mix`) — no frozen rgba copies `[R]`
- [ ] Smoke: Admin → Theme → Style Settings — change accent + bg (light and dark if present); chrome + content update; dark does not inherit light-only changes `[R]`

## 7. `social_preview` block `[R]`

Complete object present with valid values (see `core/docs/dev/theme-social-preview.md`):

- [ ] Colors: `og_accent_color`, `og_vignette_color`, `og_text_color`, `og_bar_color`
- [ ] `og_font` + `og_fonts`
- [ ] `og_headline_style` ∈ redacted|shadow|plain|left|left_redacted|center|center_redacted|outline|banner|boxed|underline|caption|poster
- [ ] `og_text_case` ∈ upper|title|as_is
- [ ] `og_grade_preset` ∈ noir|clean|none|vibrant|warm|cool|fade|high_contrast|sepia|mono|dusk|night|paper
- [ ] `og_accent_bar` boolean
- [ ] `og_watermark_enabled` boolean if present (optional; engine default true)
- [ ] `og_watermark_source` / `og_watermark_layout` / `og_watermark_corner` / `og_watermark_scale` optional enums if present
- [ ] `og_default_hero` / `og_default_image` / fallbacks
- [ ] `twitter_card` (e.g. `summary_large_image`)

---

## 8. Chrome `[R]`

- [ ] Site header + branding render (`_header` / logo helpers)
- [ ] Primary menu desktop + mobile toggle with sturdy dropdowns (gapless hover bridge + JS grace delay)
- [ ] Secondary menu sidebar widget / nav rendered when `menu('secondary')` is non-empty
- [ ] Footer menu rendered when `menu('footer')` is non-empty
- [ ] FOUC prevention script before stylesheets (only needed if dark mode variant built) `[O]`
- [ ] Theme / color-scheme toggle wired (optional, only if theme explicitly includes user-requested dark variant) `[O]`
- [ ] Footer closes document and loads theme JS
- [ ] Index/archive listing usable (post cards or equivalent)
- [ ] Sidebar partials only referenced if `supports.sidebars` and files exist

---

## 9. Dual-duty packaging `[D]`

- [ ] `theme.json` declares `editor_skin` (or agreed equivalent) matching skin id
- [ ] Skin file path is theme-owned: `assets/css/skin-{id}.css`
- [ ] Admin can load that skin for the active theme from theme assets only (no `vendor/traven/skins/` dependency)
- [ ] Default workspace `editorSkin` follows active theme skin (override still allowed; resets when site theme id changes)
- [ ] Chrome `styles.css` is not required for shortcode fidelity in the editor

---

## 10. Golden fixture QA `[R]`

Fixtures: standard demo markdown posts.

- [ ] Page opens under the theme without layout collapse
- [ ] Image align × size matrix cells are visually distinct (not all identical widths — especially **small vs medium**)
- [ ] Centered `size="small"` renders centered even when source omits `align="center"`
- [ ] Primary, Secondary, and Footer menus render parent and child items without unstyled gaps or flimsy hover drops
- [ ] Dual-duty: editor with theme skin ≈ published post for the fixture body (chrome ignored)
