# Changelog

All notable changes to PenCMS will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] - 2026-09-04

### Inaugural Public Release

PenCMS is the world's first AI-native, agent-first, Markdown-and-Git Content Management System.

* **Bundles Traven Editor v0.2.28** (`@freedomware/traven` and `@freedomware/traven-expand-embed`).

### Key Features

#### 🤖 Agent-First Architecture & MCP
* **Model Context Protocol (MCP) Server**: Built-in streamable HTTP MCP gateway (`/api/mcp`) supporting standard MCP client connections.
* **OAuth 2.0 & CIMD**: Sovereign authentication with RFC-compliant OAuth authorization server, Protected Resource Metadata (PRM), and Client ID Metadata Documents (CIMD).
* **Granular Agent Capabilities**: Scoped keys (`read`, `write:posts`, `write:pages`, `publish`, etc.) preventing agent privilege escalation.
* **Agent Leash & Loop Guard**: Built-in session guard (`McpSessionGuardMiddleware`) and sliding-window rate limiting (`McpRateLimitMiddleware`).

#### 📝 Markdown & Flat-File Storage
* **Zero Database Bottlenecks**: Content, taxonomy, and menus stored in plain Markdown files with YAML frontmatter.
* **High-Performance Query Cache**: Embedded SQLite index for instantaneous reads and full-text search (FTS) without sacrificing flat-file sovereignty.
* **Optimistic Concurrency**: Opaque version tokens and `expected_version` checks preventing race conditions between human and agent writes.

#### 🎨 Human Admin & Traven Editor
* **Dual-Door System**: PHP admin UI (`:8009`) for humans alongside FastAPI brain (`:8008`) for agents.
* **Embedded Traven Editor (v0.2.28)**: Clean WYSIWYM Markdown editing with dual-duty CSS, custom block widgets, and shortcode previews.
* **Theme Customizer & Live Inspect**: Dynamic theme tweaking with dual-scope CSS rules and headless Playwright Chromium inspection.

#### 🌐 Multi-Site & Publishing
* **Multi-Site Tenancy**: Host multiple sovereign blogs, wikis, and agent sites from a single deployment with isolated content trees.
* **Static Export & Multi-Provider Deploy**: Static HTML generator (`generate-static.php`) with direct deployment grants for Cloudflare Pages, GitHub Pages, Netlify, and Vercel.
* **Scheduled Publishing**: Native support for future-dated posts with automated rebuild triggers (`rebuild-due.php`).

#### 🔒 Security Hardening
* ReDoS-safe shortcode and markdown heading parsers in `mcp_tools`.
* SSRF guards and sanitized URL fetching for remote assets and AI proxies.
* Strict `SameSite` and `Secure` cookie attributes for human admin sessions.
* DOMPurify sanitization in the AI sidebar and markdown rendering.
