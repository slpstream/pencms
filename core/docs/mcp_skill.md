# PenCMS MCP skill stub

Use PenCMS as a remote MCP CMS over Streamable HTTP.

## Connect
- MCP URL: `{JWT_ISSUER}/api/mcp` (must equal `MCP_RESOURCE_URL`)
- Interactive clients: OAuth discovery (PRM → AS → PKCE) then admin consent (pick existing agent key)
- New key without paste: `POST /api/auth/agent/request-code` → admin approves code → `POST /api/auth/agent/verify-code` → store `pen-sk-…`
- Automation: `POST /api/auth/token` with `{"agent_key":"pen-sk-…"}`; use returned Bearer on `/api/mcp`. `GET /llms.txt` first. Echo `Mcp-Session-Id` or initialize `result.sessionId` on later JSON-RPC in the **same** session (do not re-initialize per tool); or call REST `/api/v1/mcp/*`. Missing session on `tools/list` → 400. Single YAML field → `update_frontmatter_field`. Omitted `Accept` is OK.

## Scopes
Humans and agents share one vocabulary (stored as string lists). Expansion is check-time only.

- `read` — search, list, inspect (monolithic; no `read:posts`)
- `write:posts` / `write:pages` — create+update; same page tools; branch on frontmatter `page: true` (create: body; update/delete: existing doc). Kind flip → `cannot_change_page_kind`
- `delete:posts` / `delete:pages` — delete (MCP: translation sibling only)
- `write:media` / `write:menus` / `write:authors` / `write:seo` / `write:theme` / `write:taxonomy`
- `publish:content` — content status / translation review. **Not** host deploy
- `write` (legacy) — expands one-way to all `write:*`, `delete:*`, `publish:content`. Does **not** imply host `publish`. `write:posts` does not expand to `write` or `write:theme`
- `publish` — static host deploy (`publish_site`); requires Deploy Grant; never returns host passwords
- `commit_and_push` still needs stored `write` (git only; not host deploy)

## Prefer live docs
If this stub disagrees with [`mcp_guide.md`](./mcp_guide.md) or [`llms.txt`](./llms.txt), follow those files (or `GET /llms.txt` on a live issuer).

## Zero-to-Hero bootstrap
Draft checklist for blank-site setup (theme, identity, SEO, menus, authors, taxonomy, first posts, extractive summary/faqs): [`zero-to-hero-skill.md`](./zero-to-hero-skill.md). Human sponsor + agent’s own site: [`agent-owned-site.md`](./agent-owned-site.md). Presentation tools: `list_themes`, `get_site_presentation`, `update_site_presentation`. Extractive persist: [`mcp_guide.md`](./mcp_guide.md#extractive-summary-and-faqs).

## Publish to host
- Human: [`publish-howto.md`](./publish-howto.md)
- Agent + hybrid: [`publish-agents.md`](./publish-agents.md)
- `publish_site` / `get_publish_site_status` ≠ `commit_and_push` / `get_publish_status`

## Expand / embed (Nutshell)
- `suggest_internal_links` — live-published link/expand targets
- `check_expand_refs` — validate `[expand]`/`[embed]` slugs in markdown or a page
- Insert shortcodes with `write_content_file` (no MCP cursor tool). See [`editor-link-suggest-and-expand.md`](./editor-link-suggest-and-expand.md).

## Exact-language siblings
- Discover with `get_translation_config` + `list_translation_gaps`. If optional `automation_policy.enabled` is true, use a target bound to this key and match its exact `operation` and non-secret `model`.
- Start/finish body-free external telemetry with `report_translation_run`; compatible targets may share a run only when operation/model/key/review policy match.
- Create gaps with `create_translation_sibling`; update existing siblings with `write_content_file(language=...)`. When policy is enabled, both require the active bound `run_id`; runless or unbound writes are rejected.
- `delete_translation_sibling` does not need a run, but an enabled policy still requires the target's bound key.
- Agent writes honor `ai_publish_autonomy` (including translation siblings). `require_review` is the safe default for the `needs_review` queue flag; explicit `allow_unreviewed_draft` only clears that flag and never publishes. Human Approve publishes. Agents cannot self-review.
- Pause blocks new automation but not human/manual writes. Revocation blocks new translation writes/run starts even for an already-minted token.
- Policy files and JSONL telemetry contain no provider credentials or translated bodies; keep model credentials in the vault or external runner secret store.
- PenCMS provides no model execution, queue, scheduler, or translation orchestration; run that loop externally.
