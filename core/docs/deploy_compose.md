# Deploy PenCMS with Docker Compose

One clear **VPS / public HTTPS** path for the PenCMS FastAPI brain: Compose runs **API + Caddy (TLS)**. The PHP admin stays on the host (or behind Caddy once you extend the Caddyfile).

LAN-only installs without Docker: [`lan_https.md`](./lan_https.md). MCP operator detail: [`mcp_guide.md`](./mcp_guide.md).

## What you get

```text
Internet / agents
        |  https://$PUBLIC_HOST
        v
[ Caddy ]  ← TLS (Let's Encrypt on public DNS; internal CA on localhost)
        |
        +--> /api, /.well-known, /oauth, /llms.txt  →  FastAPI (:8008)
        +--> / (optional)                          →  PHP admin (you wire this)
```

Compose also publishes **host port 8008** so same-machine `php -S` / curl can hit the API over HTTP without Caddy.

## Prerequisites

- Docker Engine + Compose v2
- A DNS name pointing at the VPS (for public TLS), **or** `localhost` for a local smoke
- For the human admin UI: PHP CLI on the host (see below)

## Quick start

```bash
cd deploy
cp .env.example .env
# Edit PUBLIC_HOST, JWT_SECRET, JWT_ISSUER, MCP_RESOURCE_URL, CORS_ALLOW_ORIGINS
docker compose up -d --build
```

Env checklist (all must agree on scheme + host):

| Variable | Example | Notes |
|---|---|---|
| `PUBLIC_HOST` | `cms.example.com` | Hostname only (no `https://`); Caddy site address |
| `JWT_SECRET` | long random string | **Required** in production; signs agent JWTs |
| `JWT_ISSUER` | `https://cms.example.com` | No trailing slash; OAuth AS issuer |
| `MCP_RESOURCE_URL` | `https://cms.example.com/api/mcp` | JWT `aud` / PRM `resource`; path exact |
| `CORS_ALLOW_ORIGINS` | `https://cms.example.com` | Comma-separated admin origins |
| `AGENT_TOKEN_EXPIRE_MINUTES` | `15` | Optional |
| `PENCMS_RATE_LIMIT_MCP` | on (unset) | Agent MCP loop-guard. Set `0` to disable. Not a Caddy replacement |
| `PENCMS_RATE_LIMIT_MCP_PER_MIN` | `120` | Sliding-window ceiling per agent key |
| `PENCMS_API_TARGET` | `api` (default) or `inspect` | Dockerfile target. Slim API vs in-process Chromium for Customize inspect |
| `PENCMS_PREVIEW_BASE_URL` | `http://host.docker.internal:8009` | PHP origin **from the API container**. Required for inspect. Never the API port |

Content and assets live in Docker volumes (`pencms_content`, `pencms_assets`). OAuth SQLite + FTS cache use `pencms_runtime`.

### Multisite content layout

The `pencms_content` volume is the whole content tree. On first API start, any former flat layout is migrated into `sites/default/` inside that volume (on disk: `content/sites/{id}/`). Site menus (`menus.yaml`), taxonomy/collections seeds, and media (`assets/…`) also live under each site dir; install-wide `menus.json` / flat `assets/` are migrated into `default` once. You do **not** remount per site — one volume covers all sites. Manage the registry in PHP **Settings → Sites** (create, soft-edit name/domain/branding/theme, hard-rename id, delete, move content), or via `/api/sites`. Deleted sites are tombstoned under `content/_deleted/{id}-{timestamp}/` on the same volume (recoverable from disk/Git; not hard-purged). Agent keys bind to one site and can be reassigned without reminting; there is still **one** MCP connector URL (`MCP_RESOURCE_URL`) for the install.

### Multi-hostname public sites

PenCMS picks the public site from the request **Host** header by matching the site registry `domain` field (unique across sites; miss → `default`). Point multiple hostnames at the **same** PenCMS origin (same Compose stack / Caddy upstream); do not run a separate install per site.

Example Caddy site block (same reverse_proxy targets as your primary host):

```caddy
wiki.example.com, blog.example.com {
    # same handlers as $PUBLIC_HOST — API + PHP public front
    reverse_proxy /api* pencms-api:8000
    reverse_proxy /* php-upstream:8009
}
```

Then set each site’s **Domain** in **Settings → Sites** to `wiki.example.com` / `blog.example.com`. Install-wide `config.ini` `[General]` / `[theme]` remain the fallback when a site leaves branding or theme unset. MCP `MCP_RESOURCE_URL` / JWT `aud` stay install-wide (not per hostname).

### Static export (per site)

Dynamic public uses Host → registry. Static trees are an export of the same site content:

```bash
# Export static production bundle for a site (default site if --site omitted)
php frontend-php/cli-tools/generate-static.php --site=wiki --domain=wiki.example.com --output=dist
```

Canonical links prefer `--domain`, else each site’s registry `domain`, else localhost. Per-site `web_root` / CDN configuration is not required; operators publish or sync each `dist/{id}/` tree as needed.

### Scheduled posts and static rebuild

Posts with `status: published` and a future `publish_at` stay out of public listings until that time (PHP preview filters by clock; no status flip). Static `dist/` trees only pick them up on the next export.

If you host static trees and want auto go-live without a manual Export, cron `rebuild-due.php` (requires the API running):

```bash
# Dry-run: list sites with publish_at due in the last 6 hours
php frontend-php/cli-tools/rebuild-due.php --dry-run --hours=6

# Cron every 5 minutes (rebuild only sites that have recently due posts)
*/5 * * * * cd /path/to/pencms/frontend-php/cli-tools && php rebuild-due.php --hours=6 >> /var/log/pencms-rebuild-due.log 2>&1
```

Skip this if you only use PHP preview.

### Local smoke (no public DNS)

```bash
# In deploy/.env
PUBLIC_HOST=localhost
JWT_ISSUER=https://localhost
MCP_RESOURCE_URL=https://localhost/api/mcp
CORS_ALLOW_ORIGINS=https://localhost,http://127.0.0.1:8009
JWT_SECRET=dev-only-change-me
```

Then `docker compose up -d --build`. Caddy serves `https://localhost` with an internal certificate. For raw HTTP API checks: `http://127.0.0.1:8008` (set issuer/resource to that origin **only** if clients use that origin).

## PHP admin notes

The Compose file does **not** run PHP. Two common shapes:

### Same machine (dev / small VPS)

Loopback defaults (same on a laptop and behind LAN nginx): API **8008**, PHP **8009**.

1. API published on host `8008` (Compose default).
2. From the repo:

   ```bash
   cd frontend-php
   php -c php.ini -S 0.0.0.0:8009 router.php
   # Or explicitly pass upload size flags:
   # php -d upload_max_filesize=10M -d post_max_size=12M -S 0.0.0.0:8009 router.php
   ```

3. `router.php` proxies `/api/*` to `http://127.0.0.1:8008`.
4. Add `http://127.0.0.1:8009` (and/or `http://localhost:8009`) to `CORS_ALLOW_ORIGINS` if the browser talks to the API origin directly. Same-origin via the PHP proxy does not need CORS.

### Production: terminate everything on Caddy

Extend [`deploy/Caddyfile`](../../deploy/Caddyfile) so `/` (and admin paths) reverse-proxy to your PHP upstream, while keeping `/api*`, `/.well-known*`, `/oauth*`, and `/llms.txt` on FastAPI — same split as [`lan_https.md`](./lan_https.md).

Set `CORS_ALLOW_ORIGINS` to `https://$PUBLIC_HOST` when admin and API share that origin.

## Customize inspect (Chromium)

Inspect tools (`describe_element`, screenshot, …) need **headless Chromium in the FastAPI process** and a preview origin the API can GET `/blog/` from. PHP is still not in Compose. There is **no** Playwright sidecar.

**Docker (opt-in fat image):**

```bash
# deploy/.env
PENCMS_API_TARGET=inspect
PENCMS_PREVIEW_BASE_URL=http://host.docker.internal:8009
```

Then `docker compose up -d --build`. Default `PENCMS_API_TARGET=api` stays slim (library only, no browser). Compose already adds `host.docker.internal:host-gateway` so the API container can reach PHP on the host. Use the PHP port the **container** can hit (`8009`), never API `8008`.

**Host API (LAN / VPS, no Docker):**

```bash
pip install playwright && playwright install --only-shell
export PENCMS_PREVIEW_BASE_URL=http://127.0.0.1:8009   # or LAN IP / public origin
```

Unset or unreachable preview returns `PREVIEW_UNREACHABLE`, not a 500. Missing Chromium returns `BROWSER_UNAVAILABLE`. Operator detail: [`mcp_guide.md`](./mcp_guide.md) (Theme Customize).

## First agent key → connector or curl

Against this recipe (replace the host with your `PUBLIC_HOST`):

1. **Admin** — open the PHP admin (once wired). Optionally create sites under **Settings → Sites**. Then **Settings → AI → Agent Keys**: create a key with **Name + Site + Scope** (prefer `{site}-{agent}`, e.g. `blog-cursor`; scopes `read` or `read+write`). Copy the `pen-sk-…` secret once.
2. **Custom Connector (Cursor / Claude)** — MCP URL (**one per install**, not per site):

   `https://$PUBLIC_HOST/api/mcp`

   Must match `MCP_RESOURCE_URL`. Complete OAuth; at consent, pick the agent key (label shows `site · name`). Site isolation is the key’s `site_id`, not a second connector URL.
3. **Automation (scripts / CI)** — no browser:

   ```bash
   curl -sS -X POST "https://$PUBLIC_HOST/api/auth/token" \
     -H "Content-Type: application/json" \
     -d '{"agent_key":"pen-sk-your-copied-key"}'
   ```

   Use `Authorization: Bearer <access_token>` on later `/api/mcp` calls. The JWT includes `site_id`.

Full discovery / consent detail and smoke checklist (including cross-site denial): [`mcp_guide.md`](./mcp_guide.md).

### Minimal API smoke (no connector)

```bash
# Expect 401 + WWW-Authenticate with resource_metadata
curl -sS -D - -o /dev/null "https://$PUBLIC_HOST/api/mcp"

curl -sS "https://$PUBLIC_HOST/.well-known/oauth-protected-resource" | jq .
curl -sS "https://$PUBLIC_HOST/.well-known/oauth-authorization-server" | jq .
```

Confirm `resource` / `issuer` match `MCP_RESOURCE_URL` / `JWT_ISSUER` in `.env`.

## Alternative: Cloud & PaaS Platforms (Fly.io, Render)

While this guide focuses on self-hosting with Docker Compose and Caddy, the API container ([`deploy/Dockerfile`](../../deploy/Dockerfile)) can also be deployed to container-based cloud platforms like Fly.io or Render:

- **Environment Variables**: Configure the required `JWT_*` and `CORS_*` settings in your platform's environment dashboard.
- **TLS Termination**: You can allow the cloud provider to terminate TLS at the edge or continue using Caddy as a reverse proxy.
- **Deployment**: Standard container builds run directly from `deploy/Dockerfile` without requiring custom platform-specific configuration files.

## Related

- Product direction: [`product_thesis.md`](./product_thesis.md)
- LAN HTTPS (mkcert, no Docker): [`lan_https.md`](./lan_https.md)
- MCP guide: [`mcp_guide.md`](./mcp_guide.md)
