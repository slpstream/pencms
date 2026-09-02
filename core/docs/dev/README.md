# Developer Documentation

Guides for developers who want to dig deeper into PenCMS internals — host wiring, admin Alpine, PHP resolvers, multisite, and MCP — rather than operator how-tos alone.

---

## Knowledgebase

- **[Knowledgebase](knowledgebase.md)** — Living sticky notes for easy-to-forget host truths (expand `text` vs `heading`, Alpine `store.pages`, Host/JWT site binding, AI content rules), plus a DRY map of canonical docs and a “where to look in code” cheat sheet.

## Theme contracts

- **[PenCMS theme development](../pencms-theme-development.md)** — Complete theme blueprint (layers, dual-duty, shortcodes, checklist).
- **[Traven dual-scope CSS / editor skinning](traven-theme-development.md)** — CodeMirror 6 live-widget selector bible and dual-DOM-scope rules.
- **[Theme Social / OG (`social_preview`)](theme-social-preview.md)** — Required `theme.json` Social Previews block, fonts (TTF vs woff2), two image jobs, Twig globals, checklist for new themes.
- **[Theme style settings (`style` block)](../pencms-theme-development.md)** — Optional operator-tunable CSS custom properties in `theme.json` (Admin Settings → Theme → Style Settings).
- **[Adding themes](../theme-adding.md)** — Scaffold, switch, validate quick-start.

## Editor & AI host wiring

- **[TravenEditor API reference](AI-and-TravenEditor-API-reference.md)** — Low-level JS API options, methods, and events for the vendored `TravenEditor` instance.
- **[Host vs editor philosophy](AI-MCP-Traven.md)** — Architecture rationale on host-owned MCP vs embedded editor.


Feature-length operator and feature guides remain under [`core/docs/`](../). Operator SEO how-to: [`seo-settings.md`](../seo-settings.md). Traven CodeMirror / WYSIWYM internals live in the sibling Traven repo (`traven/docs/dev/knowledgebase.md`).
