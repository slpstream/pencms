"""Feedback ingest v1 poll client: POST /api/v1/feedback/sync + MCP tool."""

from __future__ import annotations

import json
import secrets
from pathlib import Path

import frontmatter
import httpx
import pytest
import yaml


def _stub_path(temp_data_root: Path, site_id: str, slug: str) -> Path:
    return temp_data_root / "content" / "sites" / site_id / slug / "index.md"


def _comment_path(
    temp_data_root: Path, site_id: str, post_slug: str, comment_slug: str
) -> Path:
    return (
        temp_data_root
        / "content"
        / "sites"
        / site_id
        / post_slug
        / "comments"
        / f"{comment_slug}.md"
    )


def _seed_post(temp_data_root: Path, slug: str = "my-post") -> str:
    path = _stub_path(temp_data_root, "default", slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nname: Seed Post\nstatus: published\ncategory: blog\n---\nBody\n",
        encoding="utf-8",
    )
    return slug


@pytest.fixture(autouse=True)
def _clear_relay_site_fields():
    from services.site_service import get_site, update_site

    yield
    if get_site("default") is None:
        return
    update_site(
        "default",
        feedback_relay_url="",
        feedback_submission_key="",
        feedback_fetch_token="",
        feedback_relay_cursor="",
    )


@pytest.fixture
def agent_token_factory(authed_client):
    def _create(scopes, *, site_id="default"):
        resp = authed_client.post(
            "/api/auth/keys",
            json={
                "name": f"fb-{secrets.token_hex(4)}",
                "scopes": scopes,
                "site_id": site_id,
            },
        )
        assert resp.status_code == 200, resp.text
        raw_key = resp.json()["key"]
        resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    return _create


def _set_relay_keys(
    *,
    submission_key=None,
    fetch_token=None,
    relay_url="http://relay.test",
    cursor=None,
):
    from services.site_service import update_site

    kwargs = {
        "feedback_relay_url": relay_url,
        "feedback_submission_key": submission_key or secrets.token_hex(16),
        "feedback_fetch_token": fetch_token or secrets.token_hex(32),
    }
    if cursor is not None:
        kwargs["feedback_relay_cursor"] = cursor
    return update_site("default", **kwargs)


def _patch_async_client(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    monkeypatch.setattr(
        "services.feedback_service.httpx.AsyncClient", client_factory
    )
    return transport


def test_write_key_syncs_contact_and_comment_to_correct_trees(
    authed_client, agent_token_factory, temp_data_root: Path, monkeypatch
):
    site = _set_relay_keys()
    from services.site_service import update_site

    update_site("default", comments_enabled=True)
    _seed_post(temp_data_root, "my-post")
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "GET" and request.url.path.endswith("/fetch"):
            assert request.headers.get("Authorization") == (
                f"Bearer {site.feedback_fetch_token}"
            )
            assert request.url.params.get("submission_key") == site.feedback_submission_key
            assert request.url.params.get("since") == "0"
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": 40,
                            "name": "Bob",
                            "message": "Please get in touch",
                            "email": "bob@example.com",
                            "kind": "contact",
                            "received_at": "2026-08-19T11:00:00Z",
                        },
                        {
                            "id": 42,
                            "name": "Alice",
                            "message": "Hello from the relay queue",
                            "email": "alice@example.com",
                            "source_url": "https://example.com/my-post",
                            "parent_slug": "my-post",
                            "kind": "comment",
                            "received_at": "2026-08-19T12:00:00Z",
                        },
                        {
                            "id": 43,
                            "name": "Eve",
                            "message": "Orphan comment should skip",
                            "parent_slug": "no-such-post",
                            "kind": "comment",
                            "received_at": "2026-08-19T13:00:00Z",
                        },
                    ]
                },
            )
        if request.method == "POST" and request.url.path.endswith("/ack"):
            body = json.loads(request.content.decode())
            assert body["submission_key"] == site.feedback_submission_key
            assert body["ids"] == [40, 42, 43]
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(404, json={"error": "unexpected"})

    _patch_async_client(monkeypatch, handler)
    token = agent_token_factory(["read", "write"])
    resp = authed_client.post(
        "/api/v1/feedback/sync",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["written"] == 2
    assert "reason" not in data
    slugs = data["slugs"]
    assert len(slugs) == 2
    contact_slug = next(s for s in slugs if s.startswith("fb-"))
    comment_slug = next(s for s in slugs if s.startswith("c-"))

    contact_path = _stub_path(temp_data_root, "default", contact_slug)
    assert contact_path.is_file()
    contact_fm = dict(frontmatter.loads(contact_path.read_text(encoding="utf-8")).metadata)
    assert contact_fm["kind"] == "contact"
    assert contact_fm["submitter"] == "Bob"
    assert contact_fm["source_type"] == "relay"
    assert contact_fm["status"] == "stub"
    assert contact_fm["email"] == "bob@example.com"

    comment_path = _comment_path(temp_data_root, "default", "my-post", comment_slug)
    assert comment_path.is_file()
    comment = frontmatter.loads(comment_path.read_text(encoding="utf-8"))
    comment_fm = dict(comment.metadata)
    assert comment_fm["author_name"] == "Alice"
    assert comment_fm["source_type"] == "relay"
    assert comment_fm["kind"] == "comment"
    assert comment_fm["post_slug"] == "my-post"
    assert comment_fm["visibility"] == "pending"
    assert comment_fm["author_kind"] == "public"
    assert comment_fm["received_at"] == "2026-08-19T12:00:00Z"
    assert "email" not in comment_fm
    assert comment.content.strip() == "Hello from the relay queue"

    orphan_dir = (
        temp_data_root / "content" / "sites" / "default" / "no-such-post" / "comments"
    )
    assert not orphan_dir.exists()
    assert ("GET", "/fetch") in calls
    assert ("POST", "/ack") in calls

    from services.site_service import get_site

    assert get_site("default").feedback_relay_cursor == "43"


def test_human_session_can_sync(authed_client, monkeypatch):
    _set_relay_keys()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"items": []})
        return httpx.Response(404)

    _patch_async_client(monkeypatch, handler)
    resp = authed_client.post("/api/v1/feedback/sync")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"written": 0, "slugs": []}


def test_no_relay_configured_is_not_500(authed_client, agent_token_factory):
    from services.site_service import update_site

    update_site(
        "default",
        feedback_submission_key="",
        feedback_fetch_token="",
    )
    token = agent_token_factory(["read", "write"])
    resp = authed_client.post(
        "/api/v1/feedback/sync",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"written": 0, "reason": "no_relay_configured"}


def test_relay_unreachable_on_http_error(
    authed_client, agent_token_factory, monkeypatch
):
    _set_relay_keys()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "down"})

    _patch_async_client(monkeypatch, handler)
    token = agent_token_factory(["read", "write"])
    resp = authed_client.post(
        "/api/v1/feedback/sync",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"written": 0, "reason": "relay_unreachable"}


def test_relay_unreachable_on_connect_error(
    authed_client, agent_token_factory, monkeypatch
):
    _set_relay_keys()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _patch_async_client(monkeypatch, handler)
    token = agent_token_factory(["read", "write"])
    resp = authed_client.post(
        "/api/v1/feedback/sync",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"written": 0, "reason": "relay_unreachable"}


def test_mcp_sync_remote_feedback_and_read_key_forbidden(
    authed_client, agent_token_factory, monkeypatch
):
    _set_relay_keys()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"items": []})
        return httpx.Response(404)

    _patch_async_client(monkeypatch, handler)

    read_token = agent_token_factory(["read"])
    denied = authed_client.post(
        "/api/v1/mcp/feedback/sync",
        headers={"Authorization": f"Bearer {read_token}"},
    )
    assert denied.status_code == 403, denied.text
    assert "lacks required scope: write" in denied.json()["detail"]

    rest_denied = authed_client.post(
        "/api/v1/feedback/sync",
        headers={"Authorization": f"Bearer {read_token}"},
    )
    assert rest_denied.status_code == 403, rest_denied.text
    assert "lacks required scope: write" in rest_denied.json()["detail"]

    write_token = agent_token_factory(["read", "write"])
    ok = authed_client.post(
        "/api/v1/mcp/feedback/sync",
        headers={"Authorization": f"Bearer {write_token}"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["written"] == 0


def test_unauthenticated_sync_is_401(client):
    assert client.post("/api/v1/feedback/sync").status_code == 401
    assert client.post("/api/v1/mcp/feedback/sync").status_code == 401


def test_mcp_tool_registered_in_openapi(client):
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths", {})
    route = paths["/api/v1/mcp/feedback/sync"]["post"]
    assert "mcp" in route["tags"]
    assert route.get("operationId") == "sync_remote_feedback"


def test_openapi_yaml_documents_feedback_sync():
    spec = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "core" / "openapi.yaml").read_text(
            encoding="utf-8"
        )
    )
    path = spec["paths"]["/feedback/sync"]["post"]
    assert path["security"]
    assert "200" in path["responses"]
    assert "403" in path["responses"]
    schema = spec["components"]["schemas"]["FeedbackSyncResult"]
    assert "written" in schema["properties"]
    assert schema["properties"]["reason"]["enum"] == [
        "no_relay_configured",
        "relay_unreachable",
    ]


@pytest.mark.asyncio
@pytest.mark.feedback_relay_http
async def test_ensure_feedback_relay_registers_raw_fetch_token(monkeypatch):
    from services.feedback_service import ensure_feedback_relay
    from services.site_service import get_site, update_site

    update_site(
        "default",
        feedback_submission_key="",
        feedback_fetch_token="",
    )
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/register"):
            seen["url"] = str(request.url)
            seen["body"] = json.loads(request.content.decode())
            return httpx.Response(200, json={"status": "registered"})
        return httpx.Response(404)

    _patch_async_client(monkeypatch, handler)
    record = await ensure_feedback_relay(
        "default", relay_url="http://relay.test"
    )
    assert record.feedback_submission_key
    assert len(record.feedback_submission_key) == 32
    assert record.feedback_fetch_token
    assert len(record.feedback_fetch_token) == 64
    assert seen["url"].startswith("http://relay.test/")
    assert seen["body"]["submission_key"] == record.feedback_submission_key
    assert seen["body"]["fetch_token_hash"] == record.feedback_fetch_token
    listed = get_site("default")
    assert listed.feedback_fetch_token == record.feedback_fetch_token


@pytest.mark.feedback_relay_http
def test_patch_empty_fetch_token_rotates_and_reregisters(
    authed_client, monkeypatch
):
    from services.site_service import get_site

    original = _set_relay_keys()
    old_token = original.feedback_fetch_token
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/register"):
            seen.append(json.loads(request.content.decode()))
            return httpx.Response(200, json={"status": "registered"})
        return httpx.Response(404)

    _patch_async_client(monkeypatch, handler)
    resp = authed_client.patch(
        "/api/sites/default",
        json={"feedback_fetch_token": ""},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "feedback_fetch_token" not in body
    assert body["has_feedback_fetch_token"] is True
    assert body["feedback_submission_key"] == original.feedback_submission_key

    updated = get_site("default")
    assert updated.feedback_fetch_token != old_token
    assert updated.feedback_submission_key == original.feedback_submission_key
    assert seen and seen[0]["fetch_token_hash"] == updated.feedback_fetch_token

    listed = authed_client.get("/api/sites").json()["sites"]
    default = next(s for s in listed if s["id"] == "default")
    assert "feedback_fetch_token" not in default
    assert default["has_feedback_fetch_token"] is True


def test_live_post_still_works_without_relay(client, temp_data_root: Path):
    resp = client.post(
        "/api/v1/feedback",
        json={"name": "Local", "message": "Direct ingest without a relay", "kind": "contact"},
    )
    assert resp.status_code == 200, resp.text
    slug = resp.json()["slug"]
    path = _stub_path(temp_data_root, "default", slug)
    fm = dict(frontmatter.loads(path.read_text(encoding="utf-8")).metadata)
    assert fm["source_type"] == "form"
    assert fm["submitter"] == "Local"


def test_create_site_mints_feedback_keys():
    from services.site_service import create_site, ensure_sites_initialized, get_site

    ensure_sites_initialized()
    record = create_site("inbox", "Inbox")
    assert record.feedback_submission_key
    assert len(record.feedback_submission_key) == 32
    assert record.feedback_fetch_token
    assert len(record.feedback_fetch_token) == 64
    stored = get_site("inbox")
    assert stored.feedback_submission_key == record.feedback_submission_key


def test_site_list_includes_relay_url_and_exposes_keys(authed_client):
    resp = authed_client.get("/api/sites")
    assert resp.status_code == 200, resp.text
    default = next(s for s in resp.json()["sites"] if s["id"] == "default")
    assert "feedback_relay_url" in default
    assert default["has_feedback_fetch_token"] is True
    assert default["feedback_submission_key"]
    assert len(default["feedback_submission_key"]) == 32


def test_empty_relay_url_resolves_to_default_origin():
    from services.site_service import (
        DEFAULT_FEEDBACK_RELAY_URL,
        SiteRecord,
        resolve_feedback_relay_url,
    )

    site = SiteRecord(id="x", name="X", content_relpath="sites/x")
    assert resolve_feedback_relay_url(site) == DEFAULT_FEEDBACK_RELAY_URL
    assert resolve_feedback_relay_url(site, url="") == DEFAULT_FEEDBACK_RELAY_URL
    assert (
        resolve_feedback_relay_url(site, url="https://relay.example.com/")
        == "https://relay.example.com"
    )
