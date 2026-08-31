"""Feedback ingest: contact fb-* stubs; comments beside the post as c-*.md."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

import frontmatter
import pytest
import yaml


@pytest.fixture(autouse=True)
def _clear_feedback_rate_limit():
    from routers.feedback import reset_feedback_rate_limit

    reset_feedback_rate_limit()
    yield
    reset_feedback_rate_limit()


def _unique_token(prefix: str = "fb") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _enable_comments(site_id: str = "default") -> None:
    from services.site_service import ensure_sites_initialized, update_site

    ensure_sites_initialized()
    update_site(site_id, comments_enabled=True)


def _post_json(client, payload: dict, **kwargs):
    return client.post("/api/v1/feedback", json=payload, **kwargs)


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


def test_post_json_writes_stub_frontmatter_and_body(client, temp_data_root: Path):
    token = _unique_token("Hello")
    message = f"{token} from curl ingest test"
    resp = _post_json(
        client,
        {"name": "Test Submitter", "message": message, "kind": "contact"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "received"
    slug = data["slug"]
    assert slug.startswith("fb-")

    path = _stub_path(temp_data_root, "default", slug)
    assert path.is_file()
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    fm = dict(post.metadata)
    assert fm["name"] != "Test Submitter"
    assert fm["submitter"] == "Test Submitter"
    assert fm["status"] == "stub"
    assert fm["published"] is False
    assert fm["page"] is True
    assert fm["kind"] == "contact"
    assert fm["source_type"] == "form"
    assert "received_at" in fm
    assert post.content.strip() == message
    assert "parent_slug" not in fm


def test_comment_writes_beside_existing_post(client, temp_data_root: Path):
    _enable_comments()
    _seed_post(temp_data_root, "my-post")
    token = _unique_token("Comment")
    message = f"{token} on a post"
    resp = _post_json(
        client,
        {
            "name": "Reader",
            "message": message,
            "kind": "comment",
            "parent_slug": "My Post!",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "received"
    slug = data["slug"]
    assert slug.startswith("c-")
    assert not _stub_path(temp_data_root, "default", slug).exists()

    path = _comment_path(temp_data_root, "default", "my-post", slug)
    assert path.is_file()
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    fm = dict(post.metadata)
    assert fm["name"] != "Reader"
    assert fm["kind"] == "comment"
    assert fm["post_slug"] == "my-post"
    assert fm["slug"] == slug
    assert fm["visibility"] == "pending"
    assert fm["author_name"] == "Reader"
    assert fm["author_kind"] == "public"
    assert fm["source_type"] == "form"
    assert fm.get("in_reply_to") in (None, "")
    assert "received_at" in fm
    assert "email" not in fm
    assert post.content.strip() == message


def test_comment_unknown_parent_is_400(client, temp_data_root: Path):
    _enable_comments()
    token = _unique_token("NoPost")
    resp = _post_json(
        client,
        {
            "name": "Reader",
            "message": f"{token} on missing post",
            "kind": "comment",
            "parent_slug": "does-not-exist-xyz",
        },
    )
    assert resp.status_code == 400, resp.text
    assert "Unknown post_slug" in resp.text
    comments_root = temp_data_root / "content" / "sites" / "default"
    assert not list(comments_root.glob("does-not-exist-xyz/comments/*.md"))
    assert not list(comments_root.glob("c-*/index.md"))


def test_comment_missing_parent_slug_is_400(client, temp_data_root: Path):
    _enable_comments()
    resp = _post_json(
        client,
        {
            "name": "Reader",
            "message": f"{_unique_token('NoParent')} needs a post",
            "kind": "comment",
        },
    )
    assert resp.status_code == 400, resp.text


def test_comment_rejects_feedback_stub_as_parent(client, temp_data_root: Path):
    _enable_comments()
    contact = _post_json(
        client,
        {"message": f"{_unique_token('Stub')} contact stub", "kind": "contact"},
    )
    assert contact.status_code == 200, contact.text
    stub_slug = contact.json()["slug"]
    assert stub_slug.startswith("fb-")

    resp = _post_json(
        client,
        {
            "message": f"{_unique_token('OnStub')} should fail",
            "kind": "comment",
            "parent_slug": stub_slug,
        },
    )
    assert resp.status_code == 400, resp.text
    assert not _comment_path(
        temp_data_root, "default", stub_slug, "ignored"
    ).parent.exists()


def test_comment_body_not_in_live_list_or_search(
    authed_client, temp_data_root: Path
):
    _enable_comments()
    post_slug = _seed_post(temp_data_root)
    token = _unique_token("HiddenCmt")
    posted = _post_json(
        authed_client,
        {
            "name": "Reader",
            "message": f"{token} must not leak into search",
            "kind": "comment",
            "parent_slug": post_slug,
        },
    )
    assert posted.status_code == 200, posted.text
    comment_slug = posted.json()["slug"]

    listed = authed_client.get("/api/pages/", params={"live_only": True})
    assert listed.status_code == 200, listed.text
    ids = {p["id"] for p in listed.json()}
    assert comment_slug not in ids

    minted = authed_client.post(
        "/api/auth/keys",
        json={"name": "comment-reader", "scopes": ["read"], "site_id": "default"},
    )
    assert minted.status_code == 200, minted.text
    raw_key = minted.json()["key"]
    exchanged = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
    assert exchanged.status_code == 200, exchanged.text
    bearer = exchanged.json()["access_token"]

    search = authed_client.get(
        "/api/v1/mcp/search",
        params={"query": token},
        headers={"Authorization": f"Bearer {bearer}"},
    )
    assert search.status_code == 200, search.text
    haystacks = []
    for row in search.json():
        haystacks.append(row.get("slug") or "")
        haystacks.append(row.get("excerpt") or "")
        haystacks.append(row.get("title") or "")
    blob = " ".join(haystacks).lower()
    assert token.lower() not in blob
    assert comment_slug not in haystacks


def test_host_not_overridable_by_body_site_id(client, temp_data_root: Path):
    from services.site_service import create_site, ensure_sites_initialized

    ensure_sites_initialized()
    other_id = f"fbx{uuid.uuid4().hex[:8]}"
    create_site(other_id, "Other Feedback Site", domain=f"{other_id}.example")

    token = _unique_token("Cross")
    resp = _post_json(
        client,
        {
            "name": "Visitor",
            "message": f"{token} should stay on default",
            "kind": "contact",
            "site_id": other_id,
        },
    )
    assert resp.status_code == 200, resp.text
    slug = resp.json()["slug"]
    assert _stub_path(temp_data_root, "default", slug).is_file()
    assert not _stub_path(temp_data_root, other_id, slug).exists()

    token_b = _unique_token("Bound")
    resp_b = _post_json(
        client,
        {"message": f"{token_b} belongs on other", "kind": "contact"},
        headers={"Host": f"{other_id}.example"},
    )
    assert resp_b.status_code == 200, resp_b.text
    slug_b = resp_b.json()["slug"]
    assert _stub_path(temp_data_root, other_id, slug_b).is_file()
    assert not _stub_path(temp_data_root, "default", slug_b).exists()


def test_x_pen_site_id_selects_ingest_site(client, temp_data_root: Path):
    from services.site_service import create_site, ensure_sites_initialized

    ensure_sites_initialized()
    other_id = f"fbx{uuid.uuid4().hex[:8]}"
    create_site(other_id, "Other Feedback Site", domain=f"{other_id}.example")
    _enable_comments(other_id)
    post_slug = _seed_post(temp_data_root, site_id=other_id)

    token = _unique_token("Header")
    contact = _post_json(
        client,
        {
            "name": "Visitor",
            "message": f"{token} contact on other",
            "kind": "contact",
            "site_id": "default",
        },
        headers={"X-Pen-Site-Id": other_id},
    )
    assert contact.status_code == 200, contact.text
    contact_slug = contact.json()["slug"]
    assert _stub_path(temp_data_root, other_id, contact_slug).is_file()
    assert not _stub_path(temp_data_root, "default", contact_slug).exists()

    comment = _post_json(
        client,
        {
            "name": "Reader",
            "message": f"{token} comment on other",
            "kind": "comment",
            "parent_slug": post_slug,
        },
        headers={"X-Pen-Site-Id": other_id, "Host": "testserver"},
    )
    assert comment.status_code == 200, comment.text
    comment_slug = comment.json()["slug"]
    assert _comment_path(
        temp_data_root, other_id, post_slug, comment_slug
    ).is_file()
    assert not _comment_path(
        temp_data_root, "default", post_slug, comment_slug
    ).exists()


def test_query_site_selects_ingest_site_when_host_unmapped(
    client, temp_data_root: Path
):
    from services.site_service import create_site, ensure_sites_initialized

    ensure_sites_initialized()
    other_id = f"fbx{uuid.uuid4().hex[:8]}"
    create_site(other_id, "Other Feedback Site", domain=f"{other_id}.example")
    _enable_comments(other_id)
    post_slug = _seed_post(temp_data_root, site_id=other_id)

    token = _unique_token("Query")
    comment = client.post(
        "/api/v1/feedback",
        params={"site": other_id},
        json={
            "name": "Reader",
            "message": f"{token} via query site",
            "kind": "comment",
            "parent_slug": post_slug,
        },
    )
    assert comment.status_code == 200, comment.text
    comment_slug = comment.json()["slug"]
    assert _comment_path(
        temp_data_root, other_id, post_slug, comment_slug
    ).is_file()

    spoof = client.post(
        "/api/v1/feedback",
        params={"site": "default"},
        json={
            "name": "Visitor",
            "message": f"{token} must stay on host site",
            "kind": "contact",
        },
        headers={"Host": f"{other_id}.example"},
    )
    assert spoof.status_code == 200, spoof.text
    spoof_slug = spoof.json()["slug"]
    assert _stub_path(temp_data_root, other_id, spoof_slug).is_file()
    assert not _stub_path(temp_data_root, "default", spoof_slug).exists()


def test_source_url_and_cookie_select_ingest_site_when_host_unmapped(
    client, temp_data_root: Path
):
    from services.site_service import create_site, ensure_sites_initialized

    ensure_sites_initialized()
    other_id = f"fbx{uuid.uuid4().hex[:8]}"
    create_site(other_id, "Other Feedback Site", domain=f"{other_id}.example")
    _enable_comments(other_id)
    post_slug = _seed_post(temp_data_root, site_id=other_id)

    token = _unique_token("SrcUrl")
    via_source = _post_json(
        client,
        {
            "name": "Reader",
            "message": f"{token} from preview url",
            "kind": "comment",
            "parent_slug": post_slug,
            "source_url": (
                "https://192.168.5.199/blog/post.php"
                f"?slug={post_slug}&site={other_id}"
            ),
        },
    )
    assert via_source.status_code == 200, via_source.text
    assert _comment_path(
        temp_data_root, other_id, post_slug, via_source.json()["slug"]
    ).is_file()

    via_cookie = _post_json(
        client,
        {
            "name": "Reader",
            "message": f"{token} from preview cookie",
            "kind": "comment",
            "parent_slug": post_slug,
            "source_url": f"https://192.168.5.199/blog/post.php?slug={post_slug}",
        },
        cookies={"pen_site_id": other_id},
    )
    assert via_cookie.status_code == 200, via_cookie.text
    assert _comment_path(
        temp_data_root, other_id, post_slug, via_cookie.json()["slug"]
    ).is_file()

    host_ignores_source = _post_json(
        client,
        {
            "name": "Visitor",
            "message": f"{token} host mapped",
            "kind": "contact",
            "source_url": "https://example.test/blog/?site=default",
        },
        headers={"Host": f"{other_id}.example"},
    )
    assert host_ignores_source.status_code == 200, host_ignores_source.text
    host_slug = host_ignores_source.json()["slug"]
    assert _stub_path(temp_data_root, other_id, host_slug).is_file()
    assert not _stub_path(temp_data_root, "default", host_slug).exists()


def test_rate_limit_sixth_post_is_429(client):
    ip = f"203.0.113.{uuid.uuid4().int % 200 + 1}"
    headers = {"X-Forwarded-For": ip}
    for i in range(5):
        resp = _post_json(
            client,
            {"message": f"{_unique_token('Rate')} hit {i}"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
    sixth = _post_json(
        client,
        {"message": f"{_unique_token('Rate')} hit 5"},
        headers=headers,
    )
    assert sixth.status_code == 429, sixth.text


def test_live_only_list_omits_stub(client):
    token = _unique_token("Hidden")
    resp = _post_json(client, {"message": f"{token} must not list live"})
    assert resp.status_code == 200, resp.text
    slug = resp.json()["slug"]

    listed = client.get("/api/pages/", params={"live_only": True})
    assert listed.status_code == 200, listed.text
    ids = {p["id"] for p in listed.json()}
    assert slug not in ids


def test_read_key_search_finds_body_revoke_blocks_token(authed_client):
    token = _unique_token("Searchable")
    message = f"{token} agent read should find this body"
    posted = _post_json(authed_client, {"message": message, "kind": "contact"})
    assert posted.status_code == 200, posted.text

    minted = authed_client.post(
        "/api/auth/keys",
        json={"name": "feedback-reader", "scopes": ["read"], "site_id": "default"},
    )
    assert minted.status_code == 200, minted.text
    raw_key = minted.json()["key"]
    exchanged = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
    assert exchanged.status_code == 200, exchanged.text
    bearer = exchanged.json()["access_token"]

    search = authed_client.get(
        "/api/v1/mcp/search",
        params={"query": token},
        headers={"Authorization": f"Bearer {bearer}"},
    )
    assert search.status_code == 200, search.text
    slugs = [row["slug"] for row in search.json()]
    assert posted.json()["slug"] in slugs
    excerpts = " ".join(row.get("excerpt") or "" for row in search.json())
    titles = " ".join(row.get("title") or "" for row in search.json())
    assert token in excerpts or token in titles or any(
        token.lower() in (row.get("slug") or "") for row in search.json()
    )

    keys = authed_client.get("/api/auth/keys")
    assert keys.status_code == 200, keys.text
    index = next(
        k["id"] for k in keys.json()["keys"] if k["name"] == "feedback-reader"
    )
    revoked = authed_client.delete(f"/api/auth/keys/{index}")
    assert revoked.status_code == 200, revoked.text

    again = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
    assert again.status_code == 401, again.text


def test_form_encoded_post_succeeds(client, temp_data_root: Path):
    token = _unique_token("Form")
    resp = client.post(
        "/api/v1/feedback",
        data={
            "name": "Form User",
            "message": f"{token} via form encoding",
            "kind": "contact",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "received"
    slug = resp.json()["slug"]
    path = _stub_path(temp_data_root, "default", slug)
    assert path.is_file()
    fm = dict(frontmatter.loads(path.read_text(encoding="utf-8")).metadata)
    assert fm["submitter"] == "Form User"


def test_missing_message_is_400(client):
    resp = _post_json(client, {"name": "No Body"})
    assert resp.status_code == 400, resp.text


def test_blank_message_is_400(client):
    resp = _post_json(client, {"message": "   "})
    assert resp.status_code == 400, resp.text


def test_invalid_kind_is_400(client):
    resp = _post_json(
        client,
        {"message": f"{_unique_token('BadKind')} x", "kind": "spam"},
    )
    assert resp.status_code == 400, resp.text


def test_anonymous_submitter_when_name_omitted(client, temp_data_root: Path):
    token = _unique_token("Anon")
    resp = _post_json(client, {"message": f"{token} anonymous handle"})
    assert resp.status_code == 200, resp.text
    path = _stub_path(temp_data_root, "default", resp.json()["slug"])
    fm = dict(frontmatter.loads(path.read_text(encoding="utf-8")).metadata)
    assert fm["submitter"] == "Anonymous"


def test_openapi_documents_feedback_path():
    spec = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "core" / "openapi.yaml").read_text(
            encoding="utf-8"
        )
    )
    path = spec["paths"]["/feedback"]["post"]
    assert "security" not in path
    content = path["requestBody"]["content"]
    assert "application/json" in content
    assert "application/x-www-form-urlencoded" in content
    assert "200" in path["responses"]
    assert "400" in path["responses"]
    assert "429" in path["responses"]
    parent = spec["components"]["schemas"]["FeedbackIngest"]["properties"]["parent_slug"]
    assert "kind=comment" in parent["description"]
    slug_desc = spec["components"]["schemas"]["FeedbackReceived"]["properties"]["slug"][
        "description"
    ]
    assert "c-" in slug_desc
    assert "fb-" in slug_desc
