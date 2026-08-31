"""Public GET /api/v1/comments: visible-only thread, Host / X-Pen-Site-Id binding."""

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


def _get_comments(client, post_slug: Optional[str] = None, **kwargs):
    params = {}
    if post_slug is not None:
        params["post_slug"] = post_slug
    return client.get("/api/v1/comments", params=params, **kwargs)


def test_lists_visible_omits_pending_and_hidden(client, temp_data_root: Path):
    post = _seed_post(temp_data_root, "gluten-free-cupcakes")
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150000z-pending",
        body="Grandmother just submitted this.",
        visibility="pending",
        received_at="2026-08-20T15:00:00Z",
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

    resp = _get_comments(client, post)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["post_slug"] == post
    slugs = [row["slug"] for row in data["comments"]]
    assert slugs == ["c-20260820t152000z-visible"]
    row = data["comments"][0]
    assert row["author_name"] == "Ada"
    assert row["author_kind"] == "public"
    assert row["body"] == "The lemon frosting is perfect."
    assert row["in_reply_to"] is None
    assert row["received_at"] == "2026-08-20T15:20:00Z"
    assert "visibility" not in row
    assert "email" not in row
    assert "agent_key_name" not in row
    assert "source_type" not in row


def test_oldest_first_by_received_at_then_slug(client, temp_data_root: Path):
    post = _seed_post(temp_data_root, "order-post")
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t160000z-later",
        body="Second by time.",
        visibility="visible",
        received_at="2026-08-20T16:00:00Z",
    )
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150000z-zebra",
        body="Same time, later slug.",
        visibility="visible",
        received_at="2026-08-20T15:00:00Z",
    )
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150000z-alpha",
        body="Same time, earlier slug.",
        visibility="visible",
        received_at="2026-08-20T15:00:00Z",
    )

    resp = _get_comments(client, post)
    assert resp.status_code == 200, resp.text
    slugs = [row["slug"] for row in resp.json()["comments"]]
    assert slugs == [
        "c-20260820t150000z-alpha",
        "c-20260820t150000z-zebra",
        "c-20260820t160000z-later",
    ]


def test_delayed_reply_follows_parent_not_end_of_list(client, temp_data_root: Path):
    post = _seed_post(temp_data_root, "thread-post")
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t140000z-alice",
        body="Nice article.",
        visibility="visible",
        received_at="2026-08-20T14:00:00Z",
        author_name="Alice",
    )
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150000z-kiki",
        body="Does Wikipedia own WikiLeaks?",
        visibility="visible",
        received_at="2026-08-20T15:00:00Z",
        author_name="Kiki",
    )
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t150500z-bot",
        body="No, they are different organizations.",
        visibility="visible",
        received_at="2026-08-20T15:05:00Z",
        author_name="synticbot",
        in_reply_to="c-20260820t150000z-kiki",
    )
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t160000z-paul",
        body="What about Norwegian Wikipedia?",
        visibility="visible",
        received_at="2026-08-20T16:00:00Z",
        author_name="Paul",
    )
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260825t230000z-adamski",
        body="Well, Kiki, they are not the same.",
        visibility="visible",
        received_at="2026-08-25T23:00:00Z",
        author_name="Adamski",
        in_reply_to="c-20260820t150000z-kiki",
    )

    resp = _get_comments(client, post)
    assert resp.status_code == 200, resp.text
    slugs = [row["slug"] for row in resp.json()["comments"]]
    assert slugs == [
        "c-20260820t140000z-alice",
        "c-20260820t150000z-kiki",
        "c-20260820t150500z-bot",
        "c-20260825t230000z-adamski",
        "c-20260820t160000z-paul",
    ]


def test_unknown_post_returns_empty_list(client):
    resp = _get_comments(client, "no-such-post-xyz")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["post_slug"] == "no-such-post-xyz"
    assert data["comments"] == []


def test_existing_post_with_no_comments_is_empty(client, temp_data_root: Path):
    post = _seed_post(temp_data_root, "lonely-post")
    resp = _get_comments(client, post)
    assert resp.status_code == 200, resp.text
    assert resp.json()["comments"] == []


def test_missing_post_slug_is_400(client):
    resp = _get_comments(client)
    assert resp.status_code == 400, resp.text
    blank = client.get("/api/v1/comments", params={"post_slug": "   "})
    assert blank.status_code == 400, blank.text


def test_unauthenticated(client, temp_data_root: Path):
    post = _seed_post(temp_data_root, "public-thread")
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t170000z-ok",
        body="Visible to strangers.",
        visibility="visible",
        received_at="2026-08-20T17:00:00Z",
    )
    resp = _get_comments(client, post)
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["comments"]) == 1


def test_x_pen_site_id_and_host_binding(client, temp_data_root: Path):
    from services.site_service import create_site, ensure_sites_initialized

    ensure_sites_initialized()
    other_id = f"cmt{uuid.uuid4().hex[:8]}"
    create_site(other_id, "Other Comment Site", domain=f"{other_id}.example")

    default_post = _seed_post(temp_data_root, "shared-slug", site_id="default")
    other_post = _seed_post(temp_data_root, "shared-slug", site_id=other_id)
    assert default_post == other_post == "shared-slug"

    _write_comment_file(
        temp_data_root,
        post_slug="shared-slug",
        comment_slug="c-20260820t180000z-default",
        body="On default.",
        visibility="visible",
        received_at="2026-08-20T18:00:00Z",
        site_id="default",
    )
    _write_comment_file(
        temp_data_root,
        post_slug="shared-slug",
        comment_slug="c-20260820t181000z-other",
        body="On other.",
        visibility="visible",
        received_at="2026-08-20T18:10:00Z",
        site_id=other_id,
    )

    default_resp = _get_comments(client, "shared-slug")
    assert default_resp.status_code == 200, default_resp.text
    default_slugs = [row["slug"] for row in default_resp.json()["comments"]]
    assert default_slugs == ["c-20260820t180000z-default"]

    header_resp = _get_comments(
        client, "shared-slug", headers={"X-Pen-Site-Id": other_id}
    )
    assert header_resp.status_code == 200, header_resp.text
    header_slugs = [row["slug"] for row in header_resp.json()["comments"]]
    assert header_slugs == ["c-20260820t181000z-other"]

    host_resp = _get_comments(
        client, "shared-slug", headers={"Host": f"{other_id}.example"}
    )
    assert host_resp.status_code == 200, host_resp.text
    host_slugs = [row["slug"] for row in host_resp.json()["comments"]]
    assert host_slugs == ["c-20260820t181000z-other"]

    host_bound = _get_comments(
        client,
        "shared-slug",
        headers={"X-Pen-Site-Id": "default", "Host": f"{other_id}.example"},
    )
    assert host_bound.status_code == 200, host_bound.text
    assert [row["slug"] for row in host_bound.json()["comments"]] == [
        "c-20260820t181000z-other"
    ]


def test_visibility_query_is_ignored(client, temp_data_root: Path):
    post = _seed_post(temp_data_root, "no-leak")
    _write_comment_file(
        temp_data_root,
        post_slug=post,
        comment_slug="c-20260820t190000z-pending",
        body="Must not leak.",
        visibility="pending",
        received_at="2026-08-20T19:00:00Z",
    )
    resp = client.get(
        "/api/v1/comments",
        params={"post_slug": post, "visibility": "pending"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["comments"] == []


def test_openapi_documents_comments_get():
    spec = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "core" / "openapi.yaml").read_text(
            encoding="utf-8"
        )
    )
    path = spec["paths"]["/comments"]["get"]
    assert "security" not in path
    params = {p["name"]: p for p in path["parameters"]}
    assert params["post_slug"]["required"] is True
    assert "200" in path["responses"]
    assert "400" in path["responses"]
    schema = spec["components"]["schemas"]["PublicComment"]
    assert "email" not in schema["properties"]
    assert "visibility" not in schema["properties"]
