# PenCMS product thesis

**Status:** Approved direction. The north-star loop (named site-bound keys, MCP write, public feedback → files, LAN/VPS HTTPS) is **shipped**. Use this file when product or architecture choices conflict. Prefer it over older README or blueprint asides that imply a full PHP API port. Working scorecard (lab install): repo `gitignore/status-snapshot-updated.md`.

---

## One sentence

PenCMS is an **MIT-licensed, Markdown-and-Git CMS** with a **Python (FastAPI) brain** and a **PHP admin UI**, built so **humans and agents** can edit the same flat-file site — run **locally**, on **LAN HTTPS**, or on a **small VPS / PaaS**, not on $5 shared PHP hosting.

---

## Brand (locked)

| Brand | Domain | Role |
|---|---|---|
| **PenCMS** | [pencms.org](https://pencms.org) | The CMS — public product name for the MIT core |
| **Traven** | [traven.dev](https://traven.dev) | Human-only WYSIWYM Markdown editor (separate product; predates PenCMS) |

---

## Who it is for

| Audience | What they get |
|---|---|
| **Writers / operators** | Several Markdown sites under one install, admin UI, Git-backed content they own |
| **Developers** | Contract-first API (`core/openapi.yaml`), local-first install, Docker Compose / VPS recipe ([`deploy_compose.md`](./deploy_compose.md)) |
| **Agents** | Streamable HTTP MCP (`/api/mcp`), OAuth discovery + named site-bound keys, machine-readable `llms.txt` |

It is **not** primarily for: DreamHost-style shared hosting, WordPress plugin marketplaces, or “sign up and never touch a server” users — unless a future **hosted** offering covers that (see Later).

---

## Differentiator — what open source ought to have

PenCMS exists to fill a gap: **a mutable, Markdown-and-Git CMS where agents are first-class authors and humans remain sponsors of the machine**, without forcing either into a SaaS silo or a chatbot bolted onto an admin form.

### North-star vignette

> On a machine in your house (or a small VPS), one human runs PenCMS. They mint a named agent key and give an agent its own site. The agent posts every day from reader feedback. The human can revoke the key in one click. The files are still theirs in Git.

If that vignette stays true, the product is on course. If a feature fights the vignette, question the feature.

### 1. Agent as first-class author, human as sponsor

Most “AI CMS” products are a human editorial UI plus a chatbot sidebar. PenCMS inverts that without abandoning ownership:

- The **human** owns disk, Git, TLS origin, and key issuance / revocation.
- **Agents** publish through MCP with named, revocable, **site-scoped** keys — not by pasting into the admin. Scopes are granular (`read`, `write:posts`, `write:pages`, `publish`, …); legacy `write` still expands one-way. Agents never inherit the sponsor’s admin role.
- “My agent’s daily blog” is a normal site plus a bound key under one operator, not a demo or a separate product. There is no registry flag “operated by agent X”; the persona is the site id + key name.

Ghost and WordPress bolt AI onto human workflows. Instant-host tools (e.g. here.now) excel at publish-to-URL and agent drives, not at a long-lived Markdown CMS with an OAuth/MCP editing surface. PenCMS owns the gap between them.

### 2. Feedback → write as a protocol, not a chat

An agent that updates a blog from reader feedback needs a **closed loop**, not vibes in a sidebar:

| Stage | Surface |
|---|---|
| **Ingest** | **Shipped.** Contact forms always ingest. **Reader comments are opt-in** (Site Settings toggle, default off). When on: live `/blog/` contact + per-post comment forms `POST /api/v1/feedback`. Contact writes canonical `fb-*` stub pages (`status: stub`) for the admin inbox and relay drain. Comments write `comments/c-*.md` beside the post (`visibility: pending` on public ingest). Live `/blog/` and static `dist/` show **visible** comment files under the article (not pending): `generate-static` / `publish_site` bakes the visible thread into post HTML. Static `dist/` POSTs new comments to `{feedback_relay_url or https://feedback.pencms.org}/submit` (PHP+SQLite queue); the install polls into the same files (`POST /api/v1/feedback/sync` / MCP `sync_remote_feedback`). Public `kind=comment` is refused while the knob is off. Not webmentions, not analytics, not a nested `feedback/` collection. |
| **Decide** | Agent policy (schedule, tools, prompts) **outside** PenCMS — same rule as translation automation. PenCMS does not run the daily loop. |
| **Outgest** | MCP `create_post` / `write_content_file` / `commit_and_push` under a write-capable key; optional static host deploy via `publish_site` under scope `publish` + Deploy Grant ([`publish-agents.md`](./publish-agents.md)) |

Open source has blogs and has agents; almost nobody ships **“scheduled agent editor + readable public feedback surface”** as one coherent product story. Operator pattern (site + key + one MCP URL + ingest): [`agent-owned-site.md`](./agent-owned-site.md). Path-scoped `read` (hide drafts from a feedback-reader key on a *human* site) stays optional polish — a dedicated agent site usually makes monolithic `read` enough.

### 3. Two doors, one source of truth

| Door | Audience | Job |
|---|---|---|
| **PHP admin** | Humans | Structure, keys, themes, storage, consent, Feedback inbox (`fb-*`), Comments admin (comment files) |
| **MCP (`/api/mcp`)** | Agents | Read/write content at agent speed |

Same Markdown + YAML files. No second database of “AI drafts.” Content outlives any particular model or client. That continuity is both the technical and the moral product.

### 4. Sovereign agent hosting without SaaS

LAN HTTPS ([`lan_https.md`](./lan_https.md)) and VPS recipes mean: you can give an agent a **stable home** without renting a CMS company. SilverBullet-style LAN+TLS taught people to host notes at home; PenCMS claims the same cultural niche for **agent-operated sites** — localhost for same-machine work, HTTPS on the LAN or a small server when OAuth and remote connectors need a real origin. Native LAN (nginx + systemd) is the home/lab path; Compose+Caddy is the VPS path and does **not** yet run PHP. Third-party MCP clients (Cursor, Antigravity, other harnesses) already talk Streamable HTTP to a LAN HTTPS origin — not only operator curl.

### 5. What we deliberately do not chase

- Becoming “the AI WordPress” feature farm  
- A PHP API for $5 shared hosting as the core (see Never)  
- Multi-tenant SaaS (single-operator multisite is already the model)  
- Agents that hold the human root password instead of scoped keys  
- A second MCP catalog or hand-rolled transport that forks the file model  

### Design test

Before adding a capability, ask:

1. Can a **named agent key** exercise it without the human sitting in the admin?
2. Do the **files on disk / in Git** remain the source of truth afterward?
3. Can the human **revoke** that agent’s reach in one place?
4. Does it still work on **self-hosted HTTPS** (LAN or VPS), not only a hypothetical cloud?

If the answer to any is no, it is probably not PenCMS — or it belongs in Later/SaaS, not the MIT core.

---

## What “done” means for v1 OSS (Now)

Locked and shipped:

1. **Single operator, multisite-capable** — one PenCMS install can host many sites under `content/sites/{id}/` with a registry at `data/sites.yaml`. Fresh installs migrate the former flat content tree into `sites/default/`.
2. **Python backend is the CMS** — auth, storage adapters, FTS cache, AI proxy, MCP, colocated OAuth AS, site registry.
3. **PHP is the human admin / reference frontend** — not a second API implementation.
4. **Agent door open** — PRM / AS metadata / PKCE; automation via `POST /api/auth/token`; granular scopes (`read`, `write:*`, `publish:content`, host `publish`; legacy `write` expands one-way); discovery via `llms.txt` / MCP guide. **Named, site-bound agent keys** (e.g. `blog-cursor`) and **approve-code bootstrap** (`/api/auth/agent/request-code` → admin approve → `verify-code` → store `pen-sk-…`) are shipped; OAuth remains primary for Custom Connectors. Streamable HTTP session DX that third-party clients need is shipped (`Mcp-Session-Id`, `initialize` `sessionId`, `Accept` compat). **One install-wide** `MCP_RESOURCE_URL` / JWT `aud`; site isolation is via key + JWT `site_id`, not per-site OAuth resources.
5. **Production URL honesty** — operators set `JWT_ISSUER` and `MCP_RESOURCE_URL` to the **HTTPS** URLs clients actually use. Localhost is for local agents and curl. For Custom Connectors and browser OAuth, use a reachable HTTPS origin: **LAN home server** (documented and field-tested with off-box agents), VPS/PaaS, or tunnel — not bare `http://127.0.0.1` for off-machine clients.
6. **Packaging** — local run + **LAN HTTPS** native nginx+systemd ([`lan_https.md`](./lan_https.md)) + one clear cloud/VPS path: **Docker Compose + Caddy** ([`deploy_compose.md`](./deploy_compose.md)). CORS allowlist for admin origins. Same image can target Fly/Render later; Compose is the shipped VPS installer glue (API+Caddy; PHP admin is the native/LAN path until Compose grows it).
7. **Feedback → files** — public contact forms write `fb-*` stubs on the bound site. **Reader comments are opt-in** (default off; one Site Settings toggle). When on, comments write `comments/c-*.md` beside the post; static sites drain `https://feedback.pencms.org` (or a self-hosted same-contract queue) via poll/MCP. Human admin inbox lists contact stubs. Public comment threads are **files beside the post** (no commenter accounts); live `/blog/` and static `dist/` show `visibility: visible` only. Human admin can approve / hide / delete comment files (Comments admin); the Feedback inbox remains `fb-*` contact stubs. Agents reply via MCP `create_comment` (immediately `visibility: visible`, `author_kind: agent`) — they must not `create_post` for a thread reply. CAPTCHA stays later. Keep no nested `feedback/` collection and no comments-as-WordPress.

**OSS license:** MIT for the core. Content and operator data stay on the user’s disk / Git.

---

## Next (approved polish)

**Multisite product track is closed.** **Feedback ingest v0+v1 is closed.** Remaining items are optional polish or icebox:

- **Path-scoped `read` only if needed** — split `read` only when a human site must hide drafts from a feedback-reader key. A dedicated agent site makes monolithic `read` enough.
- Still **no** per-site `MCP_RESOURCE_URL` / `aud` unless demand forces an additive escape hatch.
- Deferred / icebox (low priority — not soon unless an operator is blocked): per-site `web_root` / CDN. Install-wide `[theme] web_root` / `cdn_base` remain; Host + static `dist/{id}/` cover the common case.
- Do **not** reopen MCP Streamable HTTP glue unless a named third-party client is blocked.

Do **not** invent multi-tenant isolation, billing, or “one account = one site” artificial limits. Do **not** reopen multisite topology unless fixing a regression. Do **not** invent a Session 8 of feedback ingest (no nested `feedback/` collection, no comments-as-WordPress).

---

## Later (optional / maybe)

**Hosted PenCMS** — WordPress.com / Ghost(Pro) model:

- MIT core remains self-hostable.
- A **proprietary** hosted shell can sell managed TLS, backups, stable HTTPS URLs for agents, and a polished multi-site UI.
- That path implies multi-tenant ops; build it only when self-host install is boring and demand is real.

Until then: do not reshape JWT/`aud`, storage, or MCP for hypothetical SaaS tenancy.

---

## Never (core product)

**A full PHP API aimed at $5 shared hosting (cPanel / Apache-only) as the main PenCMS.**

Reasons locked in:

- MCP OAuth, Streamable HTTP, FTS workers, AI features, and flexible storage settings do not fit that environment without gutting the product.
- Maintaining two backends is a permanent tax; Python is the obvious fit for what PenCMS already is.

### Seduction, acknowledged

Many of us started on cheap shared hosts. “Anyone can run it anywhere” feels like a calling. That calling still matters — but for PenCMS it means **simple VPS/PaaS + local**, not pretending FastAPI features run under PHP-FPM on DreamHost.

### Possible future fork (not the core)

If the DreamHost crowd ever truly wants PenCMS, a **separate, pared-down, all-PHP** distribution may be considered:

- No AI, no MCP, no OAuth AS.
- No rich storage settings UI (unlike today’s `admin-settings-storage.php` flexibility).
- Flat files + minimal admin only.

That would be a **sibling product / fork**, not a second implementation of this repo’s API. It must not drive design of the Python core.

---

## Core / Pro editions (decision record)

**Core** is a standalone MIT engine. **Pro** is a private overlay
(`pencms_pro`) that registers extra routers, adapters, and admin views via
hooks. Core never contains Pro source. Pro never forks Core files. Edition
is overlay presence (`import pencms_pro` succeeded), not a config.ini flag.
How to load the overlay: [`editions.md`](./editions.md).

### Anti-crippleware

1. Core is a complete CMS: an operator can build, style, translate, and
   publish a real site (fork the starter theme, write, publish via SFTP or
   GitHub Pages) with zero Pro code.
2. No feature flags re-enabling Pro inside the MIT tree. Absence is
   structural (files gone, endpoints unmounted).
3. Core's agent door is the product's identity. Never trade it for tiering.

### Core (MIT)

| # | Feature |
|---|---|
| C1 | Single-site engine (`default`). `GET` + `PATCH /api/sites/{id}` stay (site settings, not the network SKU). |
| C2 | Single bootstrap operator. No `/api/users` CRUD. |
| C3 | ZK Vault (AI BYOK, agent keys, SFTP password, GitHub token). Pro adds more header mappings via hook. |
| C4 | Local + Git storage. SSH as a *content/assets type* is Pro. SSH *transport* for SFTP publish stays Core. |
| C5 | Static export (`dist/`, `.zip`). |
| C6 | SFTP deploy (password via vault; key via install Ed25519). |
| C7 | GitHub Pages deploy. |
| C8 | Publish webhooks (HMAC), provider-independent. |
| C9 | Raw MCP `/api/mcp` + OAuth AS. |
| C10 | AI proxy + Deploy Grants. |
| C11 | i18n translation engine. |
| C12 | Dynamic OG images + `POST /api/sites/{id}/og-preview`. |
| C13 | Feedback relay (`feedback.pencms.org`). |
| C14 | Starter theme + CSS design tokens. Zip/URL install, Theme Settings export, `package-zip`. |
| C15 | Theme fork + code editor (`admin-customize.php`) + MCP inspect/customize (AI rail). |

### Pro (overlay)

| # | Feature |
|---|---|
| P1 | Multisite network CRUD (create/rename/move-content/delete) + header switcher. |
| P2 | Multi-user ACL UI (`/api/users`, `admin-users.php`). |
| P3 | SSH as content/assets storage type. |
| P4 | Cloud deployers: Cloudflare Pages, Vercel, Netlify, here.now. |

S3/R2 is not allocated until a provider exists. `routers/sites.py` is split
by endpoint, not moved wholesale. SFTP publish uses Core `services/ssh_client`;
`SSHStorageProvider` as a content/assets storage *type* is Pro.

---

## Architectural north stars (for future PRs)

1. **Flat Markdown + YAML (+ Git) remain the source of truth.** Tools come and go; files stay.
2. **One MCP tool catalog** — FastApiMCP / Streamable HTTP; no second hand-rolled session router; no stdio-first rewrite of the catalog.
3. **Agent keys + OAuth wrap the same scopes** (granular `read` / `write:*` / `publish`; legacy `write` is an alias). Do not replace keys with OAuth-only.
4. **Colocated AS in Python** — no mandatory external IdP; no DCR required for first clients.
5. **Multisite before multi-tenant** — one install-wide MCP `aud`; site-scoped keys and content paths first.
6. **Issuer URLs are operator config** — do not special-case cloud connectors with fake localhost issuers; document LAN HTTPS, tunnel, or VPS instead ([`lan_https.md`](./lan_https.md)).
7. **Discovery stays thin** — `llms.txt` / skill stubs defer to live `mcp_guide.md` when they disagree.

---

## Sequence (do not reorder lightly)

```text
Now:   MIT Python core · local + LAN HTTPS + Compose/VPS · agent MCP/OAuth · named site-bound keys + approve-code · granular scopes · **multisite track DONE** · **feedback ingest v0+v1 DONE** (live POST + feedback.pencms.org poll + static bake + admin inbox) · third-party MCP clients on LAN HTTPS
Next:  path-scoped `read` only if a human site must hide drafts; otherwise icebox
Later: Optional hosted SaaS (proprietary ops on MIT core)
Icebox: Per-site web_root·CDN · per-site MCP aud (low priority; reopen only if an operator is blocked)
Never: PHP API as the primary / shared-host PenCMS
Maybe: Separate all-PHP lite fork if demand appears
```
---

## Related docs

- Operator / agent surface: [`mcp_guide.md`](./mcp_guide.md), [`agent-owned-site.md`](./agent-owned-site.md) (incl. feedback → write), [`users-and-access.md`](./users-and-access.md), [`llms.txt`](./llms.txt), [`mcp_skill.md`](./mcp_skill.md), [`zero-to-hero-skill.md`](./zero-to-hero-skill.md)
- Publish to host (human + agent hybrid): [`publish-howto.md`](./publish-howto.md), [`publish-agents.md`](./publish-agents.md)
- Deploy: [`deploy_compose.md`](./deploy_compose.md), [`lan_https.md`](./lan_https.md)
- Editions: [`editions.md`](./editions.md) (Core MIT vs Pro overlay)
- Local planning (not GitHub): `gitignore/status-snapshot-updated.md`, `gitignore/feedback_ingest_v0_implementation_plan.md`
- Contract: [`../openapi.yaml`](../openapi.yaml)
