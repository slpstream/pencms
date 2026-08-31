# LAN HTTPS for PenCMS (home / lab server)

PenCMS works on `http://localhost` for local curl and same-machine agents. **Stock Custom Connectors and browser OAuth consent** expect a stable **HTTPS** origin whose scheme/host match `JWT_ISSUER` and `MCP_RESOURCE_URL`.

You do not need a public cloud for that. A common pattern (same idea as SilverBullet’s LAN install): run PenCMS on a **machine on your LAN**, terminate TLS at a reverse proxy, and point clients at that HTTPS URL.

## Recommended shape

```text
[ Laptop / phone / agent ]
        |  https://pencms.lan  (or https://192.168.x.x)
        v
[ Reverse proxy: Caddy / Nginx / Apache ]  ← TLS + optional HSTS
        |
        +--> PHP admin (frontend, loopback :8009)
        +--> FastAPI backend (loopback :8008)
```

## Steps (outline)

1. **Pick a hostname** clients will use, e.g. `pencms.lan` or a fixed LAN IP. Put it in `/etc/hosts` (or your router DNS) on every client that needs the admin UI or OAuth redirect.
2. **Issue a locally trusted cert** with [`mkcert`](https://github.com/FiloSottile/mkcert) (or your own CA):

   ```bash
   mkcert -install
   mkcert pencms.lan 192.168.1.50
   ```

   Point the reverse proxy at the generated `.pem` / `-key.pem`.
3. **Proxy** `/` (or admin paths) to the PHP frontend and `/api`, `/.well-known`, `/oauth`, `/llms.txt` to the Python backend (or proxy everything to PHP’s `router.php` if it already forwards `/api/*`).
4. **Set env on the backend** to the **same** HTTPS origin clients type in the browser:

   ```bash
   export JWT_ISSUER=https://pencms.lan
   export MCP_RESOURCE_URL=https://pencms.lan/api/mcp
   export CORS_ALLOW_ORIGINS=https://pencms.lan
   ```

   Scheme and host must match exactly (no `http://` leftovers, no trailing slash on issuer).
5. **Smoke:** open `https://pencms.lan`, complete OAuth consent once, then point Cursor/Claude at `https://pencms.lan/api/mcp`.

## Nginx + systemd (native LAN)

**Prefer this on a home/lab box that already has nginx and PHP.** Docker Compose ([`deploy_compose.md`](./deploy_compose.md)) is the VPS/public-HTTPS path; it does not yet run PHP and would fight an existing nginx on :80/:443.

Drop-in files live in [`deploy/lan/`](../../deploy/lan/):

| File | Role |
|---|---|
| `nginx-pencms.conf` | TLS terminator; `/api`, `/.well-known`, `/oauth`, `/llms.txt` → FastAPI `:8008`; `/fonts/`, `/assets/vendor/`, `/assets/fonts/`, `/admin/css/` → disk; `/admin/js/` Core-on-disk then PHP (`PENCMS_PRO_ADMIN`); everything else `/` → PHP `:8009` |
| `pencms-api.service` | uvicorn on `127.0.0.1:8008` (`--reload` for git-pull/edit LAN boxes; omit on a hands-off VPS). **`--reload` drops in-memory MCP sessions** — echo a fresh `Mcp-Session-Id` after the API restarts, or omit `--reload` if agents keep long Streamable HTTP sessions. REST `/api/v1/mcp/*` is unaffected. |
| `pencms-php.service` | `php -S 127.0.0.1:8009` + `router.php` (`PHP_CLI_SERVER_WORKERS=8`) |
| `pencms.env.example` | `JWT_ISSUER` / `MCP_RESOURCE_URL` / `CORS_ALLOW_ORIGINS` must be the **HTTPS** origin clients type. Optional `PYTHONPATH` + `PENCMS_PRO_ADMIN` load a sibling Pro overlay. |

Copy `pencms.env.example` → `pencms.env` (mode `0600`), set a long `JWT_SECRET`, then either:

- **User systemd** (graphical login or `loginctl enable-linger`): drop the two `.service` files in `~/.config/systemd/user/`, omit `User=` / `Group=`, `WantedBy=default.target`.
- **System systemd**: install the units as-is under `/etc/systemd/system/`.

After editing a unit file **or `pencms.env`**, recopy the unit into `~/.config/systemd/user/` (or `/etc/systemd/system/`), then `daemon-reload` and **restart** the service. uvicorn `--reload` watches Python source only — it does **not** pick up unit-file PATH, `EnvironmentFile`, or `ExecStart` changes.

Enable the nginx site, `nginx -t`, reload. First browser visit: `https://$HOST/admin/setup.php` (bootstrap admin), then mint a site-scoped agent key.

Pin `mcp>=1.12.0,<2` — `fastapi-mcp==0.4.0` crashes on MCP SDK 2.0.

## Load PenCMS Pro on a LAN install

Edition is overlay presence, not a `config.ini` flag. Core stays Core until the API can `import pencms_pro` and PHP can serve Users/Sites from the overlay admin tree. See [`editions.md`](./editions.md).

1. Check out `pencms-pro` as a **sibling** of Core (example: `/home/user/pencms` + `/home/user/pencms-pro`).
2. In `pencms.env` (not bash `export` — systemd `EnvironmentFile` is not a shell), set:

   ```bash
   PYTHONPATH=/home/user/pencms-pro
   PENCMS_PRO_ADMIN=/home/user/pencms-pro/frontend-php/src/admin
   ```

   Both services must load that file. The API unit already does. The PHP unit must list `EnvironmentFile=` too, or Users/Sites PHP will 404 while `/api/config` says `"edition":"pro"`.
3. Restart **both** units (`systemctl --user restart pencms-api pencms-php` or the system equivalents). `init_pro` failures fail API boot on purpose; a missing `PYTHONPATH` is a silent Core boot (`ImportError` swallowed).
4. Recopy [`nginx-pencms.conf`](../../deploy/lan/nginx-pencms.conf) into the live nginx site and `nginx -t` + reload. `/admin/js/` is served from Core disk first; overlay scripts (`users.js`, `settings-sites.js`) fall through to PHP. Skipping this step 404s those scripts and Alpine reports `usersAdmin` / `sitesSettings` is not defined.
5. Smoke: `GET /api/config` → `"edition":"pro"`; hard-refresh admin; sidebar Users and Sites; `GET /admin/js/users.js` is 200.

## Multisite (same as Compose)

Content lives under `content/sites/{id}/` after first-boot migration. Use **one** MCP connector URL (`MCP_RESOURCE_URL`) for the whole install; bind agents with named, site-scoped keys (PHP **Settings → Sites** / **AI → Agent Keys**). Details: [`mcp_guide.md`](./mcp_guide.md), [`deploy_compose.md`](./deploy_compose.md).

## What still needs the public internet

- **Cloud-hosted** Custom Connectors (e.g. some Claude connector flows) must reach your URL from *their* network. Pure LAN HTTPS is enough for browsers and agents on the same network; for off-LAN agents use a VPS, Tailscale/funnel, or a tunnel — still set `JWT_ISSUER` / `MCP_RESOURCE_URL` to that reachable HTTPS URL.

## Customize inspect (optional)

Theme Customize inspect needs Chromium **on the API host** (same process as FastAPI) and `PENCMS_PREVIEW_BASE_URL` set to the PHP origin that process can GET `/blog/` from (never the API port).

```bash
pip install playwright && playwright install --only-shell
export PENCMS_PREVIEW_BASE_URL=http://127.0.0.1:8009
```

Docker Compose uses a separate image target (`PENCMS_API_TARGET=inspect`): [`deploy_compose.md`](./deploy_compose.md).

## Related

- VPS / public HTTPS via Docker Compose + Caddy: [`deploy_compose.md`](./deploy_compose.md)
- MCP operator notes: [`mcp_guide.md`](./mcp_guide.md) (deployment + smoke checklist)
- Agent-owned site (sponsor + daily editor): [`agent-owned-site.md`](./agent-owned-site.md)
- Product direction: [`product_thesis.md`](./product_thesis.md)
- Longer Secure Context / mkcert walkthrough (same TLS idea as SilverBullet / the Rezilienz prototype): `securing_local_installations.md` if you still keep a copy of that tree.
