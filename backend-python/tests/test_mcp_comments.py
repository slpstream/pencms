"""MCP comment tools: agent list/create/moderate. Public GET stays visible-only."""

from __future__ import annotations

import secrets
import uuid
from pathlib import Path
from typing import Optional

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


def _seed_post(
    temp_data_root: Path, slug: Optional[str] = None, site_id: str = "default"
) -> str:
    post_slug = slug or f"post{uuid.uuid4().hex[:10]}"
    path = _stub_path(temp_data_root, site_id, post_slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nname: Seed Post\nstatus: published\ncategory: blog\n---\nBody\n",
        encoding="utf-8",
    )
    return post_slug


def _write_comment_file(
    temp_data_root: Path,
    *,
    post_slug: str,
    comment_slug: str,
    body: str,
    visibility: str,
    received_at: str,
    author_name: str = "Reader",
    site_id: str = "default",
    in_reply_to: Optional[str] = None,
) -> Path:
    path = _comment_path(temp_data_root, site_id, post_slug, comment_slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    reply = "null" if not in_reply_to else in_reply_to
    path.write_text(
        (
            f"---\n"
            f"name: {body.split()[0] if body.split() else 'Comment'}\n"
            f"slug: {comment_slug}\n"
            f"kind: comment\n"
            f"post_slug: {post_slug}\n"
            f"in_reply_to: {reply}\n"
            f"visibility: {visibility}\n"
            f"author_name: {author_name}\n"
            f"author_kind: public\n"
            f"agent_key_name: null\n"
            f"source_type: form\n"
            f"received_at: {received_at}\n"
            f"---\n"
            f"{body}\n"
        ),
        encoding="utf-8",
    )
    return path


def _mint_agent(authed_client, scopes, *, name=None, site_id="default") -> str:
    resp = authed_client.post(
        "/api/auth/keys",
        json={
            "name": name or f"mcp-cmt-{secrets.token_hex(4)}",
            "scopes": scopes,
            "site_id": site_id,
        },
    )
    assert resp.status_code == 200, resp.text
    raw_key = resp.json()["key"]
    tok = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
    assert tok.status_code == 200, tok.text
    return tok.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _mcp_list(client, post_slug: Optional[str] = None, **kwargs):
    params = kwargs.pop("params", {})
    if post_slug is not None:
        params["post_slug"] = post_slug
    return client.get("/api/v1/mcp/comments", params=params, **kwargs)


def _public_list(client, post_slug: str, **kwargs):
    return client.get(
        "/api/v1/comments", params={"post_slug": post_slug}, **kwargs
    )


def test_unauthenticated_mcp_comment_endpoints_rejected(client, temp_data_root: Path):
    post = _seed_post(temp_data_root, "needs-auth")
    assert _mcp_list(client, post).status_code == 401
    assert (
        client.post(
            "/api/v1/mcp/comments",
            json={"post_slug": post, "body": "Hi"},
        ).status_code
        == 401
    )
    assert (
        client.patch(
            "/api/v1/mcp/comments/c-nope",
            json={"visibility": "visible", "post_slug": post},
        ).status_code
        == 401
    )
    assert (
        client.delete(
            "/api/v1/mcp/comments/c-nope",
            params={"post_slug": post},
        ).status_code
        == 401
    )


def test_read_lists_pending_public_get_stays_leak_free(
    authed_client, temp_data_root: Path
):
    post = _seed_post(temp_data_root, f"mcp-list-{uuid.uuid4().hex[:8]}")
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150000z-pending",
        body="Grandmother just submitted this.",
        visibility="pending",
        received_at="2026-08-20T15:00:00Z",
        author_name="Grandmother",
    )
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t151000z-hidden",
        body="This was hidden.",
        visibility="hidden",
        received_at="2026-08-20T15:10:00Z",
    )
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t152000z-visible",
        body="The lemon frosting is perfect.",
        visibility="visible",
        received_at="2026-08-20T15:20:00Z",
        author_name="Ada",
    )

    token = _mint_agent(authed_client, ["read"])
    listed = _mcp_list(authed_client, post, headers=_headers(token))
    assert listed.status_code == 200, listed.text
    data = listed.json()
    assert data["post_slug"] == post
    slugs = [row["slug"] for row in data["comments"]]
    assert slugs == [
        "c-20260820t150000z-pending",
        "c-20260820t151000z-hidden",
        "c-20260820t152000z-visible",
    ]
    pending = data["comments"][0]
    assert pending["visibility"] == "pending"
    assert pending["author_name"] == "Grandmother"
    assert pending["body"] == "Grandmother just submitted this."
    assert pending["source_type"] == "form"
    assert pending["agent_key_name"] is None
    assert "email" not in pending

    visible_only = _mcp_list(
        authed_client,
        post,
        headers=_headers(token),
        params={"visibility": "visible"},
    )
    assert visible_only.status_code == 200, visible_only.text
    vis_slugs = [row["slug"] for row in visible_only.json()["comments"]]
    assert vis_slugs == ["c-20260820t152000z-visible"]
    assert visible_only.json()["comments"][0]["visibility"] == "visible"

    public = _public_list(authed_client, post)
    assert public.status_code == 200, public.text
    public_rows = public.json()["comments"]
    assert [row["slug"] for row in public_rows] == ["c-20260820t152000z-visible"]
    assert "visibility" not in public_rows[0]
    assert "email" not in public_rows[0]
    assert "source_type" not in public_rows[0]
    assert "agent_key_name" not in public_rows[0]

    leaked = authed_client.get(
        "/api/v1/comments",
        params={"post_slug": post, "visibility": "pending"},
    )
    assert leaked.status_code == 200, leaked.text
    assert [row["slug"] for row in leaked.json()["comments"]] == [
        "c-20260820t152000z-visible"
    ]
    assert "visibility" not in leaked.json()["comments"][0]


def test_mcp_list_unknown_post_is_empty(authed_client):
    token = _mint_agent(authed_client, ["read"])
    resp = _mcp_list(
        authed_client, "no-such-post-xyz", headers=_headers(token)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["post_slug"] == "no-such-post-xyz"
    assert data["comments"] == []


def test_mcp_list_missing_post_slug_is_400(authed_client):
    token = _mint_agent(authed_client, ["read"])
    headers = _headers(token)
    resp = _mcp_list(authed_client, headers=headers)
    assert resp.status_code == 400, resp.text
    blank = _mcp_list(authed_client, "   ", headers=headers)
    assert blank.status_code == 400, blank.text


def test_agent_create_comment_is_visible_on_public_get(
    authed_client, temp_data_root: Path
):
    post = _seed_post(temp_data_root, "recipe")
    token = _mint_agent(
        authed_client, ["read", "write:posts"], name="jeanie"
    )
    headers = _headers(token)

    created = authed_client.post(
        "/api/v1/mcp/comments",
        json={"post_slug": post, "body": "Try the lemon frosting."},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    comment = created.json()["comment"]
    assert comment["visibility"] == "visible"
    assert comment["author_kind"] == "agent"
    assert comment["source_type"] == "mcp"
    assert comment["agent_key_name"] == "jeanie"
    assert comment["author_name"] == "jeanie"
    assert comment["body"] == "Try the lemon frosting."
    assert comment["in_reply_to"] is None
    slug = comment["slug"]
    assert slug.startswith("c-")

    path = _comment_path(temp_data_root, "default", post, slug)
    yaml_text = path.read_text(encoding="utf-8")
    assert "visibility: visible" in yaml_text
    assert "author_kind: agent" in yaml_text
    assert "source_type: mcp" in yaml_text
    assert "agent_key_name: jeanie" in yaml_text

    public = _public_list(authed_client, post)
    assert public.status_code == 200, public.text
    rows = public.json()["comments"]
    assert [row["body"] for row in rows] == ["Try the lemon frosting."]
    assert rows[0]["author_kind"] == "agent"
    assert rows[0]["author_name"] == "jeanie"
    assert "visibility" not in rows[0]
    public_path = created.json()["public_path"]
    assert public_path == (
        f"/blog/post.php?slug={post}&section=blog&site=default#{slug}"
    )


def test_create_comment_public_path_is_null_when_post_is_draft(
    authed_client, temp_data_root: Path
):
    post = "draft-recipe"
    path = _stub_path(temp_data_root, "default", post)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nname: Draft Recipe\nstatus: draft\ncategory: blog\n---\nBody\n",
        encoding="utf-8",
    )
    token = _mint_agent(authed_client, ["read", "write:posts"], name="jeanie")
    created = authed_client.post(
        "/api/v1/mcp/comments",
        json={"post_slug": post, "body": "Not on the public site yet."},
        headers=_headers(token),
    )
    assert created.status_code == 200, created.text
    assert created.json()["public_path"] is None


def test_public_path_if_live_skips_pages():
    from services.house_url_service import public_path_if_live

    assert (
        public_path_if_live(
            "wiki",
            "about",
            {"status": "published", "page": True, "category": "pages"},
        )
        is None
    )
    dre = "dr-dre-embraces-ai-in-music-production-and-calls-critics-people-who-have-trouble-creating"
    comment = "c-20260824t211245z-youre-definitely-not-alone-dr-dres"
    assert public_path_if_live(
        "wiki",
        dre,
        {"status": "published", "category": "history"},
        comment_slug=comment,
    ) == f"/blog/post.php?slug={dre}&section=history&site=wiki#{comment}"


def test_public_path_if_live_skips_pages():
    from services.house_url_service import public_path_if_live

    assert (
        public_path_if_live(
            "wiki",
            "about",
            {"status": "published", "page": True, "category": "pages"},
        )
        is None
    )
    assert (
        public_path_if_live(
            "wiki",
            "dr-dre-embraces-ai-in-music-production-and-calls-critics-people-who-have-trouble-creating",
            {"status": "published", "category": "history"},
            comment_slug="c-20260824t211245z-youre-definitely-not-alone-dr-dres",
        )
        == (
            "/blog/post.php?slug=dr-dre-embraces-ai-in-music-production-and-calls-critics-people-who-have-trouble-creating"
            "&section=history&site=wiki#c-20260824t211245z-youre-definitely-not-alone-dr-dres"
        )
    )


def test_write_posts_required_for_create_and_set_visibility(
    authed_client, temp_data_root: Path
):
    post = _seed_post(temp_data_root, "cap-write")
    path = _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150000z-pending",
        body="Needs a writer.",
        visibility="pending",
        received_at="2026-08-20T15:00:00Z",
    )
    read_token = _mint_agent(authed_client, ["read"])
    headers = _headers(read_token)

    created = authed_client.post(
        "/api/v1/mcp/comments",
        json={"post_slug": post, "body": "Nope."},
        headers=headers,
    )
    assert created.status_code == 403, created.text
    assert "write:posts" in created.json()["detail"]

    patched = authed_client.patch(
        "/api/v1/mcp/comments/c-20260820t150000z-pending",
        json={"visibility": "visible", "post_slug": post},
        headers=headers,
    )
    assert patched.status_code == 403, patched.text
    assert "write:posts" in patched.json()["detail"]
    assert "visibility: pending" in path.read_text(encoding="utf-8")


def test_delete_posts_required_for_delete(authed_client, temp_data_root: Path):
    post = _seed_post(temp_data_root, "cap-delete")
    path = _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150000z-pending",
        body="Writer cannot delete.",
        visibility="pending",
        received_at="2026-08-20T15:00:00Z",
    )
    writer = _mint_agent(authed_client, ["read", "write:posts"])
    deleted = authed_client.delete(
        "/api/v1/mcp/comments/c-20260820t150000z-pending",
        params={"post_slug": post},
        headers=_headers(writer),
    )
    assert deleted.status_code == 403, deleted.text
    assert "delete:posts" in deleted.json()["detail"]
    assert path.exists()

    deleter = _mint_agent(authed_client, ["read", "delete:posts"])
    ok = authed_client.delete(
        "/api/v1/mcp/comments/c-20260820t150000z-pending",
        params={"post_slug": post},
        headers=_headers(deleter),
    )
    assert ok.status_code == 204, ok.text
    assert not path.exists()


def test_set_comment_visibility_then_public_get(
    authed_client, temp_data_root: Path
):
    post = _seed_post(temp_data_root, "approve-me")
    path = _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150000z-frosting",
        body="The lemon frosting is perfect.",
        visibility="pending",
        received_at="2026-08-20T15:00:00Z",
        author_name="Grandmother",
    )
    token = _mint_agent(authed_client, ["read", "write:posts"])
    headers = _headers(token)

    assert "The lemon frosting is perfect." not in [
        row["body"] for row in _public_list(authed_client, post).json()["comments"]
    ]

    resp = authed_client.patch(
        "/api/v1/mcp/comments/c-20260820t150000z-frosting",
        json={"visibility": "visible", "post_slug": post},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    comment = resp.json()["comment"]
    assert comment["visibility"] == "visible"
    assert comment["slug"] == "c-20260820t150000z-frosting"
    assert "visibility: visible" in path.read_text(encoding="utf-8")

    public = _public_list(authed_client, post)
    assert [row["body"] for row in public.json()["comments"]] == [
        "The lemon frosting is perfect."
    ]
    assert "visibility" not in public.json()["comments"][0]


def test_create_unknown_post_slug_is_400(authed_client):
    token = _mint_agent(authed_client, ["read", "write:posts"])
    resp = authed_client.post(
        "/api/v1/mcp/comments",
        json={"post_slug": "no-such-post-xyz", "body": "Orphan."},
        headers=_headers(token),
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == "Unknown post_slug"


def test_set_and_delete_unknown_comment_is_404(
    authed_client, temp_data_root: Path
):
    post = _seed_post(temp_data_root, "missing-cmt")
    writer = _mint_agent(authed_client, ["read", "write:posts"])
    patched = authed_client.patch(
        "/api/v1/mcp/comments/c-20260820t150000z-nope",
        json={"visibility": "visible", "post_slug": post},
        headers=_headers(writer),
    )
    assert patched.status_code == 404, patched.text

    deleter = _mint_agent(authed_client, ["read", "delete:posts"])
    deleted = authed_client.delete(
        "/api/v1/mcp/comments/c-20260820t150000z-nope",
        params={"post_slug": post},
        headers=_headers(deleter),
    )
    assert deleted.status_code == 404, deleted.text


def test_invalid_in_reply_to_is_400(authed_client, temp_data_root: Path):
    post = _seed_post(temp_data_root, "replies")
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150000z-top",
        body="Top level.",
        visibility="visible",
        received_at="2026-08-20T15:00:00Z",
    )
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t151000z-reply",
        body="One hop.",
        visibility="visible",
        received_at="2026-08-20T15:10:00Z",
        in_reply_to="c-20260820t150000z-top",
    )
    token = _mint_agent(authed_client, ["read", "write:posts"])
    headers = _headers(token)

    missing = authed_client.post(
        "/api/v1/mcp/comments",
        json={
            "post_slug": post,
            "body": "Ghost parent.",
            "in_reply_to": "c-does-not-exist",
        },
        headers=headers,
    )
    assert missing.status_code == 400, missing.text
    assert "in_reply_to" in str(missing.json()["detail"])

    nested = authed_client.post(
        "/api/v1/mcp/comments",
        json={
            "post_slug": post,
            "body": "Two hops.",
            "in_reply_to": "c-20260820t151000z-reply",
        },
        headers=headers,
    )
    assert nested.status_code == 400, nested.text
    assert "one level" in str(nested.json()["detail"]).lower()


def test_agent_jwt_site_is_authoritative(authed_client, temp_data_root: Path):
    from services.site_service import create_site, ensure_sites_initialized

    ensure_sites_initialized()
    other_id = f"mcp{uuid.uuid4().hex[:8]}"
    create_site(other_id, "Other MCP Site")

    post_slug = f"shared-mcp-{uuid.uuid4().hex[:8]}"
    default_post = _seed_post(temp_data_root, post_slug, site_id="default")
    other_post = _seed_post(temp_data_root, post_slug, site_id=other_id)
    assert default_post == other_post == post_slug

    _write_comment_file(
        temp_data_root,
        post_slug=post_slug,
        comment_slug="c-20260820t180000z-default",
        body="On default.",
        visibility="pending",
        received_at="2026-08-20T18:00:00Z",
        site_id="default",
    )
    _write_comment_file(
        temp_data_root,
        post_slug=post_slug,
        comment_slug="c-20260820t181000z-other",
        body="On other.",
        visibility="pending",
        received_at="2026-08-20T18:10:00Z",
        site_id=other_id,
    )

    default_token = _mint_agent(authed_client, ["read", "write:posts"])
    default_headers = _headers(default_token)
    default_headers["X-Pen-Site-Id"] = other_id

    listed = _mcp_list(
        authed_client, post_slug, headers=default_headers
    )
    assert listed.status_code == 200, listed.text
    slugs = [row["slug"] for row in listed.json()["comments"]]
    assert slugs == ["c-20260820t180000z-default"]

    created = authed_client.post(
        "/api/v1/mcp/comments",
        json={"post_slug": post_slug, "body": "Default only."},
        headers=default_headers,
    )
    assert created.status_code == 200, created.text
    new_slug = created.json()["comment"]["slug"]
    assert _comment_path(temp_data_root, "default", post_slug, new_slug).exists()
    assert not _comment_path(temp_data_root, other_id, post_slug, new_slug).exists()

    other_token = _mint_agent(
        authed_client, ["read"], site_id=other_id
    )
    other_listed = _mcp_list(
        authed_client, post_slug, headers=_headers(other_token)
    )
    assert other_listed.status_code == 200, other_listed.text
    other_slugs = [row["slug"] for row in other_listed.json()["comments"]]
    assert other_slugs == ["c-20260820t181000z-other"]


def test_mcp_comment_tools_registered_in_openapi(client):
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths", {})

    assert "/api/v1/mcp/comments" in paths
    assert "/api/v1/mcp/comments/{comment_slug}" in paths

    listed = paths["/api/v1/mcp/comments"]["get"]
    assert "mcp" in listed["tags"]
    assert listed.get("operationId") == "list_comments"
    assert paths["/api/v1/mcp/comments"]["post"].get("operationId") == "create_comment"
    patched = paths["/api/v1/mcp/comments/{comment_slug}"]["patch"]
    deleted = paths["/api/v1/mcp/comments/{comment_slug}"]["delete"]
    assert patched.get("operationId") == "set_comment_visibility"
    assert deleted.get("operationId") == "delete_comment"
    assert "mcp" in patched["tags"]
    assert "mcp" in deleted["tags"]

    admin_list = paths["/api/v1/admin/comments"]["get"]
    assert "admin" in admin_list["tags"]
    assert "mcp" not in admin_list["tags"]


def test_core_openapi_documents_mcp_comments():
    spec = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "core" / "openapi.yaml").read_text(
            encoding="utf-8"
        )
    )
    listed = spec["paths"]["/mcp/comments"]["get"]
    assert listed.get("security")
    params = {p["name"]: p for p in listed["parameters"]}
    assert params["post_slug"]["required"] is True
    created = spec["paths"]["/mcp/comments"]["post"]
    assert created.get("operationId") == "create_comment"
    patched = spec["paths"]["/mcp/comments/{comment_slug}"]["patch"]
    deleted = spec["paths"]["/mcp/comments/{comment_slug}"]["delete"]
    assert patched.get("operationId") == "set_comment_visibility"
    assert deleted.get("operationId") == "delete_comment"
    public = spec["components"]["schemas"]["PublicComment"]
    assert "visibility" not in public["properties"]
    assert "email" not in public["properties"]
    create_body = spec["components"]["schemas"]["CreateComment"]
    assert "post_slug" in create_body["required"]
    assert "body" in create_body["required"]
    assert "email" not in create_body.get("properties", {})
