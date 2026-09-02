# PenCMS product thesis

**Status:** The north-star loop (named site-bound keys, MCP write, public feedback → files, LAN/VPS HTTPS) is **shipped**. 

---

## One sentence

PenCMS is an **MIT-licensed, Markdown-and-Git CMS** with a **Python (FastAPI) brain** and a **PHP admin UI**, built so **humans and agents** can edit the same flat-file site — run **locally**, on **LAN HTTPS**, or on a **small VPS / PaaS**.

---

## Brand 

| Brand | Domain | Role |
|---|---|---|
| **PenCMS** | [pencms.org](https://pencms.org) | Agent-and-human MIT-licensed content management system (used Traven as its editor) |
| **Traven** | [traven.dev](https://traven.dev) | Human-only WYSIWYM Markdown editor (separate product; from same developers as PenCMS) |

---

## Who it is for

| Audience | What they get |
|---|---|
| **Writers / operators** | Several Markdown sites under one install, admin UI, Git-backed content they own |
| **Developers** | Contract-first API (`core/openapi.yaml`), local-first install, Docker Compose / VPS recipe ([`deploy_compose.md`](./deploy_compose.md)) |
| **Agents** | Streamable HTTP MCP (`/api/mcp`), OAuth discovery + named site-bound keys, machine-readable `llms.txt` |

---

## Differentiator — open source Agent-First CMS

PenCMS exists to fill a gap: **a mutable, Markdown-and-Git CMS where agents are first-class authors and humans remain sponsors of the machine**, without forcing either into a SaaS silo or a chatbot bolted onto an admin form.

The niche that PenCMS occupies is for a flat-file, Git-native CMS with a dual-audience design — human admin via PHP, and a genuinely first-class MCP gateway so AI agents can author content autonomously under scoped, revocable keys, while the human sponsor retains ultimate ownership of the files and can revoke or take over at any time. The "sovereign agent" position (selfhosted infrastructure, human-owned files, an agent working within a leash the human controls) set PenCMS apart from "yet another headless CMS," and is specifically betting on a workflow that's only becoming relevant *now* (2026/2027).

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

### Design test

Before adding a capability, ask:

1. Can a **named agent key** exercise it without the human sitting in the admin?
2. Do the **files on disk / in Git** remain the source of truth afterward?
3. Can the human **revoke** that agent’s reach in one place?
4. Does it still work on **self-hosted HTTPS** (LAN or VPS), not only a hypothetical cloud?

If the answer to any is no, it is probably not PenCMS — or it belongs in fork/later/SaaS, not the MIT core.

---

## Locked and shipped:

1. **Python backend is the CMS** — auth, storage adapters, FTS cache, AI proxy, MCP, colocated OAuth AS, site registry.
2. **PHP is the human admin / reference frontend** — not a second API implementation.
3. **Agent door open** — PRM / AS metadata / PKCE; automation via `POST /api/auth/token`; granular scopes (`read`, `write:*`, `publish:content`, host `publish`; legacy `write` expands one-way); discovery via `llms.txt` / MCP guide. **Named, site-bound agent keys** (e.g. `blog-cursor`) and **approve-code bootstrap** (`/api/auth/agent/request-code` → admin approve → `verify-code` → store `pen-sk-…`) are shipped; OAuth remains primary for Custom Connectors. Streamable HTTP session DX that third-party clients need is shipped (`Mcp-Session-Id`, `initialize` `sessionId`, `Accept` compat). **One install-wide** `MCP_RESOURCE_URL` / JWT `aud`; site isolation is via key + JWT `site_id`, not per-site OAuth resources.
4. **Production URL honesty** — operators set `JWT_ISSUER` and `MCP_RESOURCE_URL` to the **HTTPS** URLs clients actually use. Localhost is for local agents and curl. For Custom Connectors and browser OAuth, use a reachable HTTPS origin: **LAN home server** (documented and field-tested with off-box agents), VPS/PaaS, or tunnel — not bare `http://127.0.0.1` for off-machine clients.
5. **Packaging** — local run + **LAN HTTPS** native nginx+systemd ([`lan_https.md`](./lan_https.md)) + one clear cloud/VPS path: **Docker Compose + Caddy** ([`deploy_compose.md`](./deploy_compose.md)). CORS allowlist for admin origins. Same image can target Fly/Render later; Compose is the shipped VPS installer glue (API+Caddy; PHP admin is the native/LAN path until Compose grows it).
6. **Feedback → files** — public contact forms write `fb-*` stubs on the bound site. **Reader comments are opt-in** (default off; one Site Settings toggle). When on, comments write `comments/c-*.md` beside the post; static sites drain `https://feedback.pencms.org` (or a self-hosted same-contract queue) via poll/MCP. Human admin inbox lists contact stubs. Public comment threads are **files beside the post** (no commenter accounts); live `/blog/` and static `dist/` show `visibility: visible` only. Human admin can approve / hide / delete comment files (Comments admin); the Feedback inbox remains `fb-*` contact stubs. Agents reply via MCP `create_comment` (immediately `visibility: visible`, `author_kind: agent`) — they must not `create_post` for a thread reply. CAPTCHA stays later. Keep no nested `feedback/` collection and no comments-as-WordPress.

**OSS license:** MIT. Content and operator data stay on the user’s disk / Git.

---

## Fully Featured Open-Source CMS

PenCMS is a complete, self-contained system. Operators can create, design, translate, and publish production websites — writing with live WYSIWYM previews, customizing Twig themes, automating workflows over MCP, and publishing statically via SFTP or GitHub Pages — with zero external proprietary dependencies. The agent door is first-class and central to the product's identity.

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

## Related docs

- Operator / agent surface: [`mcp_guide.md`](./mcp_guide.md), [`agent-owned-site.md`](./agent-owned-site.md) (incl. feedback → write), [`users-and-access.md`](./users-and-access.md), [`llms.txt`](./llms.txt), [`mcp_skill.md`](./mcp_skill.md), [`zero-to-hero-skill.md`](./zero-to-hero-skill.md)
- Publish to host (human + agent hybrid): [`publish-howto.md`](./publish-howto.md), [`publish-agents.md`](./publish-agents.md)
- Deploy: [`deploy_compose.md`](./deploy_compose.md), [`lan_https.md`](./lan_https.md)
- Contract: [`../openapi.yaml`](../openapi.yaml)


