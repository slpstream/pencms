# Traven / PenCMS Shortcode Reference

Theme-author inventory of shortcodes: syntax, attributes, emitted HTML, and CSS classes for the editor (WYSIWYM) and published preview. Use this for **classes and attrs**; dual-scope styling rules, float restrictions, and the full selector bible live in [`traven-theme-development.md`](traven-theme-development.md) (§1, §3, §4.4, §6).

---

## 1. Purpose and dual pipeline

| Surface | Scope | Class prefix / wrapper |
|---|---|---|
| Admin editor (WYSIWYM) | Live CodeMirror widgets | `.cm-wysiwym-*` inside `.cm-editor` |
| Published / HTML preview | Reader HTML inside the content body | Prefer `.traven-preview …` (themes must put `class="article-content traven-preview"` on post/page bodies) |

One content skin should style **both** scopes so editor and published page stay near pixel-parity. Shared layout helpers (`align-*`, `size-*`) appear on both editor widgets and preview markup.

### PenCMS published HTML vs Traven preview contract

**Primary styling contract** (compliance checklist, dual-duty skins, editor modals) is the **Traven** markup and class names documented below.

PenCMS reader HTML is produced by [`ShortcodeProcessor.php`](../../frontend-php/src/core/ShortcodeProcessor.php) after Markdown conversion ([`PostRenderer.php`](../../frontend-php/src/core/PostRenderer.php)). Most shortcodes already match Traven; a few wrappers still diverge:

| Shortcode | Traven / checklist target | PenCMS PHP today |
|---|---|---|
| `[image]` | `img.traven-image-shortcode` / `figure.traven-image-figure` + `figcaption.traven-image-caption` | `div.gallery-single` + `.photo-wrapper` + `img--{size}` / `size-{size}` + optional `span.caption` |
| Pair `[figure]…[/figure]` | `figure.traven-figure` + `figcaption.traven-figure-caption` | Legacy path often emits `div.figure-full` (image-centric), not the block wrapper |
| GitHub alerts | Often `div.traven-alert.traven-alert-{type}` in Traven preview | `blockquote.traven-alert.traven-alert-{type}` |

Until PHP and Traven are unified, keepers may need rules for **both** class families on images. Required checklist items still target the Traven preview selectors.

---

## 2. Layout contract

Canonical values from the editor image/video/audio modals:

| Attribute | Allowed values |
|---|---|
| `align` | `left` \| `right` \| `center` \| `fullbleed` |
| `size` | `small` \| `medium` \| `large` \| `full` |

Emitted as classes: `.align-{value}`, `.size-{value}`.

| Concept | Meaning |
|---|---|
| `size="full"` | Width 100% of the **content column** |
| `align="fullbleed"` | Break out past the reading column. **Theme-defined** — PenCMS does not prescribe one look. Examples: viewport wall-to-wall (`100vw` + `calc(50% - 50vw)`, centered column required), or a wider-than-column stage that never reaches the viewport edges and keeps full source height (casper-lite-style). See [`pencms-theme-development.md`](pencms-theme-development.md) §8 |
| `xsmall` / `xlarge` | **Non-canonical theme extras** — optional; do not count toward Required shortcode coverage |

Typical skin widths (Traven docs; individual skins may differ slightly): `small` ~150px, `medium` ~300px, `large` ~600px, `full` 100%.

**Editor vs preview:** do **not** float shortcode widgets in the editor (breaks CodeMirror geometry). Use auto-margins for left/right/center in `.cm-editor`; floats are fine under `.traven-preview`. Details: [`traven-theme-development.md` §4.4](traven-theme-development.md#44-no-floats-or-vertical-margins-in-the-editor).

---

## 3. Inventory

| Shortcode / syntax | Kind |
|---|---|
| `[image …]` | Media (self-closing) |
| `![alt](src)` | Legacy Markdown image |
| `[video …]` / `[youtube …]` | Media |
| `[audio …]` | Media |
| `[figure …]…[/figure]` | Pair wrapper |
| `[blockquote]` / `[quote]` / `[component name="blockquote"]` | Quote |
| `[pullquote]` | Quote (distinct from blockquote) |
| `[info]` / `[warning]` | Notice |
| `[component="…"]` / `[component name="…"]` | Generic / named block |
| `[highlight]` / `==mark==` | Inline mark |
| `> [!NOTE]` (and TIP, IMPORTANT, WARNING, CAUTION) | GitHub alert |
| `[expand …]` / `[embed …]` | PenCMS transclusion |

---

## 4. `[image]`

### Syntax

```markdown
[image src="..." alt="..." align="center" size="medium" caption="Optional" class="my-class"]
```

Legacy (no layout attrs): `![alt](src)`.

When PenCMS PHP publishes classic Markdown images, caption-worthy alt text (non-empty and not literally `image`) becomes a visible caption:

```html
<figure class="classic-markdown-figure">
  <img class="classic-markdown" src="..." alt="…">
  <figcaption class="caption">…</figcaption>
</figure>
```

Themes should style `.classic-markdown-figure .caption` / `figcaption.caption` alongside existing shortcode caption selectors (`.gallery-single .caption`, `.figure-full .caption`). Empty alt or `![image](src)` stays a bare `<img class="classic-markdown">` with no figure.

### Attributes

| Attr | Required | Default | Notes |
|---|---|---|---|
| `src` | yes | — | Resolved via theme/asset paths in PenCMS |
| `alt` | no | `""` | |
| `align` | no | (none / theme default) | `left` \| `right` \| `center` \| `fullbleed` |
| `size` | no | `medium` (PenCMS) | `small` \| `medium` \| `large` \| `full` |
| `caption` | no | — | When set → figure + caption path |
| `class` | no | — | Extra classes on the outer wrapper |

### Emitted HTML — Traven / checklist (style these)

```html
<!-- No caption -->
<img class="traven-image-shortcode align-[alignment] size-[size] [custom]" src="..." alt="...">

<!-- With caption -->
<figure class="traven-image-figure align-[alignment] size-[size] [custom]">
  <img class="traven-image-shortcode" src="..." alt="...">
  <figcaption class="traven-image-caption">Caption</figcaption>
</figure>
```

### Emitted HTML — PenCMS PHP today

```html
<div class="gallery-single [class] align-[align] inline-image-[align] img--[size] size-[size]">
  <div class="photo-wrapper">
    <img src="..." alt="...">
  </div>
  <span class="caption">…</span><!-- if caption -->
</div>
```

### Classes

| Role | Selector |
|---|---|
| Editor widget | `.cm-wysiwym-image-shortcode-container` (+ `.align-*`, `.size-*`); meta: `.shortcode-meta`, `.meta-badge`; edit: `.image-edit-icon` |
| Legacy MD image widget | `.cm-wysiwym-image-widget-container` |
| Preview (contract) | `.traven-preview img.traven-image-shortcode`, `figure.traven-image-figure`, `figcaption.traven-image-caption` |
| Preview (PenCMS PHP) | `.gallery-single`, `.photo-wrapper`, `.caption`, `.img--*`, `.inline-image-*` |
| Classic MD (PenCMS PHP) | `figure.classic-markdown-figure`, `img.classic-markdown`, `figcaption.caption` (alt-as-caption) |

---

## 5. `[video]` / `[youtube]`

### Syntax

```markdown
[video src="https://www.youtube.com/watch?v=…" align="center" size="medium" caption="…" class="…"]
[youtube src="dQw4w9WgXcQ"]
```

`[youtube]` is an alias that forces YouTube embedding (`src` may be a full URL or raw video id). `[video]` also detects Vimeo URLs and direct files (`.mp4`, `.webm`, `.ogg` → `<video controls>`).

### Attributes

| Attr | Required | Default | Notes |
|---|---|---|---|
| `src` | yes | — | URL or YouTube id |
| `align` | no | `center` | Layout contract values |
| `size` | no | `medium` | Layout contract values |
| `caption` | no | — | Adds `figcaption` |
| `class` | no | — | Extra classes on outer figure |

### Emitted HTML

PenCMS always wraps in a figure (with or without caption):

```html
<figure class="traven-video-figure align-[a] size-[s] [custom]">
  <div class="traven-video-container">
    <!-- iframe (youtube-nocookie / vimeo) or -->
    <video src="..." controls class="traven-video-shortcode"></video>
  </div>
  <figcaption class="traven-video-caption">Caption</figcaption><!-- if caption -->
</figure>
```

Traven fallback may omit the outer `<figure>` when there is no caption (bare `.traven-video-container`). Style both for safety.

### Classes

| Role | Selector |
|---|---|
| Editor | `.cm-wysiwym-video-shortcode-container` (+ placeholder children: `.video-placeholder`, `.video-placeholder-icon-wrap`, `.video-placeholder-details`, `.video-placeholder-platform`, `.video-placeholder-url`; `.video-edit-icon`) |
| Preview | `.traven-video-container` (typically 16:9 `aspect-ratio`), `figure.traven-video-figure`, `figcaption.traven-video-caption`, `video.traven-video-shortcode` |

---

## 6. `[audio]`

### Syntax

```markdown
[audio src="..." align="center" size="large" caption="…" class="…"]
```

### Attributes

| Attr | Required | Default | Notes |
|---|---|---|---|
| `src` | yes | — | e.g. `.mp3`, `.wav`, `.ogg` |
| `align` | no | `center` | |
| `size` | no | `large` (PenCMS) | Layout contract values |
| `caption` | no | — | |
| `class` | no | — | |

### Emitted HTML

```html
<figure class="traven-audio-figure align-[a] size-[s] [custom]">
  <div class="traven-audio-container">
    <audio class="traven-audio-shortcode" controls src="..."></audio>
  </div>
  <figcaption class="traven-audio-caption">Caption</figcaption><!-- if caption -->
</figure>
```

### Classes

| Role | Selector |
|---|---|
| Editor | `.cm-wysiwym-audio-shortcode-container` (+ same placeholder shape as video; `.audio-edit-icon`) |
| Preview | `.traven-audio-container`, `figure.traven-audio-figure`, `figcaption.traven-audio-caption`, `audio.traven-audio-shortcode` |

---

## 7. `[figure]…[/figure]`

### Syntax (Traven pair-tag)

```markdown
[figure align="center" size="medium" caption="My caption" class="custom-figure"]
… nested markdown / blocks …
[/figure]
```

### Attributes

| Attr | Required | Default | Notes |
|---|---|---|---|
| `align` | no | — | Layout contract |
| `size` | no | — | Layout contract |
| `caption` | no | — | Or body content as caption in some host paths |
| `class` | no | — | |

### Emitted HTML — Traven / checklist

```html
<figure class="traven-figure align-[a] size-[s] [custom]">
  <!-- nested block content -->
  <figcaption class="traven-figure-caption">Caption</figcaption>
</figure>
```

### PenCMS note

PHP’s `[figure …]` handler is still largely a **legacy image wrapper** (`div` + `.photo-wrapper`, default class `figure-full`, optional `width`). Prefer styling `.traven-figure` for dual-duty; treat `.figure-full` as legacy chrome if present.

### Classes

| Role | Selector |
|---|---|
| Editor | `.cm-wysiwym-figure-shortcode` (`.component-body`, `.figure-caption`, `.figure-edit-icon`) |
| Preview | `.traven-preview .traven-figure`, `.traven-figure-caption` |

---

## 8. Quotes — blockquote vs pullquote

**Style these as two different designs.** Pullquotes should read heavier / more editorial than attributed blockquotes. Also style native Markdown `blockquote` separately (exclude pullquotes), e.g. `.traven-preview blockquote:not(.traven-component-pullquote)`.

### Blockquote aliases

Author may write any of:

```markdown
[blockquote author="James Baldwin" source="The Fire Next Time"]
Not everything that is faced can be changed…
[/blockquote]

[quote author="…" source="…"]…[/quote]

[component name="blockquote" author="…" source="…"]…[/component]
[component="blockquote" author="…" source="…"]…[/component]
```

| Attr | Notes |
|---|---|
| `author` | Citation |
| `source` | Citation |
| `name` / positional | `blockquote` when using `[component]` |

### Pullquote

```markdown
[pullquote]
Editorial emphasis that stands apart from body quotes.
[/pullquote]
```

### Emitted HTML — Traven contract

```html
<blockquote class="traven-component-blockquote">
  <p>Quote…</p>
  <footer><cite>— Author, Source</cite></footer>
</blockquote>

<blockquote class="traven-component-pullquote">
  <p>Editorial emphasis.</p>
</blockquote>
```

### Emitted HTML — PenCMS PHP (component path)

```html
<blockquote class="traven-component-blockquote">
  <div class="component-body">…</div>
  <cite class="attribution">— Author, Source</cite>
</blockquote>

<blockquote class="traven-component-pullquote">
  <div class="component-body">…</div>
</blockquote>
```

Style `footer`/`cite`, `.attribution`, and `.component-body` so either skeleton works.

**Caveat:** a bare PenCMS `[quote …]` path (without going through `renderComponentHtml`) may emit a plain `<blockquote>` plus `.attribution` without `traven-component-blockquote`. Prefer `[blockquote]` / `[component name="blockquote"]` for consistent classes; still give native `blockquote` readable defaults.

### Classes

| Role | Selector |
|---|---|
| Editor | `.cm-wysiwym-component-shortcode.component-blockquote`, `.component-pullquote`; body `.component-body`; `cite` |
| Preview | `.traven-component-blockquote`, `.traven-component-pullquote` |

---

## 9. Notices — `[info]` / `[warning]`

### Syntax

```markdown
[info title="Optional"]Helpful context…[/info]
[warning collapsible="true" title="Caution"]Urgent note…[/warning]

[component name="info"]…[/component]
[component="warning"]…[/component]
```

### Attributes

| Attr | Notes |
|---|---|
| `title` | Optional header text |
| `collapsible` | PenCMS: `"true"` → `<details open>` + `<summary class="component-header">` |

### Emitted HTML

```html
<div class="traven-component traven-component-info">
  <div class="component-header"><span class="component-title">…</span></div><!-- if title -->
  <div class="component-body">…</div>
</div>

<!-- collapsible (PenCMS) -->
<details class="traven-component traven-component-warning" open>
  <summary class="component-header"><span class="component-title">…</span></summary>
  <div class="component-body">…</div>
</details>
```

### Classes

| Role | Selector |
|---|---|
| Editor | `.cm-wysiwym-component-shortcode.component-info`, `.component-warning` |
| Preview | `.traven-component-info`, `.traven-component-warning`, `.component-header`, `.component-title`, `.component-body` |

---

## 10. Generic `[component]`

### Syntax

```markdown
[component name="my-card"]…[/component]
[component="my-card"]…[/component]
```

### Emitted HTML — Traven / checklist

```html
<div class="traven-component traven-component-my-card">
  …
</div>
```

### PenCMS fallback (no theme Twig partial)

```html
<div class="custom-component component-my-card">…</div>
```

If a theme registers a Twig partial matching `name`, PenCMS may render that instead. Unknown names should still get a sensible default via `.traven-component` and/or `.custom-component`.

### Classes

| Role | Selector |
|---|---|
| Editor | `.cm-wysiwym-component-shortcode` |
| Preview | `.traven-component`, `.traven-component-{name}`, `.custom-component`, `.component-{name}` |

---

## 11. `[highlight]` / `==mark==`

### Syntax

```markdown
[highlight]important phrase[/highlight]
==important phrase==
```

PenCMS also accepts optional `intent` / `color` on `[highlight]` (may add `intent-*` class or inline background). Prefer skinning bare `mark` for dual-duty parity with Traven’s zero-inline-style default.

### Emitted HTML

```html
<mark>…</mark>
```

### Classes

| Role | Selector |
|---|---|
| Editor | `.cm-wysiwym-highlight` (for `==mark==`); highlight shortcode folds inline |
| Preview | `.traven-preview mark` |

Ensure readable contrast in light and dark (`.cm-wysiwym-dark` / preview dark).

---

## 12. GitHub alerts (admonitions)

Not a bracket shortcode — a GFM-style blockquote whose first line is `[!TYPE]`:

```markdown
> [!NOTE]
> Useful information that users should know.

> [!TIP]
> Helpful advice for doing things more quickly or easily.

> [!IMPORTANT]
> Key information users need to know to achieve their goal.

> [!WARNING]
> Urgent info that needs immediate user attention to avoid problems.

> [!CAUTION]
> Advises about risks or negative consequences of an action.
```

### Types and aliases

| Author writes | Normalized type / class suffix |
|---|---|
| `[!NOTE]` | `note` |
| `[!INFO]` | → `note` (Traven alias) |
| `[!TIP]` | `tip` |
| `[!IMPORTANT]` | `important` |
| `[!WARNING]` | `warning` |
| `[!CAUTION]` | `caution` |
| `[!DANGER]` | → `caution` (Traven alias) |

PenCMS `PostRenderer` postprocess matches the five canonical markers (`NOTE`, `TIP`, `IMPORTANT`, `WARNING`, `CAUTION`). Prefer those in published content.

### Emitted HTML

```html
<!-- Traven preview (typical) -->
<div class="traven-alert traven-alert-note">…</div>

<!-- PenCMS publish today -->
<blockquote class="traven-alert traven-alert-note"><p>…</p></blockquote>
```

No built-in titles or icons — add labels via CSS if desired (e.g. `.traven-alert-note::before`).

### Classes

| Role | Selector |
|---|---|
| Preview / publish | `.traven-alert`, `.traven-alert-note`, `.traven-alert-tip`, `.traven-alert-important`, `.traven-alert-warning`, `.traven-alert-caution` |
| Native blockquotes | Exclude alerts when styling plain quotes: e.g. `blockquote:not(.traven-alert):not(.traven-component-pullquote)` |

---

## 13. `[expand]` / `[embed]` (PenCMS)

Site-owned post transclusion. Deep product behavior: [`editor-link-suggest-and-expand.md`](editor-link-suggest-and-expand.md).

### Syntax

```markdown
[expand slug="other-post" text="Read more" heading="Section title"]
[expand slug="other-post" text="Finland" source="summary"]
[expand slug="other-post" text="Finland" source="deck"]
[embed slug="other-post#Section"]
[expand="other-post"]
```

### Attributes

| Attr | Notes |
|---|---|
| `slug` (or positional / `="…"`) | Target entry id; may include `#heading` |
| `heading` | Optional section within the target (do not combine with `source`) |
| `source` | Optional body source; `summary` = frontmatter summary nutshell; `deck` = frontmatter deck nutshell; each + Read more CTA |
| `text` | Expand trigger label (overrides heading/title) |

Label precedence: `text` → `heading` → display title → `slug`. Missing/unpublished targets are **silently omitted** on the reader. Empty chosen field with `source="summary"` or `source="deck"` is also omitted (no cross-field or whole-post fallback). `source` + `heading` together → omit.

### Emitted HTML

```html
<!-- embed — always visible -->
<div class="traven-embed" data-slug="…" data-heading="…?" data-source="…?">
  <div class="traven-embed-content">{resolved body HTML}</div>
</div>

<!-- expand — collapsed until clicked -->
<button type="button" class="traven-expand-trigger" data-traven-expand="{id}"
  data-slug="…" data-heading="…?" data-source="…?" aria-expanded="false">{label}</button>
<template id="{id}">{resolved body HTML}</template>
```

For `source="summary"` or `source="deck"`, resolved body is the rendered field with an inline `<a class="traven-expand-read-more" href="…" target="_blank" rel="noopener">Read more</a>` (URL via `ShortcodeProcessor::resolveContentUrl`, same as `[link]`).

Runtime (`initExpandEmbed`) inserts `.traven-expand-content.traven-expand-panel` (+ `.traven-expand-panel-arrow`) after the trigger; trailing punctuation may become `.traven-expand-punct`.

### Theme assets (Required for keepers)

Load both:

- `publicAsset('vendor/traven/expand-embed.css')` (or equivalent)
- `expand-embed-runtime.js` (`initExpandEmbed`)

### Classes to style

`.traven-expand-trigger`, `.traven-expand-panel`, `.traven-expand-content`, `.traven-expand-panel-arrow`, `.traven-expand-punct`, `.traven-expand-read-more`, `.traven-embed`, `.traven-embed-content`

---

## 14. Align × size matrices

Theme authors should implement all 16 combinations for **image**, **video**, and **audio** (Required). Fullbleed still receives a size class; apply size inside the breakout where it still makes sense.

### Image

|  | `small` | `medium` | `large` | `full` |
|---|---|---|---|---|
| `left` | ✓ | ✓ | ✓ | ✓ |
| `right` | ✓ | ✓ | ✓ | ✓ |
| `center` | ✓ | ✓ | ✓ | ✓ |
| `fullbleed` | ✓ | ✓ | ✓ | ✓ |

### Video

|  | `small` | `medium` | `large` | `full` |
|---|---|---|---|---|
| `left` | ✓ | ✓ | ✓ | ✓ |
| `right` | ✓ | ✓ | ✓ | ✓ |
| `center` | ✓ | ✓ | ✓ | ✓ |
| `fullbleed` | ✓ | ✓ | ✓ | ✓ |

### Audio

|  | `small` | `medium` | `large` | `full` |
|---|---|---|---|---|
| `left` | ✓ | ✓ | ✓ | ✓ |
| `right` | ✓ | ✓ | ✓ | ✓ |
| `center` | ✓ | ✓ | ✓ | ✓ |
| `fullbleed` | ✓ | ✓ | ✓ | ✓ |

---

## 15. Editor widget class cheat sheet

| Shortcode | Editor container |
|---|---|
| `[image]` | `.cm-wysiwym-image-shortcode-container` |
| Legacy `![alt](src)` | `.cm-wysiwym-image-widget-container` |
| `[video]` | `.cm-wysiwym-video-shortcode-container` |
| `[audio]` | `.cm-wysiwym-audio-shortcode-container` |
| `[figure]` | `.cm-wysiwym-figure-shortcode` |
| Components / quotes / notices | `.cm-wysiwym-component-shortcode` (+ `.component-blockquote`, `.component-pullquote`, `.component-info`, `.component-warning`) |
| `==highlight==` | `.cm-wysiwym-highlight` |

Full child selectors, modal scope, and dark mode: [`traven-theme-development.md` §3](traven-theme-development.md#3-the-selector-reference).

---

## 16. Related non-shortcode content

Themes that advertise diagram/math support also need footer hooks (not shortcode CSS alone):

- **Mermaid** — fenced ` ```mermaid ` blocks; auto-render in theme footer (match starter/editorial).
- **KaTeX** — `$…$` / `$$…$$`; live widgets `.cm-wysiwym-inline-math-widget` / `.cm-wysiwym-block-math-widget`; preview `.katex` / fallbacks — see theme-dev §6.6.

---

## 17. Extending Traven shortcodes

Hosts and plugins can add shortcodes via Traven’s decoupled layers (not PenCMS theme work):

1. **Grammar & parser** — detect tags/attrs in the Markdown parser.
2. **WYSIWYM widget** — CodeMirror `WidgetType` when the cursor is outside the shortcode range.
3. **Skin CSS** — tokens for `.cm-wysiwym-*` and `.traven-preview` equivalents.

PenCMS-only tags (e.g. expand/embed resolution, asset path rewriting) stay in PHP/`ShortcodeProcessor`, not in `traven.js`.
