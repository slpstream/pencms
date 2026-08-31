"""Session 3: MCP / v1 honor granular scopes; humans no longer bypass."""

from __future__ import annotations

import base64
import secrets
import uuid as uuidlib


def _slug(prefix: str) -> str:
    return f"{prefix}-{uuidlib.uuid4().hex[:10]}"


def _mint(authed_client, scopes, site_id: str = "default") -> str:
    resp = authed_client.post(
        "/api/auth/keys",
        json={
            "name": f"s3-{secrets.token_hex(4)}",
            "scopes": scopes,
            "site_id": site_id,
        },
    )
    assert resp.status_code == 200, resp.text
    tok = authed_client.post("/api/auth/token", json={"agent_key": resp.json()["key"]})
    assert tok.status_code == 200, tok.text
    return tok.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _post_fm(name: str, *, page: bool = False) -> dict:
    fm = {"name": name, "status": "draft", "published": False}
    if page:
        fm["page"] = True
        fm["hero_title"] = name
    else:
        fm["category"] = "general"
    return fm


def test_write_posts_only_cannot_theme_menus_publish_or_pages(authed_client):
    token = _mint(authed_client, ["read", "write:posts"])
    headers = _headers(token)
    slug = _slug("s3-post")

    written = authed_client.put(
        f"/api/v1/mcp/pages/{slug}",
        json={"frontmatter": _post_fm("Posts Only"), "body": "ok"},
        headers=headers,
    )
    assert written.status_code == 200, written.text

    created = authed_client.post(
        "/api/v1/mcp/posts",
        json={"name": f"Stub {slug}"},
        headers=headers,
    )
    assert created.status_code == 200, created.text

    page_slug = _slug("s3-page")
    as_page = authed_client.put(
        f"/api/v1/mcp/pages/{page_slug}",
        json={"frontmatter": _post_fm("Nope Page", page=True), "body": "nope"},
        headers=headers,
    )
    assert as_page.status_code == 403, as_page.text
    assert "write:pages" in as_page.json()["detail"]

    flip = authed_client.put(
        f"/api/v1/mcp/pages/{slug}",
        json={"frontmatter": _post_fm("Flip", page=True), "body": "flip"},
        headers=headers,
    )
    assert flip.status_code == 403, flip.text
    assert flip.json()["detail"] == "cannot_change_page_kind"

    menu = authed_client.post(
        "/api/v1/mcp/menus/primary/items",
        json={
            "menu": "primary",
            "label": "Denied",
            "target": {"type": "custom", "url": "https://example.com"},
        },
        headers=headers,
    )
    assert menu.status_code == 403, menu.text
    assert "write:menus" in menu.json()["detail"]

    # MCP theme fork is Pro; Core REST customize still requires write:theme.
    theme = authed_client.post(
        "/api/sites/default/theme/fork", json={"parent": "basekit"}, headers=headers
    )
    assert theme.status_code == 403, theme.text
    assert "write:theme" in theme.json()["detail"]

    tax = authed_client.put(
        "/api/v1/mcp/taxonomy",
        json={
            "primary_vocabulary": "topics",
            "vocabularies": {"topics": {"label": "Topics", "terms": ["News"]}},
        },
        headers=headers,
    )
    assert tax.status_code == 403, tax.text
    assert "write:taxonomy" in tax.json()["detail"]

    deploy = authed_client.post("/api/v1/mcp/publish_site", headers=headers)
    assert deploy.status_code == 403, deploy.text
    assert "publish" in deploy.json()["detail"]

    git = authed_client.post(
        "/api/v1/mcp/publish",
        json={"message": "should fail", "dry_run": True},
        headers=headers,
    )
    assert git.status_code == 403, git.text
    assert "lacks required scope: write" in git.json()["detail"]


def test_legacy_write_expands_except_host_publish(authed_client):
    token = _mint(authed_client, ["read", "write"])
    headers = _headers(token)
    slug = _slug("s3-legacy")

    written = authed_client.put(
        f"/api/v1/mcp/pages/{slug}",
        json={"frontmatter": _post_fm("Legacy Write"), "body": "ok"},
        headers=headers,
    )
    assert written.status_code == 200, written.text

    menu = authed_client.post(
        "/api/v1/mcp/menus/primary/items",
        json={
            "menu": "primary",
            "label": "Legacy",
            "target": {"type": "custom", "url": "https://example.com/legacy"},
        },
        headers=headers,
    )
    assert menu.status_code == 201, menu.text

    seo = authed_client.patch(
        "/api/v1/mcp/site-presentation",
        json={"sitename": f"Legacy {slug}"},
        headers=headers,
    )
    assert seo.status_code == 200, seo.text

    theme = authed_client.post(
        "/api/sites/default/theme/fork", json={"parent": "basekit"}, headers=headers
    )
    assert theme.status_code != 403, theme.text

    tax = authed_client.put(
        "/api/v1/mcp/taxonomy",
        json={
            "primary_vocabulary": "topics",
            "vocabularies": {"topics": {"label": "Topics", "terms": ["News"]}},
        },
        headers=headers,
    )
    assert tax.status_code == 200, tax.text
    import config
    import yaml
    from services.site_service import _empty_taxonomy_dict

    tax_path = config.CONTENT_DIR_PATH / "sites" / "default" / "taxonomy.yaml"
    tax_path.write_text(
        yaml.safe_dump(_empty_taxonomy_dict(), default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    config.invalidate_taxonomy_cache("default")

    deploy = authed_client.post("/api/v1/mcp/publish_site", headers=headers)
    assert deploy.status_code == 403, deploy.text
    assert "publish" in deploy.json()["detail"]


def test_granular_keys_succeed_on_their_tools(authed_client):
    pages = _mint(authed_client, ["read", "write:pages"])
    page_slug = _slug("s3-static")
    page_ok = authed_client.put(
        f"/api/v1/mcp/pages/{page_slug}",
        json={"frontmatter": _post_fm("Static", page=True), "body": "page"},
        headers=_headers(pages),
    )
    assert page_ok.status_code == 200, page_ok.text

    post_denied = authed_client.put(
        f"/api/v1/mcp/pages/{_slug('s3-not-post')}",
        json={"frontmatter": _post_fm("Not a page"), "body": "nope"},
        headers=_headers(pages),
    )
    assert post_denied.status_code == 403, post_denied.text
    assert "write:posts" in post_denied.json()["detail"]

    menus = _mint(authed_client, ["read", "write:menus"])
    menu_ok = authed_client.post(
        "/api/v1/mcp/menus/primary/items",
        json={
            "menu": "primary",
            "label": "Granular",
            "target": {"type": "custom", "url": "https://example.com/g"},
        },
        headers=_headers(menus),
    )
    assert menu_ok.status_code == 201, menu_ok.text

    authors = _mint(authed_client, ["read", "write:authors"])
    author_ok = authed_client.post(
        "/api/v1/mcp/authors",
        json={"name": f"S3 Author {secrets.token_hex(3)}", "bio": "Bio"},
        headers=_headers(authors),
    )
    assert author_ok.status_code == 201, author_ok.text

    seo = _mint(authed_client, ["read", "write:seo"])
    seo_ok = authed_client.patch(
        "/api/v1/mcp/site-presentation",
        json={"tagline": "granular seo"},
        headers=_headers(seo),
    )
    assert seo_ok.status_code == 200, seo_ok.text

    media = _mint(authed_client, ["read", "write:media"])
    media_ok = authed_client.post(
        "/api/v1/mcp/media",
        json={
            "filename": f"s3-{secrets.token_hex(3)}.txt",
            "content_base64": base64.b64encode(b"hi").decode("utf-8"),
        },
        headers=_headers(media),
    )
    assert media_ok.status_code == 200, media_ok.text

    theme = _mint(authed_client, ["read", "write:theme"])
    theme_ok = authed_client.post(
        "/api/sites/default/theme/fork",
        json={"parent": "basekit"},
        headers=_headers(theme),
    )
    assert theme_ok.status_code != 403, theme_ok.text


def test_human_session_no_longer_bypasses_mcp(authed_client, login_author):
    login_author(capabilities=["write:posts"], username="s3human")
    slug = _slug("s3-human-post")
    written = authed_client.put(
        f"/api/v1/mcp/pages/{slug}",
        json={"frontmatter": _post_fm("Human Post"), "body": "ok"},
    )
    assert written.status_code == 200, written.text

    menu = authed_client.post(
        "/api/v1/mcp/menus/primary/items",
        json={
            "menu": "primary",
            "label": "Human Denied",
            "target": {"type": "custom", "url": "https://example.com/h"},
        },
    )
    assert menu.status_code == 403, menu.text
    assert menu.json()["detail"] == "missing_capability: write:menus"

    theme = authed_client.post(
        "/api/sites/default/theme/fork", json={"parent": "basekit"}
    )
    assert theme.status_code == 403, theme.text
    assert theme.json()["detail"] == "missing_capability: write:theme"


def test_v1_save_and_delete_honor_posts_vs_pages(authed_client, login_author):
    token = _mint(authed_client, ["read", "write:posts", "delete:posts"])
    headers = _headers(token)
    slug = _slug("s3-v1-post")
    saved = authed_client.put(
        f"/api/v1/content/collections/general/entries/{slug}",
        json={"frontmatter": _post_fm("V1 Post"), "body": "ok"},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text

    page_slug = _slug("s3-v1-page")
    as_page = authed_client.put(
        f"/api/v1/content/collections/general/entries/{page_slug}",
        json={"frontmatter": _post_fm("V1 Page", page=True), "body": "nope"},
        headers=headers,
    )
    assert as_page.status_code == 403, as_page.text
    assert "write:pages" in as_page.json()["detail"]

    deleted = authed_client.delete(
        f"/api/v1/content/collections/general/entries/{slug}",
        headers=headers,
    )
    assert deleted.status_code == 200, deleted.text

    login_author(capabilities=["write:posts"], username="s3v1human")
    human_slug = _slug("s3-v1-human")
    human_ok = authed_client.put(
        f"/api/v1/content/collections/general/entries/{human_slug}",
        json={"frontmatter": _post_fm("Human V1"), "body": "ok"},
    )
    assert human_ok.status_code == 200, human_ok.text

    human_page = authed_client.put(
        f"/api/v1/content/collections/general/entries/{_slug('s3-v1-hpage')}",
        json={"frontmatter": _post_fm("Human Page", page=True), "body": "nope"},
    )
    assert human_page.status_code == 403, human_page.text
    assert human_page.json()["detail"] == "missing_capability: write:pages"
