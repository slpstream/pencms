# Publish to a host (operator How-To)

Build the active Content site’s static `dist/` and deploy it to a public web host — SFTP or GitHub Pages — from **Publish** in the admin sidebar. Cloudflare Pages, Vercel, Netlify, and here.now are PenCMS Pro overlay adapters.

> **Quick Concept: Git Push vs. Web Host Deploy**
> - **Git Content Push (`commit_and_push`)**: Saves markdown source files and version history to your Git repository. Updating Git does **not** automatically update the live HTML files on your public web server.
> - **Host Deploy (`publish_site`)**: Compiles your markdown and assets into a static `dist/` production build, then uploads it to your web host (via SFTP or GitHub Pages) so visitors pointing to your registered domain name see the latest live site.
> - **Deploy Grant**: An explicit server permission allowing authorized AI agents to trigger host deployments without giving those agents access to your underlying SSH keys or web host passwords.

This is **host deploy**, not Git content push. Agents that only need Markdown in the repo use MCP `commit_and_push`. Agents that should update the live site use `publish_site` after you enroll a Deploy Grant — see [`publish-agents.md`](./publish-agents.md).

**One publish target per site.** The page always uses the header’s active Content site. Multisite installs: switch sites before configuring or publishing.

---

## What Publish is (and is not)

| Surface | Job |
|---|---|
| **Publish** (this page) | Build `dist/` → upload/deploy to a **public host** |
| **Content Storage SSH** (Settings → Storage) | Live CMS content root (read/write Markdown). Do **not** point that at the public docroot |
| **MCP `commit_and_push`** | Stage/commit/push content Git |
| **MCP `publish_site`** | Same host deploy as the Publish button (agent path) |

Host passwords and platform tokens never appear in `sites.yaml`. Interactive admin keeps them in the Zero-Knowledge vault. Agents never receive them — see the agent guide.

---

## First publish (SFTP, ~5 minutes)

1. Unlock the **Zero-Knowledge vault** (admin header) if you use password auth.
2. Open **Publish** → **Settings**.
3. Set **Provider** to **SFTP**.
4. Fill **Host**, **Port** (usually `22`), **Username**, **Remote path** (docroot, e.g. `/var/www/html`), and optional **Public URL** (shown after success and used as the Live link).
5. Choose auth:
   - **Password** — enter the SFTP password; Save stores it in the vault as `PUBLISH_SFTP_PASS:{siteId}` (never in YAML).
   - **SSH key** — use the install Ed25519 key (same as Storage). Copy the public key into the host’s `authorized_keys`. No publish password needed.
6. Click **Save**, then **Test Connection**. Fix host/user/path/auth until it succeeds.
7. Open the **Publish** tab → **Publish**. Watch the log until status is success; open the Live URL if set.

Subsequent publishes are incremental (only changed files) unless you check **Force full upload**.

---

## Auth: vault password vs SSH key

| Method | When to use | Secret location |
|---|---|---|
| **Password** | Host only allows password login | ZK vault (`PUBLISH_SFTP_PASS:{siteId}`); sent as `X-Vault-Publish-Pass` while the vault is unlocked |
| **SSH key** | Preferred for unattended / agent deploys | Install `~/.ssh/id_ed25519`; grant is flag-only (no password copy) |

Unlock the vault before Save/Test/Publish when using password auth. Key auth does not need a publish password in the vault.

---

## Provider options

Pick a provider under **Publish → Settings**. Only one target is active per site.

### SFTP

Classic `scp`/OpenSSH upload to `remote_path`. Fields: host, port, username, remote path, public URL, password or key.

### GitHub Pages

Orphan git push of `dist/` to a branch (default `gh-pages`). Set **Owner**, **Repo**, optional **Branch** and **CNAME**. Vault: GitHub PAT with repo contents write. Configure the repo’s Pages source to that branch at `/`.

For every provider, interactive secrets live in the ZK vault; agentic deploys need a **Deploy Grant** ([`publish-agents.md`](./publish-agents.md)). Cloud deployers (Cloudflare Pages, Vercel, Netlify, here.now) ship with PenCMS Pro.

---

## Export as zip

On **Publish → Export**, two paths are available:

- **Export static site** — runs the streaming build pipeline (scope, optional domain override, live Build Execution Log).
- **Download as .zip** — builds the active site, packages `dist/`, and starts a browser download (`Content-Disposition: attachment`). Failed or empty builds return an error — you never get a bogus empty zip.

You do **not** need a publish host configured to export.

---

## Optional post-publish webhook

Under Settings, set **Webhook URL** (`http://` or `https://` only). After a deploy **succeeds or fails**, PenCMS POSTs JSON:

**Success**

```json
{
  "event": "publish.success",
  "site_id": "default",
  "provider": "sftp",
  "public_url": "https://example.com",
  "published_at": "2026-07-21T12:00:00+00:00"
}
```

**Failure**

```json
{
  "event": "publish.failed",
  "site_id": "default",
  "provider": "sftp",
  "public_url": "https://example.com",
  "published_at": null,
  "error": "SFTP upload failed: ..."
}
```

Optional **Webhook signing secret**: when set, requests include `X-PenCMS-Signature: sha256=<hex>` over the exact JSON body bytes (compact UTF-8, no extra whitespace). Verify with HMAC-SHA256 of the raw body using the shared secret.

Missing URL is a no-op. Webhook errors are logged as warnings and do not fail the publish.

---

## Multisite notes

- Always confirm the **active Content site** in the admin header before Save / Publish / Export.
- Single-site builds write OG images under `{output}/images/og` inside that site’s `dist/`. Pro `--all-sites` builds (admin export tooling) write `{output}/{site_id}/images/og`. Core refuses `--all-sites`.
- Each site has its own publish block, vault secrets, and Deploy Grant.

---

## Troubleshooting

| Symptom | Check |
|---|---|
| Empty Publish hero / “Connect a host” | Settings not saved, or wrong site in the header |
| Test Connection fails (password) | Vault unlocked? Correct password for this site? |
| Test Connection fails (key) | Public key on host? `authorized_keys` for that user? |
| Publish button disabled | Target not `configured` — Save Settings first |
| Concurrent run rejected | Wait for the in-progress publish, or reattach via the log/status UI |
| Platform token rejected | Re-enter token with vault unlocked; confirm provider-specific fields |

---

## Related

- Agents + hybrid enroll: [`publish-agents.md`](./publish-agents.md)
- MCP scopes and tools: [`mcp_guide.md`](./mcp_guide.md)
- Product direction: [`product_thesis.md`](./product_thesis.md)
- Agent discovery: [`llms.txt`](./llms.txt)
