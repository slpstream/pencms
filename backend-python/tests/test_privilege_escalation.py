"""Session 8: privilege-escalation pack. PHP cookies are untrusted chrome."""

from __future__ import annotations

from pathlib import Path

import uuid as uuidlib

import pytest
import yaml

from services.edition import get_edition
from services.user_service import get_user_by_uuid


def _uname() -> str:
    return f"s8{uuidlib.uuid4().hex[:10]}"


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


def _login_admin(authed_client) -> None:
    authed_client.cookies.clear()
    admin = authed_client.post(
        "/api/auth/login",
        json={"username": "testadmin", "password": "testpass123"},
    )
    assert admin.status_code == 200, admin.text


def test_forged_pen_role_cookie_cannot_call_privileged_routes(
    authed_client, login_author
):
    """pen_role=admin is forgeable chrome; APIs authorize from JWT → YAML only."""
    author = login_author(
        capabilities=["write:posts"],
        username=_uname(),
    )
    authed_client.cookies.set("pen_role", "admin")
    authed_client.cookies.set("pen_user_id", author.public.uuid)

    users = authed_client.get("/api/users")
    if get_edition() == "pro":
        assert users.status_code == 403, users.text
        assert users.json()["detail"] == "missing_capability: users:manage"
    else:
        assert users.status_code == 404, users.text

    sites = authed_client.post(
        "/api/sites",
        json={"id": _site_id("s8forge"), "name": "Forged Admin Site"},
    )
    if get_edition() == "pro":
        assert sites.status_code == 403, sites.text
        assert sites.json()["detail"] == "missing_capability: manage:sites"
    else:
        assert sites.status_code == 405, sites.text

    minted = authed_client.post(
        "/api/auth/keys", json={"name": "forged-god", "scopes": ["read"]}
    )
    assert minted.status_code == 403, minted.text
    assert minted.json()["detail"] == "Admin required"

    still = get_user_by_uuid(author.public.uuid)
    assert still is not None
    assert still.public.role == "author"


def test_author_cannot_self_elevate_via_profile(authed_client, login_author):
    """PUT /api/auth/profile cannot raise role or stamp bootstrap (Core)."""
    author = login_author(
        capabilities=["write:posts"],
        username=_uname(),
    )
    uid = author.public.uuid

    profile = authed_client.put(
        "/api/auth/profile",
        json={
            "uuid": uid,
            "username": author.public.username,
            "display_name": "Elevated",
            "role": "admin",
            "status": "active",
            "is_bootstrap": True,
        },
    )
    assert profile.status_code == 200, profile.text
    yaml_user = get_user_by_uuid(uid)
    assert yaml_user.public.role == "author"
    assert yaml_user.public.is_bootstrap is False
    assert yaml_user.public.display_name == "Elevated"


@pytest.mark.pro
def test_author_cannot_self_patch_role_to_admin(authed_client, login_author):
    pytest.importorskip("pencms_pro", reason="users CRUD is Pro overlay")
    author = login_author(
        capabilities=["write:posts"],
        username=_uname(),
    )
    uid = author.public.uuid

    denied = authed_client.patch(f"/api/users/{uid}", json={"role": "admin"})
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"] == "missing_capability: users:manage"
    assert get_user_by_uuid(uid).public.role == "author"

    _login_admin(authed_client)
    granted = authed_client.patch(
        f"/api/users/{uid}/memberships/default",
        json={"capabilities": ["write:posts", "users:manage"]},
    )
    assert granted.status_code == 200, granted.text

    authed_client.cookies.clear()
    login = authed_client.post(
        "/api/auth/login",
        json={"username": author.public.username, "password": "writerpass123"},
    )
    assert login.status_code == 200, login.text
    listed = authed_client.get("/api/users")
    assert listed.status_code == 200, listed.text

    escalate = authed_client.patch(f"/api/users/{uid}", json={"role": "admin"})
    assert escalate.status_code == 403, escalate.text
    assert escalate.json()["detail"] == "cannot_modify_self"
    assert get_user_by_uuid(uid).public.role == "author"


def test_author_cannot_spoof_x_pen_site_id(authed_client, login_author):
    from services.site_service import create_site, ensure_sites_initialized

    site_a = _site_id("s8aa")
    site_b = _site_id("s8ab")
    ensure_sites_initialized()
    create_site(site_a, "Escalation A")
    create_site(site_b, "Escalation B")

    login_author(
        capabilities=["write:posts"],
        username=_uname(),
        site_id=site_a,
    )

    spoof = authed_client.get("/api/pages/", headers={"X-Pen-Site-Id": site_b})
    assert spoof.status_code == 403, spoof.text
    assert spoof.json()["detail"] == "site_access_denied"

    denied_write = authed_client.post(
        "/api/pages/",
        json=_post_body("Spoof Post", f"s8spoof{uuidlib.uuid4().hex[:8]}"),
        headers={"X-Pen-Site-Id": site_b},
    )
    assert denied_write.status_code == 403, denied_write.text
    assert denied_write.json()["detail"] == "site_access_denied"

    ok = authed_client.get("/api/pages/", headers={"X-Pen-Site-Id": site_a})
    assert ok.status_code == 200, ok.text


def test_non_admin_cannot_mint_or_manage_agent_keys(authed_client, login_author):
    login_author(
        capabilities=["write:posts", "publish:content"],
        username=_uname(),
    )

    minted = authed_client.post(
        "/api/auth/keys", json={"name": "sneaky", "scopes": ["read", "write"]}
    )
    assert minted.status_code == 403, minted.text
    assert minted.json()["detail"] == "Admin required"

    listed = authed_client.get("/api/auth/keys")
    assert listed.status_code == 403, listed.text
    assert listed.json()["detail"] == "Admin required"

    patched = authed_client.patch("/api/auth/keys/0", json={"site_id": "default"})
    assert patched.status_code == 403, patched.text

    revoked = authed_client.delete("/api/auth/keys/0")
    assert revoked.status_code == 403, revoked.text

    pending = authed_client.get("/api/auth/agent/pending")
    assert pending.status_code == 403, pending.text

    approve = authed_client.post(
        "/api/auth/agent/approve", json={"user_code": "AAAA-BBBB"}
    )
    assert approve.status_code == 403, approve.text


def test_blocked_author_jwt_is_rejected_on_authenticated_routes(
    authed_client, login_author
):
    from services.user_service import suspend_user

    author = login_author(
        capabilities=["write:posts"],
        username=_uname(),
    )
    jwt = authed_client.cookies.get("pen_jwt")
    assert jwt

    _login_admin(authed_client)
    me = authed_client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    suspended = suspend_user(
        author.public.uuid, actor_uuid=me.json()["user"]["uuid"]
    )
    assert suspended.public.status == "blocked"

    authed_client.cookies.clear()
    authed_client.cookies.set("pen_jwt", jwt)
    pages = authed_client.get("/api/pages/")
    assert pages.status_code == 403, pages.text
    assert pages.json()["detail"] == "account_suspended"

    me = authed_client.get("/api/auth/me")
    assert me.status_code == 403, me.text
    assert me.json()["detail"] == "account_suspended"


def test_must_change_password_allows_only_me_and_change_password(authed_client):
    from services.user_service import create_user

    username = _uname()
    password = "tempPass123"
    created = create_user(
        username=username,
        password=password,
        role="author",
        memberships=[
            {"site_id": "default", "capabilities": ["write:posts"]}
        ],
    )
    assert created.auth.must_change_password is True

    authed_client.cookies.clear()
    login = authed_client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200, login.text
    assert login.json()["must_change_password"] is True

    me = authed_client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["must_change_password"] is True

    pages = authed_client.get("/api/pages/")
    assert pages.status_code == 403, pages.text
    assert pages.json()["detail"] == "password_change_required"

    keys = authed_client.post(
        "/api/auth/keys", json={"name": "locked", "scopes": ["read"]}
    )
    assert keys.status_code == 403, keys.text
    assert keys.json()["detail"] == "password_change_required"

    changed = authed_client.post(
        "/api/auth/change-password",
        json={"current_password": password, "new_password": "freshPass123"},
    )
    assert changed.status_code == 200, changed.text
    pages2 = authed_client.get("/api/pages/")
    assert pages2.status_code == 200, pages2.text


def test_openapi_documents_session_payload_without_users_crud():
    contract_path = Path(__file__).resolve().parents[2] / "core" / "openapi.yaml"
    contract = yaml.safe_load(contract_path.read_text())
    paths = contract["paths"]
    assert "/users" not in paths
    assert "/users/{uuid}" not in paths
    assert "post" not in paths.get("/sites", {})
    me = paths["/auth/me"]
    assert me["servers"] == [{"url": "/api"}]
    assert "get" in me
    session = contract["components"]["schemas"]["SessionPayload"]
    for field in (
        "user",
        "vault",
        "must_change_password",
        "memberships",
        "accessible_sites",
        "active_site_id",
        "capabilities",
        "edition",
    ):
        assert field in session["properties"]
    vocab = contract["components"]["schemas"]["Capability"]
    assert "write:posts" in vocab["enum"]
    assert "publish:content" in vocab["enum"]
    assert "publish" in vocab["enum"]
    assert "users:manage" in vocab["enum"]


def test_storage_config_requires_auth(client):
    resp = client.get("/api/storage/config")
    assert resp.status_code == 401, resp.text
    assert resp.json()["detail"] == "Not authenticated"


def test_storage_install_routes_require_admin_not_caps(
    authed_client, login_author
):
    login_author(
        capabilities=["write:posts", "users:manage"],
        username=_uname(),
    )
    listed = authed_client.get("/api/storage/config")
    assert listed.status_code == 403, listed.text
    assert listed.json()["detail"] == "Admin required"

    patched = authed_client.put("/api/storage/general", json={"use_ai": True})
    assert patched.status_code == 403, patched.text
    assert patched.json()["detail"] == "Admin required"


def test_agent_cannot_read_storage_config(authed_client, agent_key):
    resp = authed_client.get(
        "/api/storage/config",
        headers={"Authorization": f"Bearer {agent_key}"},
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == "Admin required"


def test_admin_can_read_storage_config(authed_client):
    resp = authed_client.get("/api/storage/config")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "content" in body
    assert "assets" in body
