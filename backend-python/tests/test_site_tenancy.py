"""Session 4: site tenancy, filtered GET /api/sites, /auth/me session shape. Pro overlay."""

from __future__ import annotations

import uuid as uuidlib

import pytest

pytestmark = pytest.mark.pro
pytest.importorskip("pencms_pro", reason="sites CRUD is Pro overlay")


def _site_id(prefix: str) -> str:
    return f"{prefix}{uuidlib.uuid4().hex[:8]}"


def _post_body(name: str, slug: str) -> dict:
    return {
        "frontmatter": {
            "name": name,
            "status": "draft",
            "domain": "blog",
            "published": False,
            "category": "general",
        },
        "content": f"{name} body.",
        "slug": slug,
    }


def _create_site(authed_client, site_id: str, name: str) -> None:
    resp = authed_client.post("/api/sites", json={"id": site_id, "name": name})
    assert resp.status_code == 200, resp.text


def test_admin_lists_all_sites(authed_client):
    site_a = _site_id("s4aa")
    site_b = _site_id("s4ab")
    _create_site(authed_client, site_a, "Tenancy A")
    _create_site(authed_client, site_b, "Tenancy B")

    listed = authed_client.get("/api/sites")
    assert listed.status_code == 200, listed.text
    ids = [s["id"] for s in listed.json()["sites"]]
    assert "default" in ids
    assert site_a in ids
    assert site_b in ids

    other = authed_client.get("/api/pages/", headers={"X-Pen-Site-Id": site_b})
    assert other.status_code == 200, other.text

    me = authed_client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["user"]["role"] == "admin"
    assert site_a in body["accessible_sites"]
    assert site_b in body["accessible_sites"]
    assert "users:manage" in body["capabilities"]
    assert "manage:sites" in body["capabilities"]


def test_author_cannot_spoof_foreign_site(authed_client, login_author):
    site_a = _site_id("s4ba")
    site_b = _site_id("s4bb")
    _create_site(authed_client, site_a, "Author A")
    _create_site(authed_client, site_b, "Author B")

    author = login_author(
        capabilities=["write:posts"],
        username=f"s4auth{uuidlib.uuid4().hex[:8]}",
        site_id=site_a,
    )
    assert author.public.role == "author"

    listed = authed_client.get("/api/sites")
    assert listed.status_code == 200, listed.text
    ids = [s["id"] for s in listed.json()["sites"]]
    assert site_a in ids
    assert site_b not in ids
    assert "default" not in ids

    spoof = authed_client.get("/api/pages/", headers={"X-Pen-Site-Id": site_b})
    assert spoof.status_code == 403, spoof.text
    assert spoof.json()["detail"] == "site_access_denied"

    denied_write = authed_client.post(
        "/api/pages/",
        json=_post_body("Spoof Post", f"s4spoof{uuidlib.uuid4().hex[:8]}"),
        headers={"X-Pen-Site-Id": site_b},
    )
    assert denied_write.status_code == 403, denied_write.text
    assert denied_write.json()["detail"] == "site_access_denied"

    ok = authed_client.get("/api/pages/", headers={"X-Pen-Site-Id": site_a})
    assert ok.status_code == 200, ok.text

    created = authed_client.post(
        "/api/pages/",
        json=_post_body("Allowed Post", f"s4post{uuidlib.uuid4().hex[:8]}"),
        headers={"X-Pen-Site-Id": site_a},
    )
    assert created.status_code == 201, created.text


def test_author_missing_header_resolves_to_membership_site(authed_client, login_author):
    site_a = _site_id("s4ca")
    site_b = _site_id("s4cb")
    _create_site(authed_client, site_a, "Home A")
    _create_site(authed_client, site_b, "Other B")
    login_author(
        capabilities=["write:posts"],
        username=f"s4home{uuidlib.uuid4().hex[:8]}",
        site_id=site_a,
    )

    listed = authed_client.get("/api/pages/")
    assert listed.status_code == 200, listed.text

    cookie_spoof = authed_client.get(
        "/api/pages/", cookies={"pen_site_id": site_b}
    )
    assert cookie_spoof.status_code == 403, cookie_spoof.text
    assert cookie_spoof.json()["detail"] == "site_access_denied"

    unknown = authed_client.get(
        "/api/pages/", headers={"X-Pen-Site-Id": "does-not-exist"}
    )
    assert unknown.status_code == 400
    assert "Unknown site_id" in unknown.json()["detail"]


def test_auth_me_and_login_expose_memberships_and_caps(authed_client, login_author):
    site_a = _site_id("s4da")
    site_b = _site_id("s4db")
    _create_site(authed_client, site_a, "Me A")
    _create_site(authed_client, site_b, "Me B")
    username = f"s4me{uuidlib.uuid4().hex[:8]}"
    password = "writerpass123"
    login_author(
        capabilities=["write:posts", "write:pages"],
        username=username,
        password=password,
        site_id=site_a,
    )

    me = authed_client.get("/api/auth/me", headers={"X-Pen-Site-Id": site_b})
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["user"]["role"] == "author"
    assert body["user"]["status"] == "active"
    assert body["must_change_password"] is False
    assert body["memberships"] == [
        {"site_id": site_a, "capabilities": ["write:posts", "write:pages"]}
    ]
    assert body["accessible_sites"] == [site_a]
    assert body["active_site_id"] == site_a
    assert "write:posts" in body["capabilities"]
    assert "write:pages" in body["capabilities"]
    assert "write:theme" not in body["capabilities"]
    assert site_b not in body["accessible_sites"]

    me_on_a = authed_client.get("/api/auth/me", headers={"X-Pen-Site-Id": site_a})
    assert me_on_a.status_code == 200, me_on_a.text
    assert me_on_a.json()["active_site_id"] == site_a
    assert me_on_a.json()["capabilities"] == body["capabilities"]

    authed_client.cookies.clear()
    login = authed_client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert login.status_code == 200, login.text
    logged = login.json()
    for key in (
        "user",
        "vault",
        "must_change_password",
        "memberships",
        "accessible_sites",
        "active_site_id",
        "capabilities",
        "edition",
    ):
        assert key in logged
        assert key in body
    assert logged["message"] == "Login successful"
    assert logged["memberships"] == body["memberships"]
    assert logged["accessible_sites"] == [site_a]
    assert logged["active_site_id"] == site_a
    assert logged["capabilities"] == body["capabilities"]


def test_agent_sites_list_is_jwt_site_only(authed_client):
    site_a = _site_id("s4ea")
    site_b = _site_id("s4eb")
    _create_site(authed_client, site_a, "Agent A")
    _create_site(authed_client, site_b, "Agent B")

    minted = authed_client.post(
        "/api/auth/keys",
        json={"name": f"s4ag{uuidlib.uuid4().hex[:8]}", "scopes": ["read"], "site_id": site_a},
    )
    assert minted.status_code == 200, minted.text
    raw = minted.json()["key"]
    token_resp = authed_client.post("/api/auth/token", json={"agent_key": raw})
    assert token_resp.status_code == 200, token_resp.text
    token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "X-Pen-Site-Id": site_b}

    listed = authed_client.get("/api/sites", headers=headers)
    assert listed.status_code == 200, listed.text
    ids = [s["id"] for s in listed.json()["sites"]]
    assert ids == [site_a]

    me = authed_client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["memberships"] == []
    assert body["accessible_sites"] == [site_a]
    assert body["active_site_id"] == site_a
    assert body["capabilities"] == ["read"]
