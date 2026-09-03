# Zero-to-Hero (draft skill)

> **Draft / aspirational skill packaging.** This is a bootstrap checklist for agents, not a polished Cursor skill-market package. Prefer live tool behavior in [`mcp_guide.md`](./mcp_guide.md) when anything disagrees.
>
> **Zero means a blank bound site** — no menus, authors, posts, or media yet. Steps are **order-independent**; the numbered list is recommended guidance only. Never require existing menus/authors/posts before identity, theme, or SEO.

## Prerequisites (human — not MCP)

| Step | Status | Notes |
|---|---|---|
| Site exists in registry | human | `POST /api/sites` (admin). Prefer a dedicated site so posts do not collide with a human blog — [`agent-owned-site.md`](./agent-owned-site.md) |
| Agent key bound to that `site_id` with `read` + `write` (+ `publish` if deploying) | human | Settings → AI → Agent Keys / approve-code. Name `{site}-{agent}` |

## Bootstrap canvas

| # | Action | Tool(s) |
|---|---|---|
| 1 | Discover collections / taxonomy | `get_site_config` |
| 2 | Choose theme | `list_themes` → `update_site_presentation({ "theme": "…" })` |
| 3 | Read effective presentation | `get_site_presentation` |
| 4 | Set identity + Site Meta + Indexing (sparse) | `update_site_presentation` |
| 5 | Social overrides only if brand brief needs them | `get_site_presentation` then sparse `update_site_presentation` |
| 6 | Branding assets | `write_media_file` + path fields via `update_site_presentation` |
| 7 | Menus from empty `menus.yaml` | `list_menus` / `create_menu_item` / `replace_menu_slot` / … |
| 8 | Authors from empty `authors.yaml` | `list_authors` / `create_author` / … |
| 9 | Taxonomy bootstrap (vocabs + terms) | `get_taxonomy` / `replace_taxonomy` (before first posts). Cap `write:taxonomy`. Not collections.yaml / Publishing Rules. |
| 10 | First posts + per-page OG frontmatter | `create_post` (stub) / `write_content_file` |
| 11 | Extractive `summary` / optional `faqs` | After body: `get_site_prompts` `extractive_prompts` → `update_frontmatter_field`. Persist immediately. How-to: [`mcp_guide.md`](./mcp_guide.md#extractive-summary-and-faqs) |
| 12 | Git + host publish when ready | `commit_and_push` / `publish_site` |

## Rules

1. **Empty-safe.** Presentation tools do not require menus, authors, or posts. Menu/author/content tools tolerate empty YAML / empty trees.
2. **Social is sparse.** Theme `social_preview` already makes an empty Social tab valid. Read `social_effective` / `social_preview_defaults` first; write overrides only when the brief diverges. Empty string clears a string field; `og_accent_bar: null` clears that bool.
3. **Do not** copy full theme Social JSON into site overrides. Do not expose or invent Tier-3 engine knobs (canvas size, Pillow floats, system font paths).
4. **Branding paths** (same basenames as admin storage uploads):
   - Files via `write_media_file`: `images/logo.png`, `images/favicon.ico`, `images/hero.jpg`, `images/og-default.jpg`, `images/og-defaulthero.jpg`, `images/og-watermark.png`
   - SiteRecord path fields via `update_site_presentation`: `hero_image`, `og_default_image`, `og_default_hero`, `og_watermark`
   - Logo/favicon: file presence alone is enough (PHP convention lookup)
5. **Per-page OG** stays on `write_content_file` frontmatter (high-frequency path once posts exist).
6. **No OG generate-preview** in this skill — that remains a later human affordance.
7. **Site-bound only.** JWT `site_id` is authoritative; never attempt cross-site presentation edits.

## Suggested sparse identity patch

```json
{
  "theme": "starter",
  "sitename": "Acme Blog",
  "tagline": "Notes from the workshop",
  "hero_title": "Welcome",
  "title_template": "%page% | %site%",
  "meta_description": "Short site-wide default description.",
  "robots_index": true,
  "robots_follow": true,
  "sitemap_enabled": true
}
```

Add Social keys only when needed (e.g. `twitter_card`, `og_default_image`, color overrides).

## Related docs

- Tool catalog: [`mcp_guide.md`](./mcp_guide.md)
- Human sponsor + dedicated site: [`agent-owned-site.md`](./agent-owned-site.md)
- Operator SEO: [`seo-settings.md`](./seo-settings.md)
- Theme Social contract: [`dev/theme-social-preview.md`](./dev/theme-social-preview.md)
- Discovery index: [`llms.txt`](./llms.txt)
- Connect stub: [`mcp_skill.md`](./mcp_skill.md)
