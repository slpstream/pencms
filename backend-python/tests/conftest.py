"""
Shared pytest fixtures for the PenCMS backend test suite.

Design notes
------------

The existing `/api/auth/setup` endpoint refuses to run when any user YAML
already exists in `data/users/`. Production code also reads from disk on
every request (`services.user_service.get_user_by_*` are not cached), so a
clean test requires a private `data/` root. We achieve this by:

1. Computing the backend's `BASE_DIR` (the parent of `app/`).
2. Creating a per-session temp dir that mirrors the production layout:
   - `{tmp}/content/`
   - `{tmp}/assets/`
   - `{tmp}/data/users/`
3. Monkeypatching `config.BASE_DIR` (and the derived paths that other
   modules captured by value at import time: `USERS_DIR`,
   `TAXONOMY_PATH`, `COLLECTIONS_SCHEMA_PATH`).
4. Rebinding `services.user_service._ensure_users_dir` to a no-op so the
   real `data/users/` directory is never created by accident.

Tests then use the FastAPI `TestClient` (sync wrapper over `httpx`) and
authenticate via the cookie issued by `/api/auth/setup` + `/api/auth/login`.
`Authorization: Bearer` is tested separately for the MCP gateway's agent-key
flow; for the AI proxy we exercise the human (cookie) auth path, since that
is how the sidebar actually calls it.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Iterator

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap — make `app/` importable as top-level package roots.
# Mirrors what `main.py` does at runtime.
# ---------------------------------------------------------------------------
BACKEND_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND_ROOT / "app"
sys.path.insert(0, str(APP_DIR))

# A stable JWT secret so token generation works under tests.
os.environ.setdefault("JWT_SECRET", "pytest-secret-not-for-production")
# MCP resource / issuer URLs for agent token aud/iss (Phase 0 / 1a).
os.environ.setdefault("JWT_ISSUER", "http://testserver")
os.environ.setdefault("MCP_RESOURCE_URL", "http://testserver/api/mcp")
os.environ.setdefault("AGENT_TOKEN_EXPIRE_MINUTES", "15")
# Loop-guard is default-on in production; tests disable so suites do not 429.
os.environ.setdefault("PENCMS_RATE_LIMIT_MCP", "0")


@pytest.fixture(autouse=True)
def _quiet_feedback_relay_register(request, monkeypatch):
    """Do not POST https://feedback.pencms.org from ordinary tests."""
    if request.node.get_closest_marker("feedback_relay_http"):
        return

    async def _noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr("services.feedback_service._register_with_relay", _noop)


@pytest.fixture(scope="session")
def temp_data_root() -> Iterator[Path]:
    """A throwaway PenCMS data root mirroring the real layout."""
    tmp = Path(tempfile.mkdtemp(prefix="pencms-test-"))
    (tmp / "content").mkdir()
    (tmp / "assets").mkdir()
    (tmp / "data" / "users").mkdir(parents=True)
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def patch_paths(temp_data_root: Path) -> Iterator[None]:
    """Redirect all disk-touching module globals at the temp data root."""
    import config
    import services.user_service as user_service
    import services.file_service as file_service
    from services.storage_provider import LocalStorageProvider
    from services.site_service import ensure_sites_initialized
    import services.cache_service as cache_service

    # config.BASE_DIR is the root every derived path hangs off.
    config.BASE_DIR = temp_data_root

    # `user_service` captured USERS_DIR = BASE_DIR / "data" / "users" at
    # import time — rebind it to the temp root.
    user_service.USERS_DIR = temp_data_root / "data" / "users"

    # Point content/assets storage at the temp root (multisite under sites/).
    content_path = temp_data_root / "content"
    assets_path = temp_data_root / "assets"
    content_path.mkdir(exist_ok=True)
    assets_path.mkdir(exist_ok=True)
    content_provider = LocalStorageProvider(str(content_path))
    assets_provider = LocalStorageProvider(str(assets_path))
    config.CONTENT_DIR_PATH = content_path
    config.ASSETS_DIR_PATH = assets_path
    config.CONTENT_DIR = content_path
    config.ASSETS_DIR = assets_path
    config.content_storage = content_provider
    config.assets_storage = assets_provider
    file_service.content_storage = content_provider

    # Taxonomy / collections schema paths point at the project's real
    # `core/schemas/` so tests still validate the actual YAML files.
    # (They are read-only, so no risk of mutation.)
    config.TAXONOMY_PATH = BACKEND_ROOT.parent / "core" / "schemas" / "taxonomy.yaml"
    # `COLLECTIONS_SCHEMA_PATH` is added in Phase 5; set it defensively so
    # tests that import config before Phase 5 lands do not AttributeError.
    collections_path = BACKEND_ROOT.parent / "core" / "schemas" / "collections.yaml"
    setattr(config, "COLLECTIONS_SCHEMA_PATH", collections_path)

    # Make _ensure_users_dir idempotent against the temp dir.
    user_service._ensure_users_dir = lambda: None

    # Reinitialise taxonomy + collections state from the real schema files.
    config.reload_taxonomy()
    if hasattr(config, "reload_collections_schema"):
        config.reload_collections_schema()

    ensure_sites_initialized()
    cache_service.init_db()

    yield


@pytest.fixture
def client() -> Iterator:
    """A FastAPI TestClient with a clean auth cookie jar per test."""
    # Imported here so the `patch_paths` fixture has run first.
    from main import app
    from starlette.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture
def authed_client(client, temp_data_root: Path) -> Iterator:
    """A TestClient that has registered + logged in as `testadmin`.

    Returns the client; the issued `pen_jwt` cookie is set on the client's
    cookie jar automatically. Tests that need the raw token (e.g. to test
    `Authorization: Bearer`) can read it from `authed_client.token`.

    Per-test isolation: `/api/auth/setup` refuses to run when any user YAML
    exists, so we wipe the temp `data/users/` directory before each test
    that depends on this fixture. Without this, the first test that calls
    `authed_client` would leave a user YAML behind and every subsequent
    test would fail with `403 System already initialized`.
    """
    users_dir = temp_data_root / "data" / "users"
    for stale in users_dir.glob("*.yaml"):
        stale.unlink()

    resp = client.post(
        "/api/auth/setup",
        json={"username": "testadmin", "password": "testpass123"},
    )
    assert resp.status_code == 200, resp.text

    resp = client.post(
        "/api/auth/login",
        json={"username": "testadmin", "password": "testpass123"},
    )
    assert resp.status_code == 200, resp.text
    # Stash the token for tests that need a Bearer header.
    client.token = resp.json().get("access_token") or ""
    yield client


@pytest.fixture
def agent_key(authed_client) -> str:
    """Generate an agent key and exchange it for a JWT bearer token.

    Used by tests that need to exercise the agent (Bearer) auth path that
    the MCP gateway will rely on in Phase 4.
    """
    resp = authed_client.post(
        "/api/auth/keys",
        json={"name": "pytest-agent", "scopes": ["read", "write"], "site_id": "default"},
    )
    assert resp.status_code == 200, resp.text
    raw_key = resp.json()["key"]

    resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def login_author(authed_client):
    """Factory: save a limited-cap author and switch the client to their session."""

    def _login(
        *,
        capabilities,
        username: str = "writer",
        password: str = "writerpass123",
        site_id: str = "default",
    ):
        import uuid as uuidlib

        from models.user import SiteMembership, User, UserAuth, UserPublic
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
            auth=UserAuth(
                password_hash=get_password_hash(password),
                agent_keys=[],
                memberships=[
                    SiteMembership(site_id=site_id, capabilities=list(capabilities))
                ],
            ),
        )
        assert save_user(author)
        authed_client.cookies.clear()
        login = authed_client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        assert login.status_code == 200, login.text
        return author

    return _login
