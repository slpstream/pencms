<p align="center">
  <img src="frontend-php/src/admin/images/pencms-512x512.png" alt="PenCMS" width="200">
</p>

# PenCMS

PenCMS is the world's first-ever AI-native CMS made from the ground up for the age of agents: An Agent-first, API-first, Markdown-centric headless Content Management System anyone can self-host, complete with a built-in MCP server. 


**Many agents via keys. One operator.**

PenCMS is an Agent-First and API-first MIT-licensed **Markdown-and-Git CMS**: a Python (FastAPI) brain and a PHP admin, so humans and agents edit the **same** files. You sponsor the machine — disk, Git, TLS, and revocable keys. Agents publish through MCP.

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/slpstream/pencms)

> 🚀 **Self-Hosting PenCMS?** Follow our step-by-step **[ELI5 Quickstart Guide](core/docs/quickstart.md)** to get the Python Brain and PHP Face running on your machine in 5 minutes!

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
│   └── docs/               # Guides (incl. quickstart.md, mcp_guide.md)
│
├── backend-python/         # FastAPI CMS + MCP + OAuth (the product brain)
│
└── frontend-php/           # Admin UI client (Traven Editor integration)
```

---

## Run / Deploy

| Path | Doc |
|---|---|
| **Self-hosting on your own hardware (ELI5 Quickstart)** | Step-by-step beginner guide — [`core/docs/quickstart.md`](core/docs/quickstart.md) |
| **VPS / public HTTPS** | Docker Compose + Caddy — [`core/docs/deploy_compose.md`](core/docs/deploy_compose.md) (`deploy/`) |
| **LAN home server** | mkcert + reverse proxy — [`core/docs/lan_https.md`](core/docs/lan_https.md) |
| **An agent’s own site** | [`core/docs/agent-owned-site.md`](core/docs/agent-owned-site.md) |
| **Agents / MCP / OAuth** | [`core/docs/mcp_guide.md`](core/docs/mcp_guide.md) |
| **Users + agent keys** | [`core/docs/users-and-access.md`](core/docs/users-and-access.md) |

### 🚀 2-Minute Local Quickstart (Laptop / Desktop)

PenCMS runs as two coordinated engines—the **Python Brain** (API & storage on `:8008`) and the **PHP Face** (Admin UI & Blog on `:8009`).

1. **Start the Brain** (Terminal 1):
   ```bash
   cd backend-python
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   uvicorn app.main:app --reload --port 8008
   ```

2. **Start the Face** (Terminal 2):
   ```bash
   cd frontend-php
   PHP_CLI_SERVER_WORKERS=8 php -c php.ini -S 127.0.0.1:8009 -t public router.php
   ```

3. **Initialize & Explore**:
   - Create your admin account: **[http://127.0.0.1:8009/admin/setup.php](http://127.0.0.1:8009/admin/setup.php)**
   - Admin Dashboard: **[http://127.0.0.1:8009/admin/](http://127.0.0.1:8009/admin/)**
   - Public Blog: **[http://127.0.0.1:8009/blog/](http://127.0.0.1:8009/blog/)**

👉 *For full step-by-step guidance, home server setup, and troubleshooting, read the **[ELI5 Quickstart Guide](core/docs/quickstart.md)**.*

---

### 🐳 Docker Compose (VPS / Public HTTPS)

For cloud VPS deployments with automatic Let's Encrypt TLS:

```bash
cd deploy
cp .env.example .env   # set PUBLIC_HOST, JWT_SECRET, JWT_ISSUER, MCP_RESOURCE_URL, CORS_ALLOW_ORIGINS
docker compose up -d --build
```
See [`core/docs/deploy_compose.md`](core/docs/deploy_compose.md) for full VPS configuration and reverse proxy details.

---

## License

Open-source, licensed under the [MIT License](LICENSE).
