<p align="center">
  <img src="frontend-php/src/admin/images/pencms-512x512.png" alt="PenCMS" width="200">
</p>

# PenCMS

**Many agents via keys. One operator.**

PenCMS is an Agent-First and API-first MIT-licensed **Markdown-and-Git CMS**: a Python (FastAPI) brain and a PHP admin, so humans and agents edit the **same** files. You sponsor the machine — disk, Git, TLS, and revocable keys. Agents publish through MCP.

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/slpstream/pencms)

---

## Key Principles
1. **Contract-First**: Every backend endpoint, schema, and validation rule is defined in a hand-written OpenAPI specification (`core/openapi.yaml`).
2. **Flat-File Source of Truth**: All pages, posts, and entries are stored as clean Markdown + YAML files. No second database of “AI drafts.”
3. **Two doors**: PHP admin for humans (structure, keys, themes, storage); MCP (`/api/mcp`) for agents (read/write at agent speed).
4. **High-Performance Query Cache**: Reads use a local SQLite index on write, so the CMS stays responsive on small machines.
5. **Shell-Free Git Syncing**: Remote repos (GitHub/GitLab) via HTTPS REST APIs when a shell is restricted.
6. **Selfhosting**: Run locally, on LAN HTTPS, or a small VPS.

---

## Repository Structure

```
pencms/
├── core/                   # Contract & Specifications
│   ├── openapi.yaml        # API Spec (Source of Truth)
│   ├── schemas/            # Document Schemas
│   └── docs/               # Guides (incl. mcp_guide.md)
│
├── backend-python/         # FastAPI CMS + MCP + OAuth (the product brain)
│
└── frontend-php/           # Admin UI client (Traven Editor integration)
```

---

## Run / Deploy

| Path | Doc |
|---|---|
| **VPS / public HTTPS (recommended)** | Docker Compose + Caddy — [`core/docs/deploy_compose.md`](core/docs/deploy_compose.md) (`deploy/`) |
| **LAN home server** | mkcert + reverse proxy — [`core/docs/lan_https.md`](core/docs/lan_https.md) |
| **An agent’s own site** | [`core/docs/agent-owned-site.md`](core/docs/agent-owned-site.md) |
| **Agents / MCP / OAuth** | [`core/docs/mcp_guide.md`](core/docs/mcp_guide.md) |
| **Users + agent keys** | [`core/docs/users-and-access.md`](core/docs/users-and-access.md) |

Quick Compose:

```bash
cd deploy
cp .env.example .env   # set PUBLIC_HOST, JWT_SECRET, JWT_ISSUER, MCP_RESOURCE_URL, CORS_ALLOW_ORIGINS
docker compose up -d --build
```

---

## License

Open-source, licensed under the [MIT License](LICENSE).
