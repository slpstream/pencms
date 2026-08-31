# SEO Settings (operator How-To)

Configure how each site appears in search results and when someone shares a link — from **Settings → SEO** in the admin sidebar.

SEO Settings is **site-scoped**. The active Content site (header switcher) is the site you are editing. Switch sites before changing Meta, Social, or Indexing.

This page sets **defaults and infrastructure**. Per-post Open Graph titles, descriptions, and images still come from the editor / frontmatter when a page defines them.

---

## What the three tabs do

| Tab | Job |
|---|---|
| **Site Meta** | Public sitename, tagline, hero title, title template, default meta description, keywords |
| **Social Previews** | How links look when shared (OG / Twitter), plus how generated share images look |
| **Indexing** | Robots defaults, sitemap discovery flag, Google / Bing verification tokens, optional IndexNow, AI-training Content-Signal, static 301 list |

One **Save** persists Meta + Indexing + Social for the active site.

---

## Site Meta

**Site Identity** fields (sitename, tagline, index hero title) are also editable under Settings → Site and Settings → Sites. Changes sync across those surfaces.

**Search Appearance**

- **Title template** — how page titles compose with the site name. Placeholders: `%page%`, `%site%`. Default: `%page% | %site%`.
- **Default meta description** — used when a post/page has no description of its own. Aim for about 150–160 characters.
- **Keywords** — optional / legacy; not used by Google for ranking.

---

## Social Previews

Out of the box, the **active theme** already ships complete Social / Open Graph defaults. You do **not** need to visit this tab for shares and generated images to work. Use it only when you want this site to diverge from the theme.

Unset fields show a **Theme default** tip. Clearing a field (or **Reset to theme defaults**) returns that setting to the theme.

### Share defaults

| Control | What it does |
|---|---|
| **Twitter card type** | Usually `summary_large_image` (large image card) or `summary` |
| **OG title / description fallbacks** | Used in meta tags when the page has no OG title or description |
| **Default share image** | Classic site-wide `og:image` for the homepage and bare links when no per-page image exists |

Upload a 1200×630 image when you want a fixed brand share graphic (distinct from generated per-post images).

### Generated image look

These settings control how `og-image-maker` styles **per-slug** share images during publish/build:

- Accent / vignette / text / bar colors
- Font (theme `og_fonts` plus the core registry; Pillow converts vendored woff2 locally)
- Headline style: `redacted`, `shadow`, `plain`, `left`, `left_redacted`, `center`, `center_redacted`, `outline`, `banner`, `boxed`, `underline`, `caption`, `poster`
- Text casing: `upper`, `title`, or `as_is`
- Color grade: `noir`, `clean`, `none`, `vibrant`, `warm`, `cool`, `fade`, `high_contrast`, `sepia`, `mono`, `dusk`, `night`, `paper`
- Accent bar on/off
- Watermark on/off (whether to composite the PNG)
- Fallback title text when a page has no title

Canvas size, JPEG quality, and raw Pillow knobs stay engine-only — not exposed here.

**Generate preview** sits beside the look controls on wide screens (sticky while you scroll the knobs). It renders one 1200×630 JPEG through the same Pillow path publish uses, from the **current form values** — not only what you last saved. Look changes (colors, font, style, casing, grade, accent bar, watermark on/off, use-site-hero) auto-refresh the image after a short pause. Sample title is the headline drawn on the card; it applies when you click **Generate preview** or leave the field (not live-as-you-type). Optionally use the site hero as the background when the site has one. Unsaved fallback hero / watermark drops are included in the preview; **Save** is still required to persist them.

### Generator assets (two different image jobs)

Do not confuse these with the default share image above:

| Asset | Job |
|---|---|
| **Generator fallback hero** | Background used by the image maker when a post has **no** featured/hero image |
| **Watermark overlay** | PNG composited on generated images when **Include watermark** is on |

**Watermark source** chooses what to composite: the theme overlay, the **site logo** (referenced at generate time from `images/logo.png` / `.webp` / `.jpg` — not copied into `og-watermark`), or a custom file. Site logo always uses **corner** placement. Theme overlays default to **full canvas** (1200×630). Corner placement has a named corner (TL / TR / BL / BR) and size (S / M / L). SVG logos are skipped — upload a PNG or WebP under Settings → Site if you want the logo on share images.

### Reset to theme defaults

Clears all Social overrides for this site in the form. Click **Save** to persist. After that, the active theme’s presets apply again. Switching themes also changes inherited defaults automatically; explicit site overrides remain until you clear them.

---

## Indexing

| Control | What it does |
|---|---|
| **Allow indexing / following** | Default `robots` meta (`index`/`noindex`, `follow`/`nofollow`) for URLs that do **not** set frontmatter `noindex`. Indexable URLs also get `max-image-preview:large`. |
| **Custom robots.txt** | Optional full body; leave empty to auto-generate from the toggles |
| **Include sitemap in robots.txt** | When on, generated robots.txt lists `/sitemap.xml` and the public map is served at that path |
| **Google / Bing verification** | Paste the meta `content` token from Search Console or Bing Webmaster |
| **IndexNow** | Optional ping to Bing, Yandex, Seznam, and Naver after a successful **public HTTPS** publish. Not Google. Unique per-site key; the build writes `dist/<key>.txt`. Localhost / private / preview hosts are skipped. A failed ping never blocks publish or `generate-static.php`. |
| **Allow AI training** | Content-Signal `ai-train` on markdown and `llms*.txt` headers (`yes` when on, `no` when off). Retrieval (`search=yes`, `ai-input=yes`) stays on. Default robots.txt does **not** block GPTBot, ClaudeBot, or PerplexityBot. |
| **Static redirects** | One `from -> to` path pair per line. When non-empty, `generate-static.php` emits Apache `RewriteRule` 301s in `.htaccess` and a Netlify/Cloudflare `_redirects` file. |

Public robots meta and verification tags are injected for all themes. `/robots.txt` is Host-scoped per site.

### Per-URL `noindex`

A published post or page can stay live while dropping out of discovery:

```yaml
---
name: Internal Release Notes
noindex: true
---
```

The editor **Hide from search engines** checkbox writes this field (posts and pages). When `noindex` is true:

- HTML for that URL emits `<meta name="robots" content="noindex,nofollow">`, overriding the site-wide indexing default for that page only. It cannot re-enable indexing if the site toggle is already off.
- The URL is omitted from `sitemap.xml` (static and preview), `feed.xml` / RSS, `llms.txt`, `llms-full.txt`, `content.jsonl`, and `search-index.json`. **Posts are filtered**, not only pages.
- HTML, canonical `index.md`, and `/slug.md` copies are still written so the unlisted URL exists.

Site-wide **Allow indexing / following** remains the default for URLs without this flag. i18n v1: `llms.txt` / `llms-full.txt` / `content.jsonl` / RSS stay default-language only; a localized sibling with `noindex` still gets per-URL robots on its HTML.

The public **search** HTML (`/search/` and localized `/<lang>/search/`) prefers `noindex` (thin SERP). Category archives stay out of the sitemap and are not auto-noindexed in this wave.

Every public HTML page also gets `<link rel="alternate" type="text/plain" href="…/llms.txt" title="LLM index">` when a public site URL (or absolute canonical origin) is known. That file is a static-build artifact; the PHP preview may 404 it.

### Structured data (JSON-LD)

PenCMS injects Schema.org JSON-LD in the theme engine (`ThemeEngine::injectJsonLd()`), the same way canonical and robots tags are injected. Themes do **not** need Twig edits. Existing `application/ld+json` in a template is left alone.

| Surface | `@type` |
|---|---|
| Home | `WebSite` with nested `publisher` `Organization` (`logo` when a public URL exists; `sameAs` from site social links), `inLanguage`, and `potentialAction` `SearchAction` targeting `/search/?q={search_term_string}` (localized homes use `/<lang>/search/`) |
| Post | `BlogPosting` plus `BreadcrumbList`. `datePublished` / `dateModified` (same source as `article:modified_time`: `updated` or `modified_at`, else the published date), `inLanguage`. Matched byline from `authors.yaml` emits Person `url` (`website`), `description` (`bio`), `jobTitle` (`role`), and `image` when a public avatar URL exists. Unmatched byline stays name-only. |
| Page (`page: true`) | `WebPage` plus `BreadcrumbList` — not `BlogPosting`. `inLanguage`. |
| Post / page with non-empty `faqs` | `FAQPage` in addition to `BlogPosting` or `WebPage`. `mainEntity` questions and answers are the same strings as the visible `<dt>` / `<dd>` list. Empty or missing `faqs` emits no `FAQPage` and no `.pen-qa` chrome. Never derived from `[expand]`, headings, or `llms.txt`. |
| Search / category archives | none in this wave |

Empty `faqs: []` is valid. Poetry, a two-paragraph news brief, and most posts should ship with no Q&A — that is success, not a missing checkbox. Do **not** generate FAQ from `[expand]` / accordion shortcodes (those are transclusion), from heading heuristics, or from a hidden agent-only blob. Agents already have the full markdown corpus.

MCP agents persist `summary` / `faqs` immediately (no wand preview): [`mcp_guide.md` Extractive summary and FAQs](./mcp_guide.md#extractive-summary-and-faqs). Human Magic Wand and dashboard fill stay preview-or-batch UI.

When a page *does* answer questions (docs, product, some news explainers), fill the first-class `faqs: [{q, a}]` list. A **Backgrounder** on a news explainer is that same list with different chrome, not a second schema type. The public heading comes from i18n strings `faq` / `backgrounder`; a theme opts into Backgrounder with `"qa_heading": "backgrounder"` in `theme.json` (omitted or unknown → FAQ). Schema `@type` stays `FAQPage` either way. The heading is chrome only — JSON-LD strings must match the visible Q&A pairs, not the heading.

### Language tags and share meta (engine-injected)

When a post or page has **two or more** live published language siblings, the theme engine injects `<link rel="alternate" hreflang="…">` for each sibling **and** `hreflang="x-default"` pointing at the **default-language** URL (unprefixed `/slug/`), not the URL of the HTML being viewed. Home, search, and category archives do not get an hreflang cluster in this wave. Preview and `dist/` use the same injector.

The engine also injects:

- `og:locale` from the page language (Facebook form, e.g. `en` → `en_US`, `fr` → `fr_FR`)
- `og:locale:alternate` for other languages in that same published sibling set
- On **posts** only: `article:published_time` and `article:modified_time` (ISO-8601 UTC from the dateline; modified uses frontmatter `updated` or API `modified_at` when present, otherwise the published date)

Themes do not need Twig edits for these tags.

### Sitemap (`/sitemap.xml`)

When **Include sitemap in robots.txt** is on, `/sitemap.xml` is available for the active public site. It lists the site home plus every **live-published, indexable** post and page URL (`status=published`, respecting `publish_at` embargoes; frontmatter `noindex: true` is omitted). When i18n is active, it also lists `/<lang>/<slug>/` for each exact live-published sibling that is not `noindex`. Translation groups with two or more indexable URLs include matching `xhtml:link` hreflang annotations (including `x-default` to the default-language loc) on every URL in the group. Single-language slugs stay loc + lastmod only. Draft, unpublished, embargoed, noindex, and missing siblings never create sitemap URLs or xhtml hrefs. Existing default-language URLs remain at `/<slug>/`; they are not moved under the default language code. Category archives, search, and feed URLs are not included in V1. Google ignores sitemap `priority` / `changefreq`; PenCMS does not emit them.

- **Disabled:** `/sitemap.xml` returns **404** (dynamic preview) and is omitted from static builds; robots.txt does not advertise a Sitemap line.
- **Multisite:** Resolved the same way as robots — Host header, then `?site=`, then cookie. Each sitemap contains only that site's default content and exact published siblings.
- **Static publish:** `generate-static.php` writes `sitemap.xml` and `robots.txt` into the dist output when appropriate.
- **Preview without domain:** Absolute URLs use the request Host (same fallback as the RSS feed).

### Language policy for generated discovery outputs

- **Published-site `llms.txt`:** the static site's generated `llms.txt` is an [llmstxt.org](https://llmstxt.org) index: sitename, optional tagline, **Pages** and **Posts** (with one-line excerpts from `deck`), optional HTML/markdown home links, and archive links (`llms-full.txt`, `content.jsonl`, `feed.xml`, `sitemap.xml`). It links default-language Markdown only and **omits `noindex` posts and pages**. PenCMS does not emit `/<lang>/llms.txt` in i18n v1. This is **not** the product MCP discovery file (`core/docs/llms.txt`, served as install `GET /llms.txt`). Do not add a `llm.txt` alias.
- **Published-site `llms-full.txt`:** one-GET concatenated corpus of published, indexable pages and posts as **native markdown** (never HTML reverse-converted), each preceded by a title / HTML URL / date header. Soft-capped at about 2 MiB with a truncation footer if the rest would not fit. Default-language only — there is no `/<lang>/llms-full.txt` in i18n v1. `noindex` URLs are omitted (posts and pages).
- **Search index:** `search-index.json` records include `lang` only when i18n is active. The root index marks default rows with the default language; localized merged indexes preserve each row's actual language, including default-language fallback rows. **`noindex` posts and pages are omitted.**
- **RSS:** `feed.xml` deliberately remains default-language-only. PenCMS does not emit `/<lang>/feed.xml` in i18n v1. `noindex` posts are omitted.
- **Markdown mirrors:** canonical agent URL remains `/<slug>/index.md` (and `/<lang>/<slug>/index.md` for exact localized siblings). Static builds also write a **byte copy** at `/<slug>.md` (and `/<lang>/<slug>.md` when that localized `index.md` exists) so hosts without Accept rewriting still serve guessable paths. Root `index.md` is the posts archive, not aliased.

### Static headers (markdown and LLM corpora)

`generate-static.php` writes `.htaccess`, plus example `Caddyfile` and `nginx.conf.example`, into `dist/` (for serving that directory — not the API reverse-proxy in `deploy/Caddyfile`).

| Header | `.md` | `llms.txt` / `llms-full.txt` |
|---|---|---|
| Content-Type | `text/markdown; charset=utf-8` | `text/plain; charset=utf-8` |
| `X-Robots-Tag` | `noindex` | `noindex` |
| `Vary` | `Accept` (also on `.html`, including Caddy / nginx examples) | — |
| Content-Signal | `search=yes, ai-input=yes, ai-train=no` (default) or `ai-train=yes` when **Allow AI training** is on | same |

The Apache Accept rewrite to `index.md` remains a bonus; `/slug.md` copies are the primary GEO URL. **Content-Signal training is a site SEO setting**, not hardcoded `ai-train=yes`.

### IndexNow (Bing family, not Google)

When **Ping IndexNow after publish** is on, each site gets a unique key stored in the site registry (`data/sites.yaml`, not the git repo). Static builds write `dist/<key>.txt` with that key as the body. After a successful publish to a public `https` host, PenCMS POSTs HTML sitemap URLs (preferring changed HTML files when the publish pipeline has a diff) to `api.indexnow.org`. That notifies Bing, Yandex, Seznam, and Naver. It does **not** update Google. Skip localhost, RFC1918, and special-use / preview hosts. Failures are logged; publish still succeeds.

Standalone `generate-static.php` may also ping when the site URL is public `https` and `PENCMS_SKIP_INDEXNOW` is unset. Host deploy sets that variable during the build and pings only after the files are live.

### Static 301s

A minimal redirect list on the Indexing tab (same-site paths only) is compiled into `dist/.htaccess` RewriteRules and `dist/_redirects` when the list is not empty.

---

## Resolution order (shares and OG images)

When a visitor or crawler sees a page:

1. **This page’s** frontmatter / editor SEO fields (highest)
2. **Site** Social / Meta overrides you saved here
3. **Active theme** Social / OG defaults
4. **Engine** safety defaults (rare; only if a theme omits something)

Fonts for generated images are local files (theme TTF/OTF, then the core registry with on-the-fly woff2→TTF, then a platform fallback). PenCMS does **not** fetch Google Fonts from the network while building images.

---

## Related

- Theme authors: [`dev/theme-social-preview.md`](./dev/theme-social-preview.md) — `social_preview` contract in `theme.json`
- Themes (blueprint): [`pencms-theme-development.md`](./pencms-theme-development.md) · quick-start: [`theme-adding.md`](./theme-adding.md)
- Publish / static build (when OG JPGs are generated): [`publish-howto.md`](./publish-howto.md)
