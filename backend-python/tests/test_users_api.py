"""Session 5: Users API CRUD, bootstrap/self guards, must_change_password lock. Pro overlay."""

from __future__ import annotations

import uuid as uuidlib

import pytest

pytestmark = pytest.mark.pro
pytest.importorskip("pencms_pro", reason="users CRUD is Pro overlay")

from services.user_service import USERS_DIR, get_user_by_uuid


def _uname() -> str:
    return f"s5u{uuidlib.uuid4().hex[:8]}"


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


def _create_author(authed_client, **overrides) -> dict:
    username = overrides.pop("username", _uname())
    body = {
        "username": username,
        "password": overrides.pop("password", "tempPass123"),
        "display_name": overrides.pop("display_name", "Session Five"),
        "role": overrides.pop("role", "author"),
        "memberships": overrides.pop(
            "memberships",
            [{"site_id": "default", "capabilities": ["write:posts", "write:pages"]}],
        ),
    }
    body.update(overrides)
    resp = authed_client.post("/api/users", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_admin_user_crud_and_memberships(authed_client):
    created = _create_author(authed_client)
    uid = created["uuid"]
    assert created["role"] == "author"
    assert created["status"] == "active"
    assert created["is_bootstrap"] is False
    assert created["must_change_password"] is True
    assert created["created_at"]
    assert created["memberships"] == [
        {"site_id": "default", "capabilities": ["write:posts", "write:pages"]}
    ]

    listed = authed_client.get("/api/users")
    assert listed.status_code == 200, listed.text
    ids = [u["uuid"] for u in listed.json()["users"]]
    assert uid in ids

    got = authed_client.get(f"/api/users/{uid}")
    assert got.status_code == 200, got.text
    assert got.json()["username"] == created["username"]
    assert "password_hash" not in got.json()
    assert "agent_keys" not in got.json()
    assert "vault" not in got.json()

    patched = authed_client.patch(
        f"/api/users/{uid}",
        json={"display_name": "Renamed Writer", "bio": "Hello"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["display_name"] == "Renamed Writer"
    assert patched.json()["bio"] == "Hello"

    member = authed_client.patch(
        f"/api/users/{uid}/memberships/default",
        json={"capabilities": ["write:posts", "publish:content"]},
    )
    assert member.status_code == 200, member.text
    assert member.json()["memberships"] == [
        {"site_id": "default", "capabilities": ["write:posts", "publish:content"]}
    ]

    removed = authed_client.patch(
        f"/api/users/{uid}/memberships/default",
        json={"capabilities": []},
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["memberships"] == []

    reset = authed_client.post(
        f"/api/users/{uid}/reset-password",
        json={"password": "newTemp456"},
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["must_change_password"] is True

    suspended = authed_client.post(f"/api/users/{uid}/suspend")
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["status"] == "blocked"

    activated = authed_client.post(f"/api/users/{uid}/activate")
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "active"

    deleted = authed_client.delete(f"/api/users/{uid}")
    assert deleted.status_code == 200, deleted.text
    missing = authed_client.get(f"/api/users/{uid}")
    assert missing.status_code == 404
    assert get_user_by_uuid(uid) is None
    assert not (USERS_DIR / f"{uid}.yaml").exists()


def test_duplicate_username_returns_400(authed_client):
    username = _uname()
    _create_author(authed_client, username=username)
    dup = authed_client.post(
        "/api/users",
        json={
            "username": username,
            "password": "otherPass123",
            "role": "author",
        },
    )
    assert dup.status_code == 400, dup.text
    assert "already exists" in dup.json()["detail"].lower()


def test_author_and_agent_cannot_manage_users(authed_client, login_author, agent_key):
    denied = authed_client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {agent_key}"},
    )
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"] == "missing_capability: users:manage"

    login_author(
        capabilities=["write:posts", "write:pages"],
        username=_uname(),
    )
    as_author = authed_client.get("/api/users")
    assert as_author.status_code == 403, as_author.text
    assert as_author.json()["detail"] == "missing_capability: users:manage"

    created = authed_client.post(
        "/api/users",
        json={"username": _uname(), "password": "nope12345", "role": "author"},
    )
    assert created.status_code == 403


def test_suspend_blocks_login_with_account_suspended(authed_client):
    username = _uname()
    password = "tempPass123"
    created = _create_author(authed_client, username=username, password=password)
    uid = created["uuid"]

    sus = authed_client.post(f"/api/users/{uid}/suspend")
    assert sus.status_code == 200, sus.text

    authed_client.cookies.clear()
    login = authed_client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 403, login.text
    assert login.json()["detail"] == "account_suspended"

    wrong = authed_client.post(
        "/api/auth/login",
        json={"username": username, "password": "wrong-password"},
    )
    assert wrong.status_code == 401
    assert wrong.json()["detail"] != "account_suspended"


def test_bootstrap_cannot_be_deleted_demoted_or_blocked(authed_client):
    me = authed_client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    uid = me.json()["user"]["uuid"]
    assert me.json()["user"]["is_bootstrap"] is True

    deleted = authed_client.delete(f"/api/users/{uid}")
    assert deleted.status_code == 403, deleted.text
    assert deleted.json()["detail"] == "cannot_modify_bootstrap"

    blocked = authed_client.post(f"/api/users/{uid}/suspend")
    assert blocked.status_code == 403, blocked.text
    assert blocked.json()["detail"] == "cannot_modify_bootstrap"

    demoted = authed_client.patch(f"/api/users/{uid}", json={"role": "author"})
    assert demoted.status_code == 403, demoted.text
    assert demoted.json()["detail"] == "cannot_modify_bootstrap"

    still = authed_client.get("/api/auth/me")
    assert still.status_code == 200
    assert still.json()["user"]["role"] == "admin"
    assert still.json()["user"]["is_bootstrap"] is True
    assert still.json()["user"]["status"] == "active"


def test_no_self_elevation_via_patch(authed_client):
    second = _create_author(
        authed_client,
        username=_uname(),
        password="adminPass123",
        role="admin",
        memberships=[],
    )
    uid = second["uuid"]
    assert second["is_bootstrap"] is False
    assert second["role"] == "admin"

    authed_client.cookies.clear()
    login = authed_client.post(
        "/api/auth/login",
        json={"username": second["username"], "password": "adminPass123"},
    )
    assert login.status_code == 200, login.text
    # Created admins must change password before hitting /api/users.
    changed = authed_client.post(
        "/api/auth/change-password",
        json={"current_password": "adminPass123", "new_password": "adminPass123"},
    )
    assert changed.status_code == 200, changed.text

    role = authed_client.patch(f"/api/users/{uid}", json={"role": "author"})
    assert role.status_code == 403, role.text
    assert role.json()["detail"] == "cannot_modify_self"

    boot = authed_client.patch(f"/api/users/{uid}", json={"is_bootstrap": True})
    assert boot.status_code == 403, boot.text
    assert boot.json()["detail"] == "cannot_modify_self"

    sus = authed_client.post(f"/api/users/{uid}/suspend")
    assert sus.status_code == 403
    assert sus.json()["detail"] == "cannot_modify_self"

    deleted = authed_client.delete(f"/api/users/{uid}")
    assert deleted.status_code == 403
    assert deleted.json()["detail"] == "cannot_delete_self"

    grant = authed_client.patch(
        f"/api/users/{uid}/memberships/default",
        json={"capabilities": ["write:posts", "users:manage"]},
    )
    assert grant.status_code == 403, grant.text
    assert grant.json()["detail"] == "cannot_modify_self"

    other = _create_author(authed_client)
    stamp = authed_client.patch(
        f"/api/users/{other['uuid']}",
        json={"is_bootstrap": True},
    )
    assert stamp.status_code == 403, stamp.text
    assert stamp.json()["detail"] == "cannot_modify_bootstrap"
    got = authed_client.get(f"/api/users/{other['uuid']}")
    assert got.json()["is_bootstrap"] is False


def test_must_change_password_lockout_and_own_change(authed_client):
    username = _uname()
    password = "tempPass123"
    created = _create_author(authed_client, username=username, password=password)
    uid = created["uuid"]
    assert created["must_change_password"] is True

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

    users = authed_client.get("/api/users")
    assert users.status_code == 403
    assert users.json()["detail"] == "password_change_required"

    bad = authed_client.post(
        "/api/auth/change-password",
        json={"current_password": "wrong", "new_password": "freshPass123"},
    )
    assert bad.status_code == 401

    changed = authed_client.post(
        "/api/auth/change-password",
        json={"current_password": password, "new_password": "freshPass123"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["must_change_password"] is False

    me2 = authed_client.get("/api/auth/me")
    assert me2.status_code == 200
    assert me2.json()["must_change_password"] is False

    pages2 = authed_client.get("/api/pages/")
    assert pages2.status_code == 200, pages2.text

    authed_client.cookies.clear()
    relogin = authed_client.post(
        "/api/auth/login",
        json={"username": username, "password": "freshPass123"},
    )
    assert relogin.status_code == 200, relogin.text

    # Restore admin session for later tests sharing the function-scoped client.
    admin = authed_client.post(
        "/api/auth/login",
        json={"username": "testadmin", "password": "testpass123"},
    )
    assert admin.status_code == 200, admin.text
    assert uid  # keep created user around; isolation is per authed_client


def test_delete_user_orphans_content_and_removes_yaml(authed_client):
    username = _uname()
    password = "tempPass123"
    created = _create_author(authed_client, username=username, password=password)
    uid = created["uuid"]

    authed_client.cookies.clear()
    login = authed_client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert login.status_code == 200, login.text
    changed = authed_client.post(
        "/api/auth/change-password",
        json={"current_password": password, "new_password": "freshPass123"},
    )
    assert changed.status_code == 200, changed.text

    slug = f"s5-orphan-{uuidlib.uuid4().hex[:8]}"
    posted = authed_client.post("/api/pages/", json=_post_body("Orphan Post", slug))
    assert posted.status_code == 201, posted.text
    assert posted.json()["frontmatter"]["name"] == "Orphan Post"

    authed_client.cookies.clear()
    admin = authed_client.post(
        "/api/auth/login",
        json={"username": "testadmin", "password": "testpass123"},
    )
    assert admin.status_code == 200, admin.text

    deleted = authed_client.delete(f"/api/users/{uid}")
    assert deleted.status_code == 200, deleted.text
    assert get_user_by_uuid(uid) is None

    leftover = authed_client.get(f"/api/pages/{slug}")
    assert leftover.status_code == 200, leftover.text
    assert leftover.json()["frontmatter"]["name"] == "Orphan Post"
    fm = leftover.json()["frontmatter"]
    if fm.get("created_by_id"):
        assert fm["created_by_id"] == username


def test_reset_password_sets_must_change_flag(authed_client):
    username = _uname()
    created = _create_author(authed_client, username=username, password="tempPass123")
    uid = created["uuid"]

    authed_client.cookies.clear()
    login = authed_client.post(
        "/api/auth/login",
        json={"username": username, "password": "tempPass123"},
    )
    assert login.status_code == 200
    authed_client.post(
        "/api/auth/change-password",
        json={"current_password": "tempPass123", "new_password": "freshPass123"},
    )

    authed_client.cookies.clear()
    admin = authed_client.post(
        "/api/auth/login",
        json={"username": "testadmin", "password": "testpass123"},
    )
    assert admin.status_code == 200

    reset = authed_client.post(
        f"/api/users/{uid}/reset-password",
        json={"password": "resetNow789"},
    )
    assert reset.status_code == 200
    assert reset.json()["must_change_password"] is True

    authed_client.cookies.clear()
    old = authed_client.post(
        "/api/auth/login",
        json={"username": username, "password": "freshPass123"},
    )
    assert old.status_code == 401

    new = authed_client.post(
        "/api/auth/login",
        json={"username": username, "password": "resetNow789"},
    )
    assert new.status_code == 200, new.text
    assert new.json()["must_change_password"] is True
    locked = authed_client.get("/api/pages/")
    assert locked.status_code == 403
    assert locked.json()["detail"] == "password_change_required"
