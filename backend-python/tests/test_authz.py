"""Session 1 authz: expansion, blocked login, bootstrap, admin-gated keys."""

from __future__ import annotations

import uuid as uuidlib

import yaml

from models.user import SiteMembership, User, UserAuth, UserPublic
from services.authz import (
    ALLOWED_CAPABILITIES,
    WRITE_EXPANSION,
    accessible_site_ids,
    caps_for_actor,
    expand_capabilities,
    has_capability,
    may_access_site,
    ordered_allowed_scopes,
    ordered_caps,
)


def _user(*, role: str = "author", status: str = "active", memberships=None, **public_extra) -> User:
    return User(
        public=UserPublic(
            uuid="u-test",
            username="tester",
            display_name="Tester",
            role=role,
            status=status,
            **public_extra,
        ),
        auth=UserAuth(
            password_hash="x",
            memberships=memberships or [],
        ),
    )


def test_expand_write_is_one_way_and_excludes_host_and_manage():
    expanded = expand_capabilities(["write"])
    assert "write" in expanded
    assert WRITE_EXPANSION <= expanded
    assert "publish:content" in expanded
    assert "publish" not in expanded
    assert "users:manage" not in expanded
    assert "manage:sites" not in expanded
    assert "read" not in expanded


def test_expand_write_posts_does_not_imply_write_or_theme():
    expanded = expand_capabilities(["write:posts"])
    assert expanded == frozenset({"write:posts"})
    assert "write" not in expanded
    assert "write:theme" not in expanded
    assert "write:taxonomy" not in expanded
    assert "write:pages" not in expanded


def test_expand_publish_content_does_not_imply_host_publish():
    expanded = expand_capabilities(["publish:content"])
    assert expanded == frozenset({"publish:content"})
    assert "publish" not in expanded


def test_expand_read_and_empty_and_union():
    assert expand_capabilities([]) == frozenset()
    assert expand_capabilities(["read"]) == frozenset({"read"})
    combined = expand_capabilities(["read", "write:posts", "write"])
    assert "read" in combined
    assert "write" in combined
    assert "write:posts" in combined
    assert "write:theme" in combined
    assert "publish" not in combined


def test_expand_write_plus_publish_keeps_host_publish():
    expanded = expand_capabilities(["write", "publish"])
    assert "publish" in expanded
    assert "publish:content" in expanded
    assert WRITE_EXPANSION <= expanded


def test_caps_for_actor_admin_gets_all_granular():
    admin = _user(role="admin")
    caps = caps_for_actor(admin, site_id="default", token_payload={"type": "human"})
    assert caps == ALLOWED_CAPABILITIES
    assert has_capability(
        admin, "write:theme", site_id="other", token_payload={}
    )
    assert has_capability(admin, "users:manage", site_id="default", token_payload={})


def test_caps_for_actor_author_membership_is_site_scoped():
    author = _user(
        role="author",
        memberships=[
            SiteMembership(site_id="blog", capabilities=["write:posts", "write:pages"]),
        ],
    )
    blog_caps = caps_for_actor(author, site_id="blog", token_payload={})
    assert "write:posts" in blog_caps
    assert "write:pages" in blog_caps
    assert "write:theme" not in blog_caps
    assert caps_for_actor(author, site_id="default", token_payload={}) == frozenset()


def test_caps_for_actor_agent_ignores_sponsor_admin_role():
    sponsor = _user(role="admin")
    payload = {"type": "agent", "scopes": ["write:posts"], "site_id": "default"}
    caps = caps_for_actor(sponsor, site_id="default", token_payload=payload)
    assert caps == frozenset({"write:posts"})
    assert "users:manage" not in caps
    assert "write:theme" not in caps
    assert not has_capability(
        sponsor, "write:theme", site_id="default", token_payload=payload
    )


def test_caps_for_actor_agent_legacy_write_expands():
    sponsor = _user(role="admin")
    payload = {"type": "agent", "scopes": ["read", "write"], "site_id": "default"}
    caps = caps_for_actor(sponsor, site_id="default", token_payload=payload)
    assert "write:posts" in caps
    assert "publish:content" in caps
    assert "publish" not in caps


def test_may_access_site_agent_does_not_inherit_sponsor_admin():
    sponsor = _user(role="admin")
    payload = {"type": "agent", "scopes": ["write:posts"], "site_id": "blog"}
    assert may_access_site(sponsor, "blog", token_payload=payload)
    assert not may_access_site(sponsor, "wiki", token_payload=payload)
    assert may_access_site(sponsor, "wiki", token_payload={})


def test_accessible_site_ids_preserves_registry_order():
    author = _user(
        role="author",
        memberships=[
            SiteMembership(site_id="wiki", capabilities=["write:posts"]),
            SiteMembership(site_id="blog", capabilities=["write:pages"]),
        ],
    )
    assert accessible_site_ids(
        author, token_payload={}, all_site_ids=["default", "blog", "wiki", "other"]
    ) == ["blog", "wiki"]
    admin = _user(role="admin")
    assert accessible_site_ids(
        admin, token_payload={}, all_site_ids=["default", "blog"]
    ) == ["default", "blog"]
    agent_payload = {"type": "agent", "site_id": "wiki"}
    assert accessible_site_ids(
        admin, token_payload=agent_payload, all_site_ids=["default", "blog", "wiki"]
    ) == ["wiki"]


def test_ordered_caps_scope_order_then_leftovers():
    assert ordered_caps(["write:theme", "write:posts", "read"]) == [
        "read",
        "write:posts",
        "write:theme",
    ]
    assert ordered_caps(["custom:cap", "read"]) == ["read", "custom:cap"]


def test_setup_stamps_is_bootstrap(authed_client, temp_data_root):
    me = authed_client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    public = me.json()["user"]
    assert public["is_bootstrap"] is True
    assert public["role"] == "admin"
    assert public["status"] == "active"

    yaml_path = next((temp_data_root / "data" / "users").glob("*.yaml"))
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert data["public"]["is_bootstrap"] is True
    assert data["auth"].get("must_change_password") is False


def test_sole_operator_yaml_stamped_bootstrap(client, temp_data_root):
    users_dir = temp_data_root / "data" / "users"
    for stale in users_dir.glob("*.yaml"):
        stale.unlink()
    uid = "11111111-1111-1111-1111-111111111111"
    yaml_path = users_dir / f"{uid}.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                "public:",
                f"  uuid: {uid}",
                "  username: operator",
                "  display_name: Operator",
                "  role: author",
                "auth:",
                "  password_hash: dummy",
                "  agent_keys: []",
                "",
            ]
        ),
        encoding="utf-8",
    )
    from services.user_service import get_user_by_uuid

    user = get_user_by_uuid(uid)
    assert user is not None
    assert user.public.is_bootstrap is True
    assert user.public.role == "admin"
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert data["public"]["is_bootstrap"] is True
    assert data["public"]["role"] == "admin"


def test_blocked_login_returns_account_suspended(authed_client):
    me = authed_client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    uid = me.json()["user"]["uuid"]

    from services.user_service import get_user_by_uuid, save_user

    user = get_user_by_uuid(uid)
    user.public.status = "blocked"
    assert save_user(user)

    resp = authed_client.get("/api/auth/me")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "account_suspended"

    authed_client.cookies.clear()
    resp = authed_client.post(
        "/api/auth/login",
        json={"username": "testadmin", "password": "testpass123"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "account_suspended"

    resp = authed_client.post(
        "/api/auth/login",
        json={"username": "testadmin", "password": "wrong-password"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] != "account_suspended"


def _save_author(username: str = "writer", password: str = "writerpass123") -> User:
    from services.auth_service import get_password_hash
    from services.user_service import save_user

    author = User(
        public=UserPublic(
            uuid=str(uuidlib.uuid4()),
            username=username,
            display_name="Writer",
            role="author",
            status="active",
            is_bootstrap=False,
        ),
        auth=UserAuth(password_hash=get_password_hash(password), agent_keys=[]),
    )
    assert save_user(author)
    return author


def test_non_admin_cannot_mint_list_patch_or_revoke_keys(authed_client):
    _save_author()
    authed_client.cookies.clear()
    login = authed_client.post(
        "/api/auth/login",
        json={"username": "writer", "password": "writerpass123"},
    )
    assert login.status_code == 200, login.text

    minted = authed_client.post(
        "/api/auth/keys", json={"name": "sneaky", "scopes": ["read"]}
    )
    assert minted.status_code == 403, minted.text

    listed = authed_client.get("/api/auth/keys")
    assert listed.status_code == 403

    patched = authed_client.patch("/api/auth/keys/0", json={"site_id": "default"})
    assert patched.status_code == 403

    revoked = authed_client.delete("/api/auth/keys/0")
    assert revoked.status_code == 403

    pending = authed_client.get("/api/auth/agent/pending")
    assert pending.status_code == 403


def test_agent_jwt_cannot_mint_keys(authed_client):
    minted = authed_client.post(
        "/api/auth/keys",
        json={"name": "bot", "scopes": ["read", "write"], "site_id": "default"},
    )
    assert minted.status_code == 200, minted.text
    tok = authed_client.post("/api/auth/token", json={"agent_key": minted.json()["key"]})
    assert tok.status_code == 200, tok.text
    agent_jwt = tok.json()["access_token"]

    resp = authed_client.post(
        "/api/auth/keys",
        json={"name": "escalated", "scopes": ["read"]},
        headers={"Authorization": f"Bearer {agent_jwt}"},
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == "Admin required"


def test_admin_can_mint_granular_scopes(authed_client):
    resp = authed_client.post(
        "/api/auth/keys",
        json={"name": "posts-only", "scopes": ["read", "write:posts"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["scopes"] == ["read", "write:posts"]


def test_legacy_write_still_passes_v1_write_scope(authed_client, agent_key):
    headers = {"Authorization": f"Bearer {agent_key}"}
    resp = authed_client.put(
        "/api/v1/mcp/pages/authz-legacy-write",
        json={
            "frontmatter": {"title": "Authz Write", "category": "summer"},
            "body": "ok",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


def test_ordered_allowed_scopes_includes_legacy_and_granular():
    ordered = ordered_allowed_scopes()
    assert ordered[0] == "read"
    assert "write" in ordered
    assert "write:posts" in ordered
    assert "write:taxonomy" in ordered
    assert ordered.index("write:theme") < ordered.index("write:taxonomy")
    assert "publish" in ordered
    assert "publish:content" in ordered
    assert ordered.index("write") < ordered.index("write:posts")
