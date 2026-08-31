"""Session 2: human REST honors site-scoped capabilities."""

from __future__ import annotations

import uuid as uuidlib

from services.edition import get_edition


def _slug(prefix: str) -> str:
    return f"{prefix}-{uuidlib.uuid4().hex[:10]}"


def _post_body(name: str, slug: str, *, page: bool = False, status: str = "draft") -> dict:
    fm = {
        "name": name,
        "status": status,
        "domain": "blog",
        "published": False,
    }
    if page:
        fm["page"] = True
        fm["hero_title"] = name
    else:
        fm["category"] = "general"
    return {"frontmatter": fm, "content": f"{name} body.", "slug": slug}


def test_write_posts_only_can_write_posts_not_pages_or_publish(authed_client, login_author):
    admin = authed_client
    page_slug = _slug("s2-existing-page")
    created_page = admin.post("/api/pages/", json=_post_body("Existing Page", page_slug, page=True))
    assert created_page.status_code == 201, created_page.text

    login_author(capabilities=["write:posts"])

    post_slug = _slug("s2-post")
    created = authed_client.post("/api/pages/", json=_post_body("Post Only", post_slug))
    assert created.status_code == 201, created.text

    updated = authed_client.put(
        f"/api/pages/{post_slug}",
        json=_post_body("Post Only Revised", post_slug),
    )
    assert updated.status_code == 200, updated.text

    as_page = authed_client.post(
        "/api/pages/",
        json=_post_body("Nope Page", _slug("s2-page-deny"), page=True),
    )
    assert as_page.status_code == 403, as_page.text
    assert as_page.json()["detail"] == "missing_capability: write:pages"

    put_existing_page = authed_client.put(
        f"/api/pages/{page_slug}",
        json=_post_body("Existing Page", page_slug, page=True),
    )
    assert put_existing_page.status_code == 403, put_existing_page.text
    assert put_existing_page.json()["detail"] == "missing_capability: write:pages"

    flip = authed_client.put(
        f"/api/pages/{post_slug}",
        json=_post_body("Flip Me", post_slug, page=True),
    )
    assert flip.status_code == 403, flip.text
    assert flip.json()["detail"] == "cannot_change_page_kind"

    approve = authed_client.patch(f"/api/pages/{post_slug}/approve")
    assert approve.status_code == 403, approve.text
    assert approve.json()["detail"] == "missing_capability: publish:content"

    publish = authed_client.patch(f"/api/pages/{post_slug}/publish")
    assert publish.status_code == 403, publish.text
    assert publish.json()["detail"] == "missing_capability: publish:content"

    menu = authed_client.post(
        "/api/menus/primary/items",
        json={
            "menu": "primary",
            "label": "Denied",
            "target": {"type": "custom", "url": "https://example.com"},
        },
    )
    assert menu.status_code == 403, menu.text
    assert menu.json()["detail"] == "missing_capability: write:menus"

    theme = authed_client.post(
        "/api/sites/default/theme/fork", json={"parent": "basekit"}
    )
    assert theme.status_code == 403, theme.text
    assert theme.json()["detail"] == "missing_capability: write:theme"

    deploy = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "sftp",
            "host": "example.com",
            "username": "deploy",
            "remote_path": "/var/www/html",
            "auth_method": "password",
        },
    )
    assert deploy.status_code == 403, deploy.text
    assert deploy.json()["detail"] == "missing_capability: publish"

    run = authed_client.post("/api/publish/run", json={"site": "default"})
    assert run.status_code == 403, run.text
    assert run.json()["detail"] == "missing_capability: publish"


def test_write_posts_plus_publish_content_can_approve_not_theme(authed_client, login_author):
    login_author(
        capabilities=["write:posts", "publish:content"],
        username="editor",
    )
    slug = _slug("s2-approve")
    created = authed_client.post("/api/pages/", json=_post_body("Needs Review", slug))
    assert created.status_code == 201, created.text

    approved = authed_client.patch(f"/api/pages/{slug}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["frontmatter"]["status"] == "published"
    assert approved.json()["frontmatter"]["published"] is True

    theme = authed_client.post(
        "/api/sites/default/theme/fork", json={"parent": "basekit"}
    )
    assert theme.status_code == 403, theme.text
    assert theme.json()["detail"] == "missing_capability: write:theme"


def test_write_pages_create_ok_delete_needs_delete_pages(authed_client, login_author):
    login_author(capabilities=["write:pages"], username="pager")
    slug = _slug("s2-static-page")
    created = authed_client.post(
        "/api/pages/", json=_post_body("Static", slug, page=True)
    )
    assert created.status_code == 201, created.text
    assert created.json()["frontmatter"].get("page") in (True, "true")

    denied = authed_client.delete(f"/api/pages/{slug}")
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"] == "missing_capability: delete:pages"

    login_author(
        capabilities=["write:pages", "delete:pages"],
        username="pager-del",
    )
    deleted = authed_client.delete(f"/api/pages/{slug}")
    assert deleted.status_code == 204, deleted.text


def test_write_menus_and_theme_and_publish_allowed_users(authed_client, login_author):
    login_author(capabilities=["write:menus"], username="nav")
    menu = authed_client.post(
        "/api/menus/primary/items",
        json={
            "menu": "primary",
            "label": "Allowed",
            "target": {"type": "custom", "url": "https://example.com/ok"},
        },
    )
    assert menu.status_code == 201, menu.text

    login_author(capabilities=["write:theme"], username="themer")
    context = authed_client.get("/api/sites/default/theme/context")
    assert context.status_code == 200, context.text

    login_author(capabilities=["publish"], username="publisher")
    target = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "sftp",
            "host": "example.com",
            "username": "deploy",
            "remote_path": "/var/www/html",
            "auth_method": "password",
        },
    )
    assert target.status_code == 200, target.text


def test_bootstrap_admin_still_has_full_access(authed_client):
    slug = _slug("s2-admin-post")
    created = authed_client.post("/api/pages/", json=_post_body("Admin Post", slug))
    assert created.status_code == 201, created.text

    page_slug = _slug("s2-admin-page")
    page = authed_client.post(
        "/api/pages/", json=_post_body("Admin Page", page_slug, page=True)
    )
    assert page.status_code == 201, page.text

    menu = authed_client.post(
        "/api/menus/footer/items",
        json={
            "menu": "footer",
            "label": "Admin Link",
            "target": {"type": "custom", "url": "https://example.com/admin"},
        },
    )
    assert menu.status_code == 201, menu.text

    seo = authed_client.patch(
        "/api/sites/default", json={"sitename": "Admin Sitename"}
    )
    assert seo.status_code == 200, seo.text

    target = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "sftp",
            "host": "admin.example.com",
            "username": "deploy",
            "remote_path": "/var/www/html",
            "auth_method": "password",
        },
    )
    assert target.status_code == 200, target.text

    listed = authed_client.get("/api/sites")
    assert listed.status_code == 200, listed.text
    assert any(s["id"] == "default" for s in listed.json()["sites"])


def test_write_seo_can_patch_presentation_not_registry(authed_client, login_author):
    login_author(capabilities=["write:seo"], username="seo")
    ok = authed_client.patch(
        "/api/sites/default", json={"sitename": "SEO Sitename"}
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["sitename"] == "SEO Sitename"

    og = authed_client.patch(
        "/api/sites/default", json={"twitter_card": "summary_large_image"}
    )
    assert og.status_code == 200, og.text

    denied = authed_client.patch(
        "/api/sites/default", json={"domain": "hijack.example"}
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"] == "missing_capability: manage:sites"

    mixed = authed_client.patch(
        "/api/sites/default",
        json={"sitename": "Still SEO", "domain": "nope.example"},
    )
    assert mixed.status_code == 403, mixed.text
    assert mixed.json()["detail"] == "missing_capability: manage:sites"

    create = authed_client.post(
        "/api/sites", json={"id": _slug("s2site").replace("-", "")[:16], "name": "Nope"}
    )
    if get_edition() == "pro":
        assert create.status_code == 403, create.text
        assert create.json()["detail"] == "missing_capability: manage:sites"
    else:
        assert create.status_code == 405, create.text

    # Author membership is on default; GET /api/sites includes that site.
    listed = authed_client.get("/api/sites")
    assert listed.status_code == 200, listed.text
    assert any(s["id"] == "default" for s in listed.json()["sites"])


def test_authenticated_get_pages_does_not_require_read(authed_client, login_author):
    login_author(capabilities=["write:posts"], username="readerless")
    listed = authed_client.get("/api/pages/")
    assert listed.status_code == 200, listed.text


def test_put_status_published_allowed_with_write_posts_only(authed_client, login_author):
    """Locked decision 6: generic PUT does not sniff status. PATCH approve/publish still need publish:content."""
    login_author(capabilities=["write:posts"], username=f"s8put{uuidlib.uuid4().hex[:8]}")
    slug = _slug("s8-put-status")
    created = authed_client.post("/api/pages/", json=_post_body("Draft Post", slug))
    assert created.status_code == 201, created.text
    assert created.json()["frontmatter"]["status"] == "draft"

    put_published = authed_client.put(
        f"/api/pages/{slug}",
        json=_post_body("Draft Post", slug, status="published"),
    )
    assert put_published.status_code == 200, put_published.text
    assert put_published.json()["frontmatter"]["status"] == "published"

    approve = authed_client.patch(f"/api/pages/{slug}/approve")
    assert approve.status_code == 403, approve.text
    assert approve.json()["detail"] == "missing_capability: publish:content"

    publish = authed_client.patch(f"/api/pages/{slug}/publish")
    assert publish.status_code == 403, publish.text
    assert publish.json()["detail"] == "missing_capability: publish:content"


def test_write_authors_mutation_gated(authed_client, login_author):
    login_author(capabilities=["write:posts"], username="no-bios")
    denied = authed_client.post("/api/authors/", json={"name": "Ada"})
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"] == "missing_capability: write:authors"

    login_author(capabilities=["write:authors"], username="bios")
    created = authed_client.post("/api/authors/", json={"name": "Ada Lovelace"})
    assert created.status_code == 201, created.text
