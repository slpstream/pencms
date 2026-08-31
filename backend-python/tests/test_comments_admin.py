"""Authenticated admin comment list / visibility / delete. Public GET stays visible-only."""

from __future__ import annotations

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


def _admin_list(client, post_slug: Optional[str] = None, **kwargs):
    params = {}
    if post_slug is not None:
        params["post_slug"] = post_slug
    return client.get("/api/v1/admin/comments", params=params, **kwargs)


def _public_list(client, post_slug: str, **kwargs):
    return client.get(
        "/api/v1/comments", params={"post_slug": post_slug}, **kwargs
    )


def test_unauthenticated_admin_routes_are_401(client, temp_data_root: Path):
    post = _seed_post(temp_data_root, "needs-auth")
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150000z-pending",
        body="Grandmother just submitted this.",
        visibility="pending",
        received_at="2026-08-20T15:00:00Z",
    )
    assert _admin_list(client, post).status_code == 401
    assert (
        client.patch(
            "/api/v1/admin/comments/c-20260820t150000z-pending",
            json={"visibility": "visible", "post_slug": post},
        ).status_code
        == 401
    )
    assert (
        client.delete(
            "/api/v1/admin/comments/c-20260820t150000z-pending",
            params={"post_slug": post},
        ).status_code
        == 401
    )


def test_write_posts_required_for_list_and_patch(
    authed_client, login_author, temp_data_root: Path
):
    post = _seed_post(temp_data_root, "cap-list")
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150000z-pending",
        body="Needs a writer.",
        visibility="pending",
        received_at="2026-08-20T15:00:00Z",
    )
    login_author(capabilities=["read"], username="reader-only")
    listed = _admin_list(authed_client, post)
    assert listed.status_code == 403, listed.text
    patched = authed_client.patch(
        "/api/v1/admin/comments/c-20260820t150000z-pending",
        json={"visibility": "visible", "post_slug": post},
    )
    assert patched.status_code == 403, patched.text


def test_delete_posts_required_for_delete(
    authed_client, login_author, temp_data_root: Path
):
    post = _seed_post(temp_data_root, "cap-delete")
    path = _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150000z-pending",
        body="Writer cannot delete.",
        visibility="pending",
        received_at="2026-08-20T15:00:00Z",
    )
    login_author(capabilities=["write:posts"], username="writer-no-delete")
    listed = _admin_list(authed_client, post)
    assert listed.status_code == 200, listed.text
    deleted = authed_client.delete(
        "/api/v1/admin/comments/c-20260820t150000z-pending",
        params={"post_slug": post},
    )
    assert deleted.status_code == 403, deleted.text
    assert path.exists()


def test_admin_list_includes_all_visibilities_pending_first(
    authed_client, temp_data_root: Path
):
    post = _seed_post(temp_data_root, f"cupcakes-{uuid.uuid4().hex[:8]}")
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t152000z-visible",
        body="The lemon frosting is perfect.",
        visibility="visible",
        received_at="2026-08-20T15:20:00Z",
        author_name="Ada",
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
        comment_slug="c-20260820t153000z-pending-later",
        body="Later pending.",
        visibility="pending",
        received_at="2026-08-20T15:30:00Z",
    )
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150000z-pending",
        body="Grandmother just submitted this.",
        visibility="pending",
        received_at="2026-08-20T15:00:00Z",
        author_name="Grandmother",
    )

    resp = _admin_list(authed_client, post)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["post_slug"] == post
    slugs = [row["slug"] for row in data["comments"]]
    assert slugs == [
        "c-20260820t153000z-pending-later",
        "c-20260820t152000z-visible",
        "c-20260820t151000z-hidden",
        "c-20260820t150000z-pending",
    ]
    first = data["comments"][0]
    assert first["visibility"] == "pending"
    assert first["body"] == "Later pending."
    assert first["source_type"] == "form"
    assert first["agent_key_name"] is None
    assert first["author_kind"] == "public"
    assert first["post_slug"] == post
    assert "email" not in first
    assert data["pending_counts"][post] == 2
    visibilities = {row["visibility"] for row in data["comments"]}
    assert visibilities == {"pending", "visible", "hidden"}

    public = _public_list(authed_client, post)
    assert public.status_code == 200, public.text
    public_rows = public.json()["comments"]
    assert [row["slug"] for row in public_rows] == ["c-20260820t152000z-visible"]
    assert "visibility" not in public_rows[0]
    assert "email" not in public_rows[0]
    assert "source_type" not in public_rows[0]
    assert "agent_key_name" not in public_rows[0]


def test_admin_list_unknown_post_is_empty(authed_client):
    resp = _admin_list(authed_client, "no-such-post-xyz")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["post_slug"] == "no-such-post-xyz"
    assert data["comments"] == []


def test_admin_list_site_wide_and_visibility_filter(
    authed_client, temp_data_root: Path
):
    cupcakes = _seed_post(temp_data_root, f"inbox-a-{uuid.uuid4().hex[:8]}")
    tart = _seed_post(temp_data_root, f"inbox-b-{uuid.uuid4().hex[:8]}")
    _write_comment_file(
        temp_data_root,
        post_slug=cupcakes,
        comment_slug="c-20260820t150000z-old",
        body="Older pending on cupcakes.",
        visibility="pending",
        received_at="2026-08-20T15:00:00Z",
    )
    _write_comment_file(
        temp_data_root,
        post_slug=tart,
        comment_slug="c-20260820t160000z-new",
        body="Newer pending on tart.",
        visibility="pending",
        received_at="2026-08-20T16:00:00Z",
    )
    _write_comment_file(
        temp_data_root,
        post_slug=tart,
        comment_slug="c-20260820t154000z-vis",
        body="Already visible on tart.",
        visibility="visible",
        received_at="2026-08-20T15:40:00Z",
    )

    resp = _admin_list(authed_client)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["post_slug"] == ""
    slugs = [row["slug"] for row in data["comments"]]
    ours = [s for s in slugs if s in {
        "c-20260820t160000z-new",
        "c-20260820t154000z-vis",
        "c-20260820t150000z-old",
    }]
    assert ours == [
        "c-20260820t160000z-new",
        "c-20260820t154000z-vis",
        "c-20260820t150000z-old",
    ]
    assert data["pending_counts"].get(cupcakes) == 1
    assert data["pending_counts"].get(tart) == 1
    by_slug = {row["slug"]: row for row in data["comments"]}
    assert by_slug["c-20260820t160000z-new"]["post_slug"] == tart
    assert by_slug["c-20260820t150000z-old"]["post_slug"] == cupcakes

    pending = authed_client.get(
        "/api/v1/admin/comments", params={"visibility": "pending"}
    )
    assert pending.status_code == 200, pending.text
    pending_slugs = [
        row["slug"]
        for row in pending.json()["comments"]
        if row["post_slug"] in {cupcakes, tart}
    ]
    assert pending_slugs == [
        "c-20260820t160000z-new",
        "c-20260820t150000z-old",
    ]
    assert pending.json()["pending_counts"].get(cupcakes) == 1
    assert pending.json()["pending_counts"].get(tart) == 1

    blank = _admin_list(authed_client, "   ")
    assert blank.status_code == 200, blank.text
    assert blank.json()["post_slug"] == ""


def test_admin_list_invalid_visibility_is_400(authed_client):
    resp = authed_client.get(
        "/api/v1/admin/comments", params={"visibility": "published"}
    )
    assert resp.status_code == 400, resp.text


def test_post_reply_approves_parent(
    authed_client, temp_data_root: Path
):
    post = _seed_post(temp_data_root, "reply-me")
    parent_slug = "c-20260820t150000z-frosting"
    path = _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug=parent_slug,
        body="The lemon frosting is perfect.",
        visibility="pending",
        received_at="2026-08-20T15:00:00Z",
        author_name="Grandmother",
    )
    resp = authed_client.post(
        "/api/v1/admin/comments",
        json={
            "post_slug": post,
            "body": "Glad you like it — we use Meyer lemons.",
            "in_reply_to": parent_slug,
        },
    )
    assert resp.status_code == 200, resp.text
    comment = resp.json()["comment"]
    assert comment["author_kind"] == "human"
    assert comment["source_type"] == "admin"
    assert comment["visibility"] == "visible"
    assert comment["in_reply_to"] == parent_slug
    assert comment["post_slug"] == post
    assert "visibility: visible" in path.read_text(encoding="utf-8")
    public = _public_list(authed_client, post).json()["comments"]
    bodies = [row["body"] for row in public]
    assert "The lemon frosting is perfect." in bodies
    assert "Glad you like it — we use Meyer lemons." in bodies


def test_post_reply_without_approve_parent_leaves_pending(
    authed_client, temp_data_root: Path
):
    post = _seed_post(temp_data_root, "keep-pending")
    parent_slug = "c-20260820t150000z-keep"
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug=parent_slug,
        body="Please keep me pending.",
        visibility="pending",
        received_at="2026-08-20T15:00:00Z",
    )
    resp = authed_client.post(
        "/api/v1/admin/comments",
        json={
            "post_slug": post,
            "body": "Noted internally.",
            "in_reply_to": parent_slug,
            "approve_parent": False,
        },
    )
    assert resp.status_code == 200, resp.text
    listed = _admin_list(authed_client, post).json()["comments"]
    by_slug = {row["slug"]: row for row in listed}
    assert by_slug[parent_slug]["visibility"] == "pending"
    public_bodies = [
        row["body"] for row in _public_list(authed_client, post).json()["comments"]
    ]
    assert "Please keep me pending." not in public_bodies
    assert "Noted internally." in public_bodies


def test_patch_body_keeps_slug_and_refreshes_name(
    authed_client, temp_data_root: Path
):
    post = _seed_post(temp_data_root, "edit-me")
    comment_slug = "c-20260820t150000z-frosting"
    path = _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug=comment_slug,
        body="The lemon frosting is perfect.",
        visibility="pending",
        received_at="2026-08-20T15:00:00Z",
        author_name="Grandmother",
    )
    resp = authed_client.patch(
        f"/api/v1/admin/comments/{comment_slug}",
        json={
            "post_slug": post,
            "body": "The chocolate frosting is even better.",
            "author_name": "Ada",
        },
    )
    assert resp.status_code == 200, resp.text
    comment = resp.json()["comment"]
    assert comment["slug"] == comment_slug
    assert comment["body"] == "The chocolate frosting is even better."
    assert comment["author_name"] == "Ada"
    assert comment["visibility"] == "pending"
    yaml_text = path.read_text(encoding="utf-8")
    assert path.name == f"{comment_slug}.md"
    assert "name: The chocolate frosting is even" in yaml_text
    assert "author_name: Ada" in yaml_text
    assert "visibility: pending" in yaml_text


def test_post_unknown_post_slug_is_400(authed_client):
    resp = authed_client.post(
        "/api/v1/admin/comments",
        json={"post_slug": "no-such-post-xyz", "body": "Orphan."},
    )
    assert resp.status_code == 400, resp.text


def test_patch_pending_to_visible_then_public_get_includes_body(
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
    assert "The lemon frosting is perfect." not in [
        row["body"] for row in _public_list(authed_client, post).json()["comments"]
    ]

    resp = authed_client.patch(
        "/api/v1/admin/comments/c-20260820t150000z-frosting",
        json={"visibility": "visible", "post_slug": post},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    comment = body.get("comment") or body
    assert comment["visibility"] == "visible"
    assert comment["slug"] == "c-20260820t150000z-frosting"
    yaml_text = path.read_text(encoding="utf-8")
    assert "visibility: visible" in yaml_text
    assert "kind: comment" in yaml_text

    public = _public_list(authed_client, post)
    assert public.status_code == 200, public.text
    rows = public.json()["comments"]
    assert [row["body"] for row in rows] == ["The lemon frosting is perfect."]
    assert "visibility" not in rows[0]


def test_patch_hidden_omits_from_public_get_file_stays(
    authed_client, temp_data_root: Path
):
    post = _seed_post(temp_data_root, "hide-me")
    path = _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150000z-visible",
        body="Take this off the thread.",
        visibility="visible",
        received_at="2026-08-20T15:00:00Z",
    )
    assert len(_public_list(authed_client, post).json()["comments"]) == 1

    resp = authed_client.patch(
        "/api/v1/admin/comments/c-20260820t150000z-visible",
        json={"visibility": "hidden", "post_slug": post},
    )
    assert resp.status_code == 200, resp.text
    assert path.exists()
    assert "visibility: hidden" in path.read_text(encoding="utf-8")
    assert _public_list(authed_client, post).json()["comments"] == []


def test_patch_invalid_visibility_is_400(authed_client, temp_data_root: Path):
    post = _seed_post(temp_data_root, "bad-vis")
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150000z-pending",
        body="Stay pending.",
        visibility="pending",
        received_at="2026-08-20T15:00:00Z",
    )
    resp = authed_client.patch(
        "/api/v1/admin/comments/c-20260820t150000z-pending",
        json={"visibility": "published", "post_slug": post},
    )
    assert resp.status_code == 400, resp.text


def test_patch_unknown_comment_is_404(authed_client, temp_data_root: Path):
    post = _seed_post(temp_data_root, "missing-cmt")
    resp = authed_client.patch(
        "/api/v1/admin/comments/c-20260820t150000z-nope",
        json={"visibility": "visible", "post_slug": post},
    )
    assert resp.status_code == 404, resp.text


def test_patch_and_delete_missing_post_slug_is_400(
    authed_client, temp_data_root: Path
):
    post = _seed_post(temp_data_root, "need-slug")
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150000z-pending",
        body="Need a parent.",
        visibility="pending",
        received_at="2026-08-20T15:00:00Z",
    )
    patched = authed_client.patch(
        "/api/v1/admin/comments/c-20260820t150000z-pending",
        json={"visibility": "visible"},
    )
    assert patched.status_code == 400, patched.text
    deleted = authed_client.delete(
        "/api/v1/admin/comments/c-20260820t150000z-pending"
    )
    assert deleted.status_code == 400, deleted.text


def test_delete_removes_file_and_public_get_empty(
    authed_client, temp_data_root: Path
):
    post = _seed_post(temp_data_root, "delete-me")
    path = _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150000z-gone",
        body="Remove this file.",
        visibility="visible",
        received_at="2026-08-20T15:00:00Z",
    )
    assert path.exists()
    resp = authed_client.delete(
        "/api/v1/admin/comments/c-20260820t150000z-gone",
        params={"post_slug": post},
    )
    assert resp.status_code == 204, resp.text
    assert not path.exists()
    assert _public_list(authed_client, post).json()["comments"] == []
    listed = _admin_list(authed_client, post)
    assert listed.status_code == 200, listed.text
    assert listed.json()["comments"] == []


def test_delete_unknown_comment_is_404(authed_client, temp_data_root: Path):
    post = _seed_post(temp_data_root, "delete-missing")
    resp = authed_client.delete(
        "/api/v1/admin/comments/c-20260820t150000z-nope",
        params={"post_slug": post},
    )
    assert resp.status_code == 404, resp.text


def test_site_header_does_not_leak_other_tenant(
    authed_client, temp_data_root: Path
):
    from services.site_service import create_site, ensure_sites_initialized

    ensure_sites_initialized()
    other_id = f"adm{uuid.uuid4().hex[:8]}"
    create_site(other_id, "Other Admin Site")

    default_post = _seed_post(temp_data_root, "shared-slug", site_id="default")
    other_post = _seed_post(temp_data_root, "shared-slug", site_id=other_id)
    assert default_post == other_post == "shared-slug"

    _write_comment_file(
        temp_data_root,
        post_slug="shared-slug",
        comment_slug="c-20260820t180000z-default",
        body="On default.",
        visibility="pending",
        received_at="2026-08-20T18:00:00Z",
        site_id="default",
    )
    _write_comment_file(
        temp_data_root,
        post_slug="shared-slug",
        comment_slug="c-20260820t181000z-other",
        body="On other.",
        visibility="pending",
        received_at="2026-08-20T18:10:00Z",
        site_id=other_id,
    )

    default_resp = _admin_list(authed_client, "shared-slug")
    assert default_resp.status_code == 200, default_resp.text
    default_slugs = [row["slug"] for row in default_resp.json()["comments"]]
    assert default_slugs == ["c-20260820t180000z-default"]

    other_resp = _admin_list(
        authed_client, "shared-slug", headers={"X-Pen-Site-Id": other_id}
    )
    assert other_resp.status_code == 200, other_resp.text
    other_slugs = [row["slug"] for row in other_resp.json()["comments"]]
    assert other_slugs == ["c-20260820t181000z-other"]


def test_openapi_documents_admin_comments():
    spec = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "core" / "openapi.yaml").read_text(
            encoding="utf-8"
        )
    )
    listed = spec["paths"]["/admin/comments"]["get"]
    assert listed.get("security")
    params = {p["name"]: p for p in listed["parameters"]}
    assert params["post_slug"]["required"] is False
    assert "visibility" in params
    posted = spec["paths"]["/admin/comments"]["post"]
    assert posted.get("security")
    patched = spec["paths"]["/admin/comments/{comment_slug}"]["patch"]
    deleted = spec["paths"]["/admin/comments/{comment_slug}"]["delete"]
    assert patched.get("security")
    assert deleted.get("security")
    admin = spec["components"]["schemas"]["AdminComment"]
    assert "visibility" in admin["properties"]
    assert "post_slug" in admin["properties"]
    assert "email" not in admin["properties"]
    assert "admin" in admin["properties"]["source_type"]["enum"]
    listing = spec["components"]["schemas"]["AdminCommentList"]
    assert "pending_counts" in listing["required"]
    public = spec["components"]["schemas"]["PublicComment"]
    assert "visibility" not in public["properties"]
    assert "email" not in public["properties"]
