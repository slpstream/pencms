# Traven / PenCMS Component Reference (MDX + Wikilinks)

Theme-author inventory of authoring syntax: MDX components, wikilinks, emitted HTML, and CSS classes for the editor (WYSIWYM) and published preview. Use this for **classes and attrs**; dual-scope styling rules, float restrictions, and the full selector bible live in [`traven-theme-development.md`](dev/traven-theme-development.md) (§1, §3, §4.4, §6).

Authoring is two families only:

| Family | Syntax | Purpose |
|---|---|---|
| **MDX components** | `<Image />`, `<Video />`, `<Quote>`, `<Callout>`, `<Component>` … | Media / layout / UI blocks |
| **Wikilinks** | `[[slug]]`, `[[slug\|Label]]`, `[[!slug]]`, `[[>slug]]` | Internal links + transclusion |

Single brackets are pure CommonMark (`[text](url)`, `- [ ]`, `> [!NOTE]`). Legacy `[image]` / `[expand]` / `[link]` shortcodes are **not compiled** — leftovers render as plain text.

---

## 1. Purpose and dual pipeline

| Surface | Scope | Class prefix / wrapper |
|---|---|---|
| Admin editor (WYSIWYM) | Live CodeMirror widgets | `.cm-wysiwym-*` inside `.cm-editor` |
| Published / HTML preview | Reader HTML inside the content body | Prefer `.traven-preview …` (themes must put `class="article-content traven-preview"` on post/page bodies) |

One content skin should style **both** scopes so editor and published page stay near pixel-parity. Shared layout helpers (`align-*`, `size-*`) appear on both editor widgets and preview markup.

### PenCMS published HTML vs Traven preview contract

**Primary styling contract** (compliance checklist, dual-duty skins, editor modals) is the **Traven** markup and class names documented below.

PenCMS reader HTML is produced by [`ComponentProcessor.php`](../../frontend-php/src/core/ComponentProcessor.php) + [`WikilinkProcessor.php`](../../frontend-php/src/core/WikilinkProcessor.php) **before** Markdown conversion ([`PostRenderer.php`](../../frontend-php/src/core/PostRenderer.php)). Both emit the same Session 5 class names as Traven preview, so one skin covers both. Differences left:

| Area | Traven preview | PenCMS PHP publish |
|---|---|---|
| Media classes | `img.traven-image`, `video.traven-video`, `audio.traven-audio` | Same |
| YouTube host | `youtube.com/embed` | `youtube-nocookie.com/embed` (privacy) — style both hosts |
| Wikilink links | `href="#"` (preview) | Real URL via `ContentUrls::resolveContentUrl` |
| GitHub alerts | Often `div.traven-alert.traven-alert-{type}` | `blockquote.traven-alert.traven-alert-{type}` |

Historical `.gallery-single` / `.photo-wrapper` wrappers are gone from body `<Image />` output. (PenCMS-only gallery Twig used by theme chrome templates for heroes is untouched.)

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
| `xsmall` / `xlarge` | **Non-canonical theme extras** — optional; do not count toward Required component coverage |

Typical skin widths (Traven docs; individual skins may differ slightly): `small` ~150px, `medium` ~300px, `large` ~600px, `full` 100%.

**Editor vs preview:** do **not** float component widgets in the editor (breaks CodeMirror geometry). Use auto-margins for left/right/center in `.cm-editor`; floats are fine under `.traven-preview`. Details: [`traven-theme-development.md` §4.4](dev/traven-theme-development.md#44-no-floats-or-vertical-margins-in-the-editor).

**Capitalization invariant:** only `<[A-Z]\w+>` is a component. Lowercase `<video>` / `<audio>` / `<image>` stay plain HTML.

---

## 3. Inventory

| Syntax | Kind |
|---|---|
| `<Image … />` | Media (self-closing) |
| `![alt](src)` | Classic Markdown image (non-advanced path) |
| `<Video … />` | Media |
| `<Audio … />` | Media |
| `<Figure …>…</Figure>` | Pair wrapper |
| `<Quote>` / `<Blockquote>` | Quote |
| `<Pullquote>` | Quote (distinct from blockquote) |
| `<Callout type="…">` | Notice |
| `<Component name="…">` | Generic / named block (theme Twig slot) |
| `==mark==` | Inline mark |
| `> [!NOTE]` (and TIP, IMPORTANT, WARNING, CAUTION) | GitHub alert |
| `[[slug]]` / `[[slug\|Label]]` | Internal link |
| `[[>…]]` / `[[!…]]` | PenCMS expand / embed transclusion |

---

## 4. `<Image />`

### Syntax

```markdown
<Image src="..." alt="..." align="center" size="medium" caption="Optional" class="my-class" />
```

Classic path (no layout attrs): `![alt](src)`.

When PenCMS PHP publishes classic Markdown images, caption-worthy alt text (non-empty and not literally `image`) becomes a visible caption:

```html
<figure class="classic-markdown-figure">
  <img class="classic-markdown" src="..." alt="…">
  <figcaption class="caption">…</figcaption>
</figure>
```

Themes should style `.classic-markdown-figure .caption` / `figcaption.caption` alongside component caption selectors. Empty alt or `![image](src)` stays a bare `<img class="classic-markdown">` with no figure.

### Attributes

| Attr | Required | Default | Notes |
|---|---|---|---|
| `src` | yes | — | Resolved via theme/asset paths in PenCMS |
| `alt` | no | falls back to `caption` | |
| `align` | no | `center` | `left` \| `right` \| `center` \| `fullbleed` |
| `size` | no | `medium` | `small` \| `medium` \| `large` \| `full` |
| `caption` | no | — | When set → figure + caption path |
| `class` | no | — | Extra classes on the outer wrapper |

### Emitted HTML (Traven + PenCMS — same)

```html
<!-- No caption -->
<img class="traven-image align-[alignment] size-[size] [custom]" src="..." alt="...">

<!-- With caption -->
<figure class="traven-image-figure align-[alignment] size-[size] [custom]">
  <img class="traven-image" src="..." alt="...">
  <figcaption class="traven-image-caption">Caption</figcaption>
</figure>
```

### Classes

| Role | Selector |
|---|---|
| Editor widget | `.cm-wysiwym-image-shortcode-container` (+ `.align-*`, `.size-*`); meta: `.shortcode-meta`, `.meta-badge`; edit: `.image-edit-icon` |
| Classic MD image widget | `.cm-wysiwym-image-widget-container` |
| Preview / publish | `.traven-preview img.traven-image`, `figure.traven-image-figure`, `figcaption.traven-image-caption` |
| Classic MD (PenCMS PHP) | `figure.classic-markdown-figure`, `img.classic-markdown`, `figcaption.caption` (alt-as-caption) |

---

## 5. `<Video />`

### Syntax

```markdown
<Video src="https://www.youtube.com/watch?v=…" align="center" size="medium" caption="…" class="…" />
<Video src="dQw4w9WgXcQ" />
```

YouTube is detected from watch/embed/v/`youtu.be` URLs (published embeds use **youtube-nocookie**); Vimeo URLs use the Vimeo player; direct files (`.mp4`, `.webm`, `.ogg`) render `<video controls>`.

### Attributes

| Attr | Required | Default | Notes |
|---|---|---|---|
| `src` | yes | — | URL or YouTube id |
| `align` | no | `center` | Layout contract values |
| `size` | no | `medium` | Layout contract values |
| `caption` | no | — | Adds `figcaption`; without it PenCMS emits the bare container |
| `class` | no | — | Extra classes on outer wrapper |

### Emitted HTML

```html
<!-- No caption -->
<div class="traven-video-container align-[a] size-[s] [custom]">
  <!-- iframe (youtube-nocookie / vimeo) or -->
  <video src="..." controls class="traven-video"></video>
</div>

<!-- With caption -->
<figure class="traven-video-figure align-[a] size-[s] [custom]">
  <div class="traven-video-container">…player…</div>
  <figcaption class="traven-video-caption">Caption</figcaption>
</figure>
```

### Classes

| Role | Selector |
|---|---|
| Editor | `.cm-wysiwym-video-shortcode-container` (+ placeholder children: `.video-placeholder`, `.video-placeholder-icon-wrap`, `.video-placeholder-details`, `.video-placeholder-platform`, `.video-placeholder-url`; `.video-edit-icon`) |
| Preview / publish | `.traven-video-container` (typically 16:9 `aspect-ratio`), `figure.traven-video-figure`, `figcaption.traven-video-caption`, `video.traven-video` |

---

## 6. `<Audio />`

### Syntax

```markdown
<Audio src="..." align="center" size="large" caption="…" class="…" />
```

### Attributes

| Attr | Required | Default | Notes |
|---|---|---|---|
| `src` | yes | — | e.g. `.mp3`, `.wav`, `.ogg` |
| `align` | no | `center` | |
| `size` | no | `medium` | Layout contract values |
| `caption` | no | — | |
| `class` | no | — | |

### Emitted HTML

```html
<!-- No caption -->
<div class="traven-audio-container align-[a] size-[s] [custom]">
  <audio class="traven-audio" controls src="..."></audio>
</div>

<!-- With caption -->
<figure class="traven-audio-figure align-[a] size-[s] [custom]">
  <div class="traven-audio-container">…</div>
  <figcaption class="traven-audio-caption">Caption</figcaption>
</figure>
```

### Classes

| Role | Selector |
|---|---|
| Editor | `.cm-wysiwym-audio-shortcode-container` (+ same placeholder shape as video; `.audio-edit-icon`) |
| Preview / publish | `.traven-audio-container`, `figure.traven-audio-figure`, `figcaption.traven-audio-caption`, `audio.traven-audio` |

---

## 7. `<Figure>…</Figure>`

### Syntax

```markdown
<Figure align="center">
… nested markdown / blocks …
</Figure>
```

Inner Markdown is compiled when restoring. `align` defaults to `center`.

### Emitted HTML

```html
<figure class="traven-figure align-[a]">
  <!-- nested block content -->
</figure>
```

### Classes

| Role | Selector |
|---|---|
| Editor | `.cm-wysiwym-figure-shortcode` (`.component-body`, `.figure-caption`, `.figure-edit-icon`) |
| Preview / publish | `.traven-preview .traven-figure` |

---

## 8. Quotes — blockquote vs pullquote

**Style these as two different designs.** Pullquotes should read heavier / more editorial than attributed blockquotes. Also style native Markdown `blockquote` separately (exclude pullquotes), e.g. `.traven-preview blockquote:not(.traven-component-pullquote)`.

### Syntax

```markdown
<Quote author="James Baldwin" source="The Fire Next Time">
Not everything that is faced can be changed…
</Quote>

<Pullquote>
Editorial emphasis that stands apart from body quotes.
</Pullquote>
```

`<Blockquote>` is an alias of `<Quote>`. `<Component name="blockquote">` / `<Component name="quote">` resolve the same way.

| Attr | Notes |
|---|---|
| `author` | Citation |
| `source` | Citation |

### Emitted HTML

```html
<blockquote class="traven-component-blockquote">
  <div class="component-body">…</div>
  <cite>— Author, Source</cite>
</blockquote>

<blockquote class="traven-component-pullquote">
  <div class="component-body">…</div>
</blockquote>
```

Style `cite` and `.component-body` for either skeleton.

### Classes

| Role | Selector |
|---|---|
| Editor | `.cm-wysiwym-component-shortcode.component-blockquote`, `.component-pullquote`; body `.component-body`; `cite` |
| Preview / publish | `.traven-component-blockquote`, `.traven-component-pullquote` |

---

## 9. Notices — `<Callout type="…">`

### Syntax

```markdown
<Callout type="info" title="Optional">Helpful context…</Callout>
<Callout type="warning" collapsible="true" title="Caution">Urgent note…</Callout>
```

### Attributes

| Attr | Notes |
|---|---|
| `type` | `info` (default) \| `warning` (any value becomes `traven-component-{type}`) |
| `title` | Optional header text |
| `collapsible` | `"true"` → `<div>` + inner `<details open>` + `<summary class="component-header">` |

### Emitted HTML

```html
<div class="traven-component traven-component-info">
  <div class="component-header"><span class="component-title">…</span></div><!-- if title -->
  <div class="component-body">…</div>
</div>

<!-- collapsible -->
<div class="traven-component traven-component-warning">
  <details open>
    <summary class="component-header"><span class="component-title">…</span><span class="component-toggle-icon"></span></summary>
    <div class="component-body">…</div>
  </details>
</div>
```

### Classes

| Role | Selector |
|---|---|
| Editor | `.cm-wysiwym-component-shortcode.component-info`, `.component-warning` |
| Preview / publish | `.traven-component-info`, `.traven-component-warning`, `.component-header`, `.component-title`, `.component-body`, `.component-toggle-icon` |

---

## 10. Generic `<Component name="…">`

### Syntax

```markdown
<Component name="my-card">…</Component>
<Component name="newsletter" title="…">…</Component>
```

### Emitted HTML

If the active theme ships `themes/{active}/components/{name}.twig`, that template renders with `slot` (compiled inner HTML) plus all MDX attrs. Otherwise the generic card:

```html
<div class="traven-component traven-component-my-card">
  <!-- optional header when title / collapsible -->
  <div class="component-body">…</div>
</div>
```

A starter example lives at `frontend-php/src/blog/themes/starter/components/newsletter.twig`. Names are sanitized to `[a-z0-9_-]+`.

### Classes

| Role | Selector |
|---|---|
| Editor | `.cm-wysiwym-component-shortcode` |
| Preview / publish | `.traven-component`, `.traven-component-{name}` |

---

## 11. `==mark==`

```markdown
==important phrase==
```

Prefer skinning bare `mark` for dual-duty parity with Traven’s zero-inline-style default.

### Emitted HTML

```html
<mark>…</mark>
```

### Classes

| Role | Selector |
|---|---|
| Editor | `.cm-wysiwym-highlight` (for `==mark==`) |
| Preview / publish | `.traven-preview mark` |

Ensure readable contrast in light and dark (`.cm-wysiwym-dark` / preview dark).

---

## 12. GitHub alerts (admonitions)

Not a component — a GFM-style blockquote whose first line is `[!TYPE]`:

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

## 13. Wikilinks — `[[slug]]` / `[[>…]]` / `[[!…]]` (PenCMS)

Site-owned internal links and post transclusion. Deep product behavior: [`editor-link-suggest-and-expand.md`](editor-link-suggest-and-expand.md).

### Syntax

```markdown
[[other-post]]
[[other-post|Read more]]
[[>other-post|Click for more]]
[[>other-post#Section Title|Click for more]]
[[>christmas-in-finland^summary|Finland]]
[[>christmas-in-finland^deck|Finland]]
[[!other-post]]
[[!other-post#Section]]
```

Extras parse left-to-right after the slug: `#Section` → heading slice, `^summary` / `^deck` → frontmatter nutshell source, first `|` starts the label. Incomplete `[[…` without `]]` on the same line stays text; fenced/inline code is never processed.

### Modes

| Form | Output |
|---|---|
| `[[slug]]` / `[[slug\|Label]]` | `<a class="traven-wikilink" href="{real URL}" data-slug="…">` |
| `[[!slug]]` (+ extras) | Always visible `<div class="traven-embed">` |
| `[[>slug]]` (+ extras) | Collapsed `<button class="traven-expand-trigger">` + `<template>` |

Label precedence: text → heading → display title → `slug`. Missing/unpublished targets are **silently omitted** on the reader. Empty chosen field with `^summary` or `^deck` is also omitted (no cross-field or whole-post fallback). Source + heading together → omit; unknown source → omit.

### Emitted HTML

```html
<!-- link -->
<a class="traven-wikilink" href="…" data-slug="…" data-heading="…?" data-source="…?">{label}</a>

<!-- embed — always visible -->
<div class="traven-embed" data-slug="…" data-heading="…?" data-source="…?">
  <div class="traven-embed-content">{resolved body HTML}</div>
</div>

<!-- expand — collapsed until clicked -->
<button type="button" class="traven-expand-trigger" data-traven-expand="{id}"
  data-slug="…" data-heading="…?" data-source="…?" aria-expanded="false">{label}</button>
<template id="{id}">{resolved body HTML}</template>
```

For `^summary` or `^deck`, resolved body is the rendered field with an inline `<a class="traven-expand-read-more" href="…" target="_blank" rel="noopener">Read more</a>` (URL via `ContentUrls::resolveContentUrl`).

Runtime (`initExpandEmbed`) inserts `.traven-expand-content.traven-expand-panel` (+ `.traven-expand-panel-arrow`) after the trigger; trailing punctuation may become `.traven-expand-punct`.

### Theme assets (Required for keepers)

Load both:

- `publicAsset('vendor/traven/expand-embed.css')` (or equivalent)
- `expand-embed-runtime.js` (`initExpandEmbed`)

### Classes to style

`.traven-wikilink`, `.traven-expand-trigger`, `.traven-expand-panel`, `.traven-expand-content`, `.traven-expand-panel-arrow`, `.traven-expand-punct`, `.traven-expand-read-more`, `.traven-embed`, `.traven-embed-content`

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
| `center` | ✓ | ✓ | ✓ | ✓ |
| `right` | ✓ | ✓ | ✓ | ✓ |
| `fullbleed` | ✓ | ✓ | ✓ | ✓ |

---

## 15. Editor widget class cheat sheet

| Syntax | Editor container |
|---|---|
| `<Image />` | `.cm-wysiwym-image-shortcode-container` |
| Legacy `![alt](src)` | `.cm-wysiwym-image-widget-container` |
| `<Video />` | `.cm-wysiwym-video-shortcode-container` |
| `<Audio />` | `.cm-wysiwym-audio-shortcode-container` |
| `<Figure>` | `.cm-wysiwym-figure-shortcode` |
| Components / quotes / notices | `.cm-wysiwym-component-shortcode` (+ `.component-blockquote`, `.component-pullquote`, `.component-info`, `.component-warning`) |
| `==highlight==` | `.cm-wysiwym-highlight` |

Full child selectors, modal scope, and dark mode: [`traven-theme-development.md` §3](dev/traven-theme-development.md#3-the-selector-reference).

---

## 16. Related non-component content

Themes that advertise diagram/math support also need footer hooks (not component CSS alone):

- **Mermaid** — fenced ` ```mermaid ` blocks; auto-render in theme footer (match starter/editorial).
- **KaTeX** — `$…$` / `$$…$$`; live widgets `.cm-wysiwym-inline-math-widget` / `.cm-wysiwym-block-math-widget`; preview `.katex` / fallbacks — see theme-dev §6.6.

---

## 17. Extending Traven components

Hosts and plugins can add components via Traven’s decoupled layers (not PenCMS theme work):

1. **Grammar & parser** — detect tags/attrs in the Markdown parser.
2. **WYSIWYM widget** — CodeMirror `WidgetType` when the cursor is outside the tag range.
3. **Skin CSS** — tokens for `.cm-wysiwym-*` and `.traven-preview` equivalents.

PenCMS-only resolution (expand/embed targets, asset path rewriting, named Twig slots) stays in PHP (`WikilinkProcessor` / `ComponentProcessor` / `ContentUrls`), not in `traven.js`.
