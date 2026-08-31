"""Site comments knob: default off, migrate visible threads, ingest gate."""

from __future__ import annotations

import uuid
from pathlib import Path

import frontmatter
import httpx
import pytest


@pytest.fixture
def agent_token_factory(authed_client):
    import secrets

    def _create(scopes, *, site_id="default"):
        resp = authed_client.post(
            "/api/auth/keys",
            json={
                "name": f"cmt-knob-{secrets.token_hex(4)}",
                "scopes": scopes,
                "site_id": site_id,
            },
        )
        assert resp.status_code == 200, resp.text
        raw_key = resp.json()["key"]
        tok = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
        assert tok.status_code == 200, tok.text
        return tok.json()["access_token"]

    return _create


def _enable_comments(site_id: str = "default") -> None:
    from services.site_service import ensure_sites_initialized, update_site

    ensure_sites_initialized()
    update_site(site_id, comments_enabled=True)


def _seed_post(temp_data_root: Path, slug: str = "my-post", site_id: str = "default") -> str:
    path = temp_data_root / "content" / "sites" / site_id / slug / "index.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nname: Seed Post\nstatus: published\ncategory: blog\n---\nBody\n",
        encoding="utf-8",
    )
    return slug


def _write_comment_md(
    temp_data_root: Path,
    *,
    visibility: str,
    slug: str = "c-existing",
    post_slug: str = "hello",
    site_id: str = "default",
) -> Path:
    path = (
        temp_data_root
        / "content"
        / "sites"
        / site_id
        / post_slug
        / "comments"
        / f"{slug}.md"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            f"---\n"
            f"name: Existing\n"
            f"slug: {slug}\n"
            f"kind: comment\n"
            f"post_slug: {post_slug}\n"
            f"visibility: {visibility}\n"
            f"author_name: Reader\n"
            f"author_kind: public\n"
            f"source_type: form\n"
            f"received_at: 2026-08-01T12:00:00Z\n"
            f"---\n"
            f"Keep this file.\n"
        ),
        encoding="utf-8",
    )
    return path


def test_comment_ingest_rejected_when_disabled(client, temp_data_root: Path):
    from services.site_service import update_site

    update_site("default", comments_enabled=False)
    slug = _seed_post(temp_data_root, f"post-{uuid.uuid4().hex[:8]}")
    token = f"off{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/api/v1/feedback",
        json={
            "name": "Reader",
            "message": f"{token} should be refused",
            "kind": "comment",
            "parent_slug": slug,
        },
    )
    assert resp.status_code == 403, resp.text
    comments_dir = temp_data_root / "content" / "sites" / "default" / slug / "comments"
    assert not comments_dir.exists() or not list(comments_dir.glob("c-*.md"))


def test_contact_ingest_still_works_when_comments_off(client, temp_data_root: Path):
    token = f"contact{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/api/v1/feedback",
        json={"name": "Visitor", "message": f"{token} contact still ok", "kind": "contact"},
    )
    assert resp.status_code == 200, resp.text
    slug = resp.json()["slug"]
    assert slug.startswith("fb-")
    path = temp_data_root / "content" / "sites" / "default" / slug / "index.md"
    assert path.is_file()


def test_comment_ingest_ok_when_enabled(client, temp_data_root: Path):
    _enable_comments()
    _seed_post(temp_data_root)
    token = f"on{uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/api/v1/feedback",
        json={
            "name": "Reader",
            "message": f"{token} should land",
            "kind": "comment",
            "parent_slug": "my-post",
        },
    )
    assert resp.status_code == 200, resp.text
    slug = resp.json()["slug"]
    path = (
        temp_data_root
        / "content"
        / "sites"
        / "default"
        / "my-post"
        / "comments"
        / f"{slug}.md"
    )
    assert path.is_file()
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    assert dict(post.metadata)["visibility"] == "pending"


def test_mcp_create_comment_works_when_public_knob_off(
    authed_client, temp_data_root: Path
):
    from services.site_service import get_site, update_site

    update_site("default", comments_enabled=False)
    post = _seed_post(temp_data_root, f"recipe-{uuid.uuid4().hex[:8]}")
    assert get_site("default").comments_enabled is False

    minted = authed_client.post(
        "/api/auth/keys",
        json={
            "name": f"cmt-{uuid.uuid4().hex[:6]}",
            "scopes": ["read", "write:posts"],
            "site_id": "default",
        },
    )
    assert minted.status_code == 200, minted.text
    tok = authed_client.post(
        "/api/auth/token", json={"agent_key": minted.json()["key"]}
    )
    assert tok.status_code == 200, tok.text
    headers = {"Authorization": f"Bearer {tok.json()['access_token']}"}

    created = authed_client.post(
        "/api/v1/mcp/comments",
        json={"post_slug": post, "body": "Agent reply while public comments are off."},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    comment = created.json()["comment"]
    assert comment["visibility"] == "visible"
    path = (
        temp_data_root
        / "content"
        / "sites"
        / "default"
        / post
        / "comments"
        / f"{comment['slug']}.md"
    )
    assert path.is_file()


def test_migrate_visible_comments_enables(temp_data_root: Path):
    from services.site_service import (
        _load_raw,
        _save_raw,
        create_site,
        ensure_sites_initialized,
        get_site,
    )

    ensure_sites_initialized()
    sid = f"migon{uuid.uuid4().hex[:8]}"
    create_site(sid, "Migrate On")
    sites = _load_raw()
    for entry in sites:
        if entry.get("id") == sid:
            entry.pop("comments_enabled", None)
    _save_raw(sites)

    path = _write_comment_md(
        temp_data_root, visibility="visible", site_id=sid, post_slug="hello"
    )
    ensure_sites_initialized()
    assert get_site(sid).comments_enabled is True
    assert path.is_file()


def test_migrate_pending_only_stays_off(temp_data_root: Path):
    from services.site_service import (
        _load_raw,
        _save_raw,
        create_site,
        ensure_sites_initialized,
        get_site,
    )

    ensure_sites_initialized()
    sid = f"migoff{uuid.uuid4().hex[:8]}"
    create_site(sid, "Migrate Off")
    sites = _load_raw()
    for entry in sites:
        if entry.get("id") == sid:
            entry.pop("comments_enabled", None)
    _save_raw(sites)

    path = _write_comment_md(
        temp_data_root,
        visibility="pending",
        slug="c-pending",
        site_id=sid,
        post_slug="hello",
    )
    ensure_sites_initialized()
    assert get_site(sid).comments_enabled is False
    assert path.is_file()


def test_migrate_does_not_override_explicit_false(temp_data_root: Path):
    from services.site_service import create_site, ensure_sites_initialized, get_site, update_site

    ensure_sites_initialized()
    sid = f"migkeep{uuid.uuid4().hex[:8]}"
    create_site(sid, "Keep Off")
    update_site(sid, comments_enabled=False)
    path = _write_comment_md(
        temp_data_root, visibility="visible", slug="c-kept", site_id=sid
    )
    ensure_sites_initialized()
    assert get_site(sid).comments_enabled is False
    assert path.is_file()


def test_relay_skips_comments_when_off_and_still_writes_contact(
    authed_client, agent_token_factory, temp_data_root: Path, monkeypatch
):
    from services.site_service import update_site

    import secrets

    post = _seed_post(temp_data_root, f"relay-post-{uuid.uuid4().hex[:8]}")
    update_site(
        "default",
        comments_enabled=False,
        feedback_relay_url="http://relay.test",
        feedback_submission_key=secrets.token_hex(16),
        feedback_fetch_token=secrets.token_hex(32),
        feedback_relay_cursor="",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path.endswith("/fetch"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": 1,
                            "name": "Bob",
                            "message": "Please get in touch",
                            "kind": "contact",
                            "received_at": "2026-08-19T11:00:00Z",
                        },
                        {
                            "id": 2,
                            "name": "Alice",
                            "message": "Hello from the queue",
                            "parent_slug": post,
                            "kind": "comment",
                            "received_at": "2026-08-19T12:00:00Z",
                        },
                    ]
                },
            )
        if request.method == "POST" and request.url.path.endswith("/ack"):
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(404, json={"error": "unexpected"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    monkeypatch.setattr(
        "services.feedback_service.httpx.AsyncClient", client_factory
    )

    token = agent_token_factory(["read", "write"])
    resp = authed_client.post(
        "/api/v1/feedback/sync",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["written"] == 1
    contact_slug = data["slugs"][0]
    assert contact_slug.startswith("fb-")
    comments_dir = (
        temp_data_root / "content" / "sites" / "default" / post / "comments"
    )
    assert not comments_dir.exists() or not list(comments_dir.glob("c-*.md"))
    assert (
        temp_data_root / "content" / "sites" / "default" / contact_slug / "index.md"
    ).is_file()
    update_site("default", feedback_relay_cursor="")


def test_new_site_comments_enabled_false(authed_client):
    from services.site_service import create_site, ensure_sites_initialized, get_site

    ensure_sites_initialized()
    record = create_site("quietblog", "Quiet Blog")
    assert record.comments_enabled is False
    assert get_site("quietblog").comments_enabled is False
