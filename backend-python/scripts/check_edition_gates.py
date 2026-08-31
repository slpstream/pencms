#!/usr/bin/env python3
"""Phase 6 edition grep gates for PenCMS Core product source.

Scope: backend-python/app/, frontend-php/src/ (except vendor/), core/openapi.yaml.
Does not scan tests/ or core/docs/ (those may name overlay tokens).

Run from the pencms repo root or backend-python/:

    python3 backend-python/scripts/check_edition_gates.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent
APP = BACKEND / "app"
PHP_SRC = REPO / "frontend-php" / "src"
OPENAPI = REPO / "core" / "openapi.yaml"

FORBIDDEN = [
    "cloudflare_pages",
    "here_now",
    "X-Vault-Publish-Vercel-Token",
    "X-Vault-Publish-Cf-Pages-Token",
    "X-Vault-Publish-Netlify-Token",
    "X-Vault-Publish-Here-Now-Key",
    "include_router(users_router",
]

MUST_CONTAIN = [
    "PUBLISH_GITHUB_TOKEN",
    "AGENT_KEYS",
    "webhook_url",
    "theme_customize",
    "theme_package",
    "mcp_theme_inspect",
    "translations",
    "SftpPublishProvider",
    "GithubPagesPublishProvider",
    "pencms_pro.init_pro",
]

NAV_HREF_ALLOWLIST = {
    "frontend-php/src/admin/includes/_admin-sidebar.php",
    "frontend-php/src/admin/includes/_admin-header.php",
    "frontend-php/src/admin/admin-dashboard.php",
}

PRO_ADMIN_FILES = (
    "admin-users.php",
    "admin-settings-sites.php",
)

SKIP_DIR_NAMES = {"vendor", "__pycache__", ".git"}


def _iter_product_files() -> list[Path]:
    files: list[Path] = []
    for root in (APP, PHP_SRC):
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.suffix.lower() in {
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".webp",
                ".ico",
                ".woff",
                ".woff2",
                ".ttf",
                ".eot",
                ".map",
                ".pyc",
            }:
                continue
            files.append(path)
    if OPENAPI.is_file():
        files.append(OPENAPI)
    return files


def check() -> list[str]:
    errors: list[str] = []
    rel = lambda p: str(p.resolve().relative_to(REPO))

    for name in PRO_ADMIN_FILES:
        banned = REPO / "frontend-php" / "src" / "admin" / name
        if banned.exists():
            errors.append(f"Pro admin file must not exist in Core: {rel(banned)}")

    found_must = {token: False for token in MUST_CONTAIN}
    for path in _iter_product_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        path_rel = rel(path)
        for token in FORBIDDEN:
            if token in text:
                errors.append(f"{path_rel}: forbidden token {token!r}")
        for name in PRO_ADMIN_FILES:
            if name in text and path_rel not in NAV_HREF_ALLOWLIST:
                errors.append(
                    f"{path_rel}: {name!r} is only allowed as a nav href "
                    f"in {sorted(NAV_HREF_ALLOWLIST)}"
                )
        if "NetlifyPublishProvider" in text or 'id = "netlify"' in text or "id = 'netlify'" in text:
            errors.append(f"{path_rel}: netlify publish provider id")
        for token in MUST_CONTAIN:
            if token in text:
                found_must[token] = True

        if path.name in {"config.py", "storage.py"} and path_rel.endswith(
            ("app/config.py", "app/routers/storage.py")
        ):
            if "SSHStorageProvider.from_uri" in text:
                errors.append(f"{path_rel}: SSHStorageProvider.from_uri is not allowed")
            if 'register_storage_type("ssh"' in text or "register_storage_type('ssh'" in text:
                errors.append(f"{path_rel}: register_storage_type(\"ssh\" is not allowed")

    for token, ok in found_must.items():
        if not ok:
            errors.append(f"Core product source must still contain {token!r}")
    return errors


def main() -> int:
    errors = check()
    if errors:
        print("edition grep gate FAILED:")
        for err in errors:
            print(f"  {err}")
        return 1
    print("edition grep gate OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
