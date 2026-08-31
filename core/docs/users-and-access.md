# Users and agent access (operator How-To)

**Core (2026-08-30):** one bootstrap operator, that operator’s profile, and
AI agent keys. Adding further human logins (`Settings → Users`,
`POST /api/users`) is a **Pro overlay** path — it is not a Core operator
step.

Give AI agents their own named keys from **Settings → AI**. Humans and
agents share **one capability vocabulary** (string lists such as
`write:posts`). Capabilities are **per site**. There is no own-vs-any
split yet: a writer with `write:posts` on a site may edit any post on
that site.

The PHP admin only **hides** buttons and nav. The API is the root of
trust. A hidden sidebar is not security.

This is **not** the public authors directory (`authors.yaml` / Settings →
Site). CMS logins and bylines are separate.

Connect an agent after minting a key: [`mcp_guide.md`](./mcp_guide.md).
Give an agent its own site: [`agent-owned-site.md`](./agent-owned-site.md).
Host deploy for agents: [`publish-agents.md`](./publish-agents.md).
How editions load: [`editions.md`](./editions.md).

---

## Two doors

| Who | Where you manage them | What they get |
| :--- | :--- | :--- |
| **Bootstrap operator (Core)** | Setup wizard, then **Settings → User** (profile) | Browser login, editor, site settings. One human. |
| **Additional humans (Pro)** | **Settings → Users** | Extra logins, memberships, roles. Overlay only. |
| **AI agents (Core)** | **Settings → AI** → Agent Keys | A `pen-sk-…` key bound to **one site** + scopes. MCP / OAuth — not a login form. |

Only **install admins** (`role: admin`) can mint, list, reassign, or revoke agent keys. Creating other humans (`users:manage`) is Pro; that capability does **not** let them mint agent keys.

The first account created at setup is the **bootstrap admin**. It cannot be deleted, demoted, or suspended.

---

## Additional humans (Pro overlay)

Core ships a single bootstrap operator. There is no Core UI or API for
inviting a second human. The **Users** sidebar item is hidden unless
`edition === "pro"`.

With the Pro overlay loaded you need **Settings → Users** in the sidebar
(`users:manage`, or you are already an admin).

1. Open **Settings → Users** → **Create User** (or **New**).
2. Set **username** (no spaces), **display name**, and an initial **password**. There is no email invite — tell them the password yourself.
3. Choose **role**:
   - **author** — only the sites and capabilities you assign.
   - **admin** — every site, every capability. Memberships are not required.
4. For an **author**, pick a **site** (header registry / Settings → Sites) and a **preset**, or **Customize capabilities**.
5. Click **Create user**. A YAML file appears under `data/users/{uuid}.yaml`.

Created users (and anyone whose password you reset) must **change that password** before the editor unlocks. They can still open **GET `/api/auth/me`**. The header shows a change-password banner until they succeed.

### After they log in

- The **site switcher** lists only membership sites (admins see all).
- Sidebar and in-page actions follow their **effective caps** for the active site (for example a Writer sees Posts / Pages / Media, not Theme or Publish).
- They cannot raise their own role to admin, grant themselves `users:manage` / `manage:sites`, or mint agent keys.

---

## Human presets (per site) — Pro overlay

These presets apply when the overlay is loaded and you are assigning
memberships on **Settings → Users**. Core’s bootstrap admin already has
every capability.

Presets are stored as capability lists, not special role names.

| Preset | Capabilities |
| :--- | :--- |
| **Writer** | `write:posts`, `write:pages`, `write:media`, `write:authors`, `write:taxonomy` |
| **Editor** | Writer + `delete:posts`, `delete:pages`, `delete:media`, `publish:content`, `write:seo` |
| **Publisher** | Editor + host `publish` (Deploy Grant still required for **agents**) |
| **Site admin** | All **site-scoped** caps for that site, including `read`. Does **not** include install-wide `users:manage` or `manage:sites` unless the account **role** is `admin`. |

You can tick extra caps on the checklist. Add further sites from the user’s **Edit** screen (site + preset, then **Add site**).

**Empty capabilities on a site remove that membership.** Do not save an empty list to mean “on the site with no caps.”

---

## Edit, suspend, reset, delete (Pro overlay)

On the user row or Edit screen:

| Action | Effect |
| :--- | :--- |
| **Edit** | Display name, per-site capabilities, extra sites |
| **Reset password** | You set a temporary password; they must change it on next login |
| **Suspend** | `status: blocked`. Login and API calls return **403** with “Your account is suspended.” (`account_suspended`). Wrong password still looks like a normal login failure. |
| **Activate** | Unblock |
| **Delete** | Removes the YAML and **that user’s agent keys**. Posts/pages they wrote stay on disk (orphaned provenance). No reassign workflow. Not yourself, not bootstrap. |

**Block** is not the same as **revoke**. Block stops login. Revoke (strip memberships or delete keys) can leave the account able to sign in with no sites.

---

## Capability vocabulary (shared)

`write:*` means create **and** update. `delete:*` is separate. Never split `create:` / `update:`.

| Capability | Means |
| :--- | :--- |
| `read` | Agent list/search/inspect. Monolithic — no `read:posts`. Human GET of posts/pages does **not** require `read`. |
| `write:posts` / `delete:posts` | Blog posts (`page` flag absent) |
| `write:pages` / `delete:pages` | Static pages (`page: true` in frontmatter). Same `/api/pages` router as posts. |
| `write:media` / `delete:media` | Media library |
| `publish:content` | Content **status**: approve / publish in the editor (`PATCH …/approve` and `PATCH …/publish`). **Not** host deploy. |
| `write:menus` / `write:authors` / `write:seo` / `write:theme` / `write:taxonomy` | Navigation, `authors.yaml`, SEO/presentation, theme fork, vocabularies + terms (`taxonomy.yaml`). Human Structure UI stays admin-only. Not collections.yaml / Publishing Rules. |
| `publish` | Host deploy of static `dist/` (Publish page / MCP `publish_site`). Agents also need a **Deploy Grant**. |
| `users:manage` | User CRUD / memberships / suspend / password reset (install-wide) |
| `manage:sites` | Create/rename/delete sites in the registry (install-wide). **Pro overlay** — Core unmounts HTTP CRUD; GET list + PATCH settings stay. |

**`publish:content` ≠ `publish`.** A copy editor can approve a draft without being allowed to deploy the live host.

Legacy agent scope `write` expands one-way to every `write:*`, every `delete:*`, and `publish:content`. It never implies host `publish`, `users:manage`, or `manage:sites`. `write:posts` alone does **not** expand to `write` or `write:theme`.

---

## Control granular access for AI agents

Agent keys are **admin-only**. Open **Settings → AI** → **Agent Keys** (unlock the Zero-Knowledge vault if prompted).

### Mint a key

1. **Name** the agent (unique per operator), e.g. `blog-cursor`. Prefer `{site}-{agent}`.
2. Pick the **Site**. One key ↔ one site. Content tools only touch `content/sites/{site_id}/`.
3. Pick a **scope preset** or **Custom**:

| Preset | Typical use |
| :--- | :--- |
| **Read-Only** | `read` — search and inspect |
| **Writer** | `read` + write posts/pages/media/authors/taxonomy |
| **Editor** | Writer + delete + `publish:content` + SEO |
| **Publisher** | Editor + host `publish` (still need a Deploy Grant) |
| **Legacy Read+Write** | `read` + `write` (expands to all write/delete/`publish:content`, not host deploy) |
| **Legacy Read+Write+Publish** | Legacy write + host `publish` |

Agent Writer/Editor/Publisher presets **include `read`** so the agent can list and search. Human Writer does **not** need `read` for the admin editor.

4. Click **Generate New Key**. Copy `pen-sk-…` immediately (shown once). OAuth Custom Connectors only need the key to **exist** in the list; scripts/CI need the secret.

Then connect the client: [`mcp_guide.md`](./mcp_guide.md) (OAuth consent picks `site · name`, or `POST /api/auth/token` for automation).

### Tighten or revoke

| Control | Where | Effect |
| :--- | :--- | :--- |
| **Fewer scopes** | Mint a new key with a tighter preset (scopes are chosen at mint) | New tokens follow the new key; revoke the old one |
| **Move to another site** | Agent Keys → Site dropdown → **Save** | Secret unchanged. **Existing JWTs keep the old site until they expire** (~15 minutes). Remint via token/OAuth refresh. |
| **Revoke** | Agent Keys → revoke | That agent cannot call MCP. Does not delete human users. |
| **Deploy Grant** | **Publish → Settings** | Separate knob for host deploy. Scope `publish` without a grant still cannot deploy. [`publish-agents.md`](./publish-agents.md) |

Do **not** mint a god-key (`write` + `publish` + every site) for a draft-only helper. Prefer Writer or Read-Only on the one site it should touch.

### Agent-assisted bootstrap (approve-code)

An agent can request a named, site-bound key without you pasting a secret into chat:

1. Agent calls `POST /api/auth/agent/request-code` and shows you a short **user code**.
2. You **Approve** (or deny) under **Settings → AI → Agent Keys → Pending approvals**.
3. Agent calls `POST /api/auth/agent/verify-code` and stores `pen-sk-…` once.

You still sponsor issuance. Authors cannot approve codes.

---

## What the UI does not do

- Forged `pen_role` / `pen_user_id` cookies can open admin HTML. Privileged APIs still return **403**.
- Structure, AI settings, and Translations stay **admin-only** in the sidebar (those APIs have no extra v1 cap besides the AI **keys** panel). File Storage / SSH / install `config.ini` (`GET|PUT /api/storage/config`, restart, SSH keys, `GET|PUT /api/storage/general`, install `PUT /api/storage/theme`) require a human **admin** session — not hidden chrome, not `users:manage`.
- Generic save of a post (`PUT`) does not require `publish:content`; the editor’s Published/Unpublished control does. Use **Editor** if they should change content status through the dedicated approve/publish actions.

---

## API (optional)

Same rules as the UI. Cookie `pen_jwt` or Bearer JWT → user YAML. Never `pen_role`.

| Task | Endpoint |
| :--- | :--- |
| Session (caps, sites) | `GET /api/auth/me` |
| Create user | `POST /api/users` (`users:manage`) — **Pro overlay** |
| Set one site’s caps | `PATCH /api/users/{uuid}/memberships/{site_id}` — `capabilities: []` **removes** the site — **Pro overlay** |
| Mint agent key | `POST /api/auth/keys` (admin only) |

Contract: [`../openapi.yaml`](../openapi.yaml) (`/auth/me`; `/users` is the Pro superset until the Phase 6 spec cut).
