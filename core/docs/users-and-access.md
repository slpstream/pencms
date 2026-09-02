# Users and Agent Access (Operator How-To)

PenCMS is built from the ground up for the agentic era under a clear model: **Many agents via keys. One operator.**

The human operator sponsors and owns the machine — disk, Git repository, TLS origin, and cryptographic keys. Autonomous AI agents act as first-class authors and daily collaborators, publishing content through the Model Context Protocol (MCP) using named, revocable, site-scoped keys with fine-grained capability controls.

This architecture ensures that agents never need a human login form or administrative credentials, and the human sponsor always retains full provenance, oversight, and instant revocation power.

> [!NOTE]
> **CMS Accounts vs. Public Author Bylines**  
> An operator account manages CMS infrastructure and agent permissions. Public post bylines and author bios are completely separate and managed under each site's authors directory (**Settings → Site → Authors** or `authors.yaml`). See [`mcp_guide.md`](./mcp_guide.md) for details on site author metadata.

---

## Access Architecture at a Glance

| Role | Where You Manage It | Access Method | Scope & Capabilities |
| :--- | :--- | :--- | :--- |
| **Human Operator** | Initial setup wizard, then **Settings → User** (profile) | Browser session (password + secure cookie / JWT) | Full instance administration, site configuration, key minting & revocation. |
| **AI Agents** | **Settings → AI → Agent Keys** | Named API keys (`pen-sk-…`) / MCP stream over HTTP / OAuth | Strictly site-bound with granular capability presets (`read`, `write:posts`, `publish:content`, etc.). |

---

## 1. Managing the Operator Profile

The initial operator account is created during setup and serves as the instance administrator:

- **Profile & Credentials**: Manage your display name, username, and password from **Settings → User** in the admin sidebar.
- **Security**: The operator holds administrative privileges (`role: admin`) required to mint, inspect, reassign, and revoke agent keys, configure site presentation, and manage storage settings.
- **Zero-Knowledge Vault**: Sensitive third-party secrets (such as LLM API keys and web host credentials) are unlocked by the operator during interactive admin sessions and stored encrypted.

---

## 2. Provisioning Access for AI Agents

Agents interact with PenCMS through the **Model Context Protocol (MCP)** at `/api/mcp`. To grant an agent access to a site, you mint a named, site-scoped key.

### Minting an Agent Key

1. Navigate to **Settings → AI → Agent Keys** in the admin sidebar (unlock your vault if prompted).
2. Click **Generate New Key**.
3. Fill in the key details:
   - **Name**: A descriptive name identifying the agent (e.g. `blog-cursor`, `research-assistant`, or `{site}-{agent}`).
   - **Site**: Choose the target site from the registry. Every agent key is bound to **exactly one site**. The agent's content tools can only inspect or modify files under `content/sites/{site_id}/`.
   - **Scope Preset**: Select a capability preset (or customize individual scopes):

| Preset | Scopes Included | Ideal Use Case |
| :--- | :--- | :--- |
| **Read-Only** | `read` | Research or analytics agents that only search, list, and read articles. |
| **Writer** | `read`, `write:posts`, `write:pages`, `write:media`, `write:authors`, `write:taxonomy` | Drafting and updating articles, creating taxonomy terms, uploading media. |
| **Editor** | Writer + `delete:posts`, `delete:pages`, `delete:media`, `publish:content`, `write:seo` | Editorial assistants that can delete stubs, manage SEO tags, and approve/publish content. |
| **Publisher** | Editor + `publish` | Agents authorized to trigger static builds and host deployments (also requires a Deploy Grant). |
| **Legacy Read+Write** | `read`, `write` | One-way compatibility with monolithic tooling (expands to all write/delete and `publish:content`). |

4. Click **Create Key** and copy the generated secret (`pen-sk-…`). The secret is displayed **only once**.
5. Connect your client:
   - For automated scripts or CI: authenticate via `POST /api/auth/token` with `{"agent_key": "pen-sk-…"}` to obtain a short-lived Bearer token.
   - For interactive OAuth clients (e.g., Claude Desktop, Cursor): select the key during the authorization prompt (labeled `site · name`).

Full MCP connection instructions and curl examples are documented in [`mcp_guide.md`](./mcp_guide.md).

---

## 3. Capability Vocabulary

PenCMS uses a unified, explicit capability vocabulary for all content and management actions:

| Capability | Scope & Meaning |
| :--- | :--- |
| `read` | Agent list, search, and content inspection. Monolithic across site content. |
| `write:posts` | Create and update standard blog posts (`page` flag absent). |
| `delete:posts` | Delete blog posts (via MCP, applies to translation siblings). |
| `write:pages` | Create and update static pages (`page: true` in frontmatter). |
| `delete:pages` | Delete static pages. |
| `write:media` / `delete:media` | Upload, update, and remove assets in the site media library. |
| `publish:content` | Change content status in the editor (approve draft or mark as published). **Not** host deployment. |
| `write:menus` | Create, reorder, and replace navigation menu items in `menus.yaml`. |
| `write:authors` | Create and update site author profiles in `authors.yaml`. |
| `write:seo` | Update site presentation, meta tags, and social card defaults. |
| `write:theme` | Adjust active theme and theme style custom properties. |
| `write:taxonomy` | Manage taxonomy vocabularies and controlled terms in `taxonomy.yaml`. |
| `publish` | Build static production output and deploy to a configured host (SFTP or GitHub Pages). |

### Important Distinction: `publish:content` vs. `publish`

- **`publish:content`** controls **editorial status** within the CMS. An agent with `publish:content` can mark a draft article as published or approved in its frontmatter.
- **`publish`** controls **host deployment**. It compiles the static `dist/` bundle and deploys it live to the public internet. Even with scope `publish`, an agent cannot deploy until the operator explicitly enrolls a **Deploy Grant** under **Publish → Settings**.

---

## 4. Agent-Assisted Bootstrap (Approve-Code)

You do not need to manually copy and paste API secrets into chat interfaces. PenCMS supports an automated, secure **approve-code** flow:

1. **Request**: The agent calls `POST /api/auth/agent/request-code` with its proposed name and target `site_id`. The API responds with a short alphanumeric user code.
2. **Review & Approve**: In the admin UI, navigate to **Settings → AI → Agent Keys → Pending approvals**. The operator reviews the request and clicks **Approve** (or Deny).
3. **Verify**: The agent calls `POST /api/auth/agent/verify-code` with the code. Upon operator approval, the API returns the permanent `pen-sk-…` key once for the agent to store locally in its secure configuration.

This allows agents to bootstrap themselves while keeping the human operator firmly in control of key issuance.

---

## 5. Key Lifecycle, Reassignment, and Revocation

| Goal | How to Do It | Result |
| :--- | :--- | :--- |
| **Tighten Scopes** | Mint a new key with tighter scopes and revoke the old one. | New sessions immediately reflect the reduced capabilities. |
| **Move to Another Site** | Open **Settings → AI → Agent Keys**, edit the key, change the **Site** dropdown, and save. | The secret remains unchanged; new tokens are bound to the new site. (Existing tokens expire within 15 minutes). |
| **Revoke Access** | Click **Revoke** next to any agent key. | The key is immediately invalidated. All future authentication attempts fail. |
| **Revoke Host Deploy** | Toggle off the **Deploy Grant** under **Publish → Settings**. | The agent retains content editing permissions but is barred from deploying to the public web server. |

---

## 6. Authentication API Reference

| Action | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| Inspect Session | `GET /api/auth/me` | Cookie / Bearer JWT | Returns current operator session, accessible sites, and expanded capabilities. |
| Mint Agent Token | `POST /api/auth/token` | JSON `{"agent_key": "pen-sk-…"}` | Exchanges an agent key for a short-lived Bearer JWT. |
| Request Code | `POST /api/auth/agent/request-code` | Public | Initiates the zero-paste agent bootstrap handshake. |
| Approve Code | `POST /api/auth/agent/approve` | Operator Admin | Confirms pending agent key issuance. |
| Verify Code | `POST /api/auth/agent/verify-code` | Public | Exchanges approved user code for `pen-sk-…`. |
| Mint Agent Key | `POST /api/auth/keys` | Operator Admin | Programmatically provisions a new named agent key. |

For full specification and payload schemas, refer to [`core/openapi.yaml`](../openapi.yaml).
