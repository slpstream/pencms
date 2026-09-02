# PenCMS Quickstart Guide

Welcome to PenCMS! This guide is designed for **anyone who wants to self-host PenCMS on their own hardware**—whether you are an experienced sysadmin, a curious developer, or someone setting up a home server for the very first time.

If you can copy and paste a command into a terminal window, you can run PenCMS.

---

## 1. The Big Picture: "The Brain and The Face"

PenCMS is built in two friendly parts that work together like a team:

```text
 ┌─────────────────────────────────────────────────────────────┐
 │                      YOUR COMPUTER                          │
 │                                                             │
 │   ┌───────────────────────┐       ┌─────────────────────┐   │
 │   │       THE BRAIN       │       │       THE FACE      │   │
 │   │   (Python / FastAPI)  │◄─────►│    (PHP Built-in)   │   │
 │   │       Port: 8008      │       │      Port: 8009     │   │
 │   └───────────────────────┘       └─────────────────────┘   │
 │               │                              │              │
 └───────────────┼──────────────────────────────┼──────────────┘
                 │                              │
                 ▼                              ▼
          AI Agents (MCP)                Your Web Browser
       (Claude, Cursor, etc.)         (Admin Editor & Blog)
```

1. **The Brain (Python / FastAPI on Port `8008`)**:
   - Manages all your Markdown files and media.
   - Handles search, tags, categories, and Git syncing.
   - Speaks directly to AI agents via the built-in MCP server.
2. **The Face (PHP on Port `8009`)**:
   - What you see and interact with in your web browser.
   - Includes the **Admin Dashboard**, the **Visual Post Editor**, and your **Public Blog**.
   - Automatically passes API requests to the Brain behind the scenes.

> [!IMPORTANT]
> Both **The Brain** and **The Face** must be running at the same time for PenCMS to work.

---

## 2. Before You Begin: Check Your Tools

You only need three tools on your computer. Open your terminal (Command Prompt, PowerShell, or Terminal on Linux/macOS) and check if you have them:

| Tool | Minimum Version | How to check in Terminal |
| :--- | :--- | :--- |
| **Python** | 3.12 or newer | `python3 --version` *(or `python --version`)* |
| **PHP** | 8.2 or newer | `php -v` |
| **Git** | Any recent version | `git --version` |

> [!TIP]
> **No Composer or npm required!** All required PHP packages are already bundled in the repository inside `frontend-php/vendor/`. You do not need to install Composer.

---

## 3. Track 1: 5-Minute Local Setup (Recommended)

This is the fastest, cleanest way to get PenCMS running right on your laptop or desktop.

### Step 1: Download PenCMS

```bash
git clone https://github.com/slpstream/pencms.git
cd pencms
```

---

### Step 2: Start "The Brain" (Python Backend)

Open **Terminal Window #1** and run:

```bash
cd backend-python

# 1. Create and activate an isolated Python environment
python3 -m venv venv
source venv/bin/activate       # On Windows use: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install Chromium for Theme Inspection (one-time download)
playwright install chromium

# 4. Start the Brain server!
uvicorn app.main:app --reload --port 8008
```

#### How do you know it worked?
Open your browser and visit:
👉 **[http://127.0.0.1:8008/api/health](http://127.0.0.1:8008/api/health)**

You should see:
```json
{"status":"ok"}
```
*(You can also browse the interactive API documentation at [http://127.0.0.1:8008/api/docs](http://127.0.0.1:8008/api/docs)).*

Keep this terminal window open!

---

### Step 3: Start "The Face" (PHP Frontend)

Open a **new, second terminal window** (Terminal Window #2) and navigate to the project folder:

```bash
cd pencms/frontend-php

# Start the PHP server with 8 worker processes
PHP_CLI_SERVER_WORKERS=8 php -c php.ini -S 127.0.0.1:8009 -t public router.php
```

#### How do you know it worked?
Your terminal will print:
```text
[Date] Development Server (http://127.0.0.1:8009) started
```

Keep this terminal window open too!

---

### Step 4: The 60-Second Onboarding Wizard

Now that both engines are running, open your web browser and go to:

👉 **[http://127.0.0.1:8009/admin/setup.php](http://127.0.0.1:8009/admin/setup.php)**

```text
 ┌─────────────────────────────────────────────────────────┐
 │                      PenCMS Setup                       │
 │           Create the first administrator account        │
 │                                                         │
 │   Username:        [ grandma               ]            │
 │   Master Password: [ ••••••••••••          ]            │
 │   Repeat Password: [ ••••••••••••          ]            │
 │                                                         │
 │             [ Create Admin Account ]                    │
 └─────────────────────────────────────────────────────────┘
```

1. Enter a **Username** (a single word with no spaces, e.g., `admin` or your name).
2. Enter a **Master Password** (at least 8 characters). This password securely encrypts your local keystore vault.
3. Click **Create Admin Account**.

Once saved, PenCMS will automatically redirect you to the login screen!

---

### Step 5: Log In and Tour Your New Site

1. On the login screen (**[http://127.0.0.1:8009/admin/login.php](http://127.0.0.1:8009/admin/login.php)**), enter your username and master password.
2. You are now inside the **Admin Dashboard** (**[http://127.0.0.1:8009/admin/](http://127.0.0.1:8009/admin/)**)!
3. Here you can write posts, create pages, upload images, choose themes, and manage settings.

> [!NOTE]
> **Important URL Note**: Visiting the bare address `http://127.0.0.1:8009/` returns a `404 Not Found` by design.
> - To manage your content: visit **`http://127.0.0.1:8009/admin/`**
> - To view your live public blog: visit **`http://127.0.0.1:8009/blog/`**

---

## 4. Track 2: Dedicated Home / LAN Server (Home Lab)

If you have a dedicated machine on your local home network (such as a Raspberry Pi, Intel NUC, or ThinkCentre) that stays on 24/7, you can run PenCMS as persistent system services with local HTTPS encryption.

PenCMS includes ready-to-use service and configuration templates in [`deploy/lan/`](../../deploy/lan/):

| File | Purpose |
| :--- | :--- |
| [`deploy/lan/pencms-api.service`](../../deploy/lan/pencms-api.service) | Systemd unit that keeps the Python Brain running automatically on port `8008` |
| [`deploy/lan/pencms-php.service`](../../deploy/lan/pencms-php.service) | Systemd unit that keeps the PHP Face running automatically on port `8009` |
| [`deploy/lan/nginx-pencms.conf`](../../deploy/lan/nginx-pencms.conf) | Nginx reverse-proxy configuration that provides local HTTPS (`:443`) |
| [`deploy/lan/pencms.env.example`](../../deploy/lan/pencms.env.example) | Environment template for secrets and origin configuration |

### Quick LAN Server Overview:
1. Copy `deploy/lan/pencms.env.example` to `deploy/lan/pencms.env` and set your local machine's IP (e.g. `192.168.1.50`) or local hostname (e.g. `pencms.lan`).
2. Generate a local SSL certificate using [`mkcert`](https://github.com/FiloSottile/mkcert) (`mkcert pencms.lan 192.168.1.50`).
3. Enable the two systemd units so PenCMS starts automatically whenever the computer boots.
4. Access your CMS from any device in your home at:
   - Setup: `https://<YOUR-LAN-IP>/admin/setup.php`
   - Admin: `https://<YOUR-LAN-IP>/admin/`
   - Public Blog: `https://<YOUR-LAN-IP>/blog/`

*(For full step-by-step instructions on setting up mkcert, Nginx, and systemd, see [`core/docs/lan_https.md`](./lan_https.md)).*

---

## 5. Track 3: Public VPS / Cloud Deployment (Docker)

If you want your website accessible to the entire world on a public domain (e.g. `cms.example.com`), Docker Compose with Caddy is the recommended path.

### Why Docker on a VPS?
- **Automatic SSL**: Caddy automatically provisions and renews free Let's Encrypt TLS certificates.
- **Isolated Playwright**: The container builds Chromium automatically (`PENCMS_API_TARGET=inspect`) without needing browser dependencies installed on the server OS.
- **Clean Backups**: Markdown files, uploaded media, and SQLite caches live in named Docker volumes (`pencms_content`, `pencms_assets`, `pencms_runtime`).

### Quick VPS Launch:
```bash
cd deploy
cp .env.example .env
```

Edit `.env` and set your public domain:
```ini
PUBLIC_HOST=cms.yourdomain.com
JWT_SECRET=use-a-long-random-string-here
JWT_ISSUER=https://cms.yourdomain.com
MCP_RESOURCE_URL=https://cms.yourdomain.com/api/mcp
CORS_ALLOW_ORIGINS=https://cms.yourdomain.com
PENCMS_API_TARGET=inspect
PENCMS_PREVIEW_BASE_URL=http://host.docker.internal:8009
```

Then start the stack:
```bash
docker compose up -d --build
```

Visit `https://cms.yourdomain.com/admin/setup.php` to initialize your site.

*(For complete details on multi-site domains, static site generation, and reverse proxying, see [`core/docs/deploy_compose.md`](./deploy_compose.md)).*

---

## 6. Connecting Your First AI Agent (Cursor, Claude, Scripts)

PenCMS is built from the ground up for the age of AI agents. You can connect agents like Cursor, Claude Desktop, or custom Python scripts to draft and edit articles.

### 1. Create an Agent Key
1. Log into your Admin Dashboard (**`http://127.0.0.1:8009/admin/`**).
2. Go to **Settings → AI → Agent Keys**.
3. Click **Create Agent Key**:
   - **Name**: Give it a friendly name (e.g., `cursor-writer` or `claude-partner`).
   - **Site**: Select `default`.
   - **Scope**: Choose `read` (to let the agent read posts) or `read+write` (to let the agent create and edit posts).
4. Click **Create Key** and copy the secret key (it starts with `pen-sk-...`). Keep it safe!

### 2. Connect via MCP
Point your AI agent harness (e.g. Cursor MCP or Claude Desktop) to your MCP endpoint:

| Setup Type | MCP Endpoint URL | Notes |
| :--- | :--- | :--- |
| **Local Machine (Track 1)** | `http://127.0.0.1:8008/api/mcp` | Direct connection to the Python Brain |
| **Home LAN Server (Track 2)** | `https://<YOUR-LAN-IP>/api/mcp` | Connect via standard HTTPS on port 443 |
| **Public VPS (Track 3)** | `https://cms.yourdomain.com/api/mcp` | Must match your `MCP_RESOURCE_URL` |

> [!CAUTION]
> **MCP URL Hygiene**: When connecting across a LAN or the internet, **never put `:8008` or `:8009` in your MCP Connector URL**. Always use the root HTTPS origin (port `443`), e.g., `https://myhost.com/api/mcp`.

*(For complete technical details on OAuth authorization and agent tools, see [`core/docs/mcp_guide.md`](./mcp_guide.md)).*

---

## 7. Help! Something Went Wrong (Troubleshooting)

### Q: I opened `http://127.0.0.1:8009/` and got a "404 Not Found" error.
**Answer**: Don't panic! PenCMS does not have a generic index at `/`.
- To view your administration dashboard: visit **[http://127.0.0.1:8009/admin/](http://127.0.0.1:8009/admin/)** (or `/admin/setup.php` on first run).
- To view your public blog: visit **[http://127.0.0.1:8009/blog/](http://127.0.0.1:8009/blog/)**.

---

### Q: Setup or Login says "Network error. Could not reach API."
**Answer**: The PHP Face cannot talk to the Python Brain.
1. Check **Terminal Window #1** (the Python backend). Is it still running?
2. Open **[http://127.0.0.1:8008/api/health](http://127.0.0.1:8008/api/health)** in your browser. If it doesn't return `{"status":"ok"}`, restart your Python server using `uvicorn app.main:app --reload --port 8008`.

---

### Q: In the Admin Theme Customize screen, I get "BROWSER_UNAVAILABLE".
**Answer**: The Theme Inspector uses headless Chromium to render preview snapshots.
1. Activate your Python virtual environment (`source venv/bin/activate`).
2. Run: `playwright install chromium`.
3. Restart the Uvicorn server in Terminal #1.

---

### Q: How do I turn PenCMS off and on again?
- **To Stop**: Click into Terminal #1 and press `Ctrl + C`. Then click into Terminal #2 and press `Ctrl + C`.
- **To Start Again**:
  - In Terminal #1:
    ```bash
    cd backend-python
    source venv/bin/activate
    uvicorn app.main:app --reload --port 8008
    ```
  - In Terminal #2:
    ```bash
    cd frontend-php
    PHP_CLI_SERVER_WORKERS=8 php -c php.ini -S 127.0.0.1:8009 -t public router.php
    ```
  - Re-open **[http://127.0.0.1:8009/admin/](http://127.0.0.1:8009/admin/)**. All your posts, themes, and settings are safely preserved in your `pencms-data` directory.
