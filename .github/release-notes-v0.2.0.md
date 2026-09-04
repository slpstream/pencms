# PenCMS v0.2.0: The Agent-First, Flat-File CMS

Freedomware is glad to announce the inaugural public release of **PenCMS** (`v0.2.0`).

PenCMS is the world’s first AI-native, flat-file CMS designed for the age of autonomous agents. It combines an MIT-licensed Markdown-and-Git engine with a Python (FastAPI) brain and a PHP human admin interface, allowing humans and AI agents to collaborate on shared content.

### Highlights

* **Agent-First MCP Gateway (`/api/mcp`)**: Full Model Context Protocol server support with OAuth 2.0 discovery, granular capabilities (`read`, `write:posts`, `write:pages`, `publish`), and site-bound revocable keys.
* **Traven Editor Integration**: Built-in integration with the [Traven](https://github.com/slpstream/traven) WYSIWYM markdown editor with dual-duty CSS and live shortcode previews.
* **Contract-First OpenAPI Specification**: Every route, validation rule, and schema is codified under `core/openapi.yaml`.
* **Zero-DB Content Storage**: Content and metadata are stored directly in clean Markdown + YAML files. Fast reads are powered by a lightweight local SQLite FTS index.
* **Static Site Generator & Multi-Host Deploy**: Export static sites with scheduled post handling and publish directly with SFTP or git.

---

### Quick Start

**Local Dev (2 minutes):**
```bash
# Terminal 1: Python Backend (:8008)
cd backend-python && pip install -r requirements.txt && uvicorn app.main:app --port 8008

# Terminal 2: PHP Admin (:8009)
cd frontend-php && php -c php.ini -S 127.0.0.1:8009 -t public router.php
```
