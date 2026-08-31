import secrets
import pytest
from services.ai_settings_service import save_ai_settings, load_ai_settings


@pytest.fixture(autouse=True)
def clean_ai_settings():
    # Save clean baseline for default
    baseline = {
        "text_generation_prompt": "Test Persona Default",
        "image_generation_prompt": "Test Image Style Default",
        "post_quality_checklist": "1. Check spelling",
    }
    save_ai_settings("default", baseline)
    yield
    save_ai_settings("default", baseline)


@pytest.fixture
def agent_token_factory(authed_client):
    def _create(scopes, site_id="default"):
        resp = authed_client.post(
            "/api/auth/keys",
            json={
                "name": f"prompt-agent-{secrets.token_hex(4)}",
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


def test_unauthenticated_mcp_prompt_endpoints_rejected(client):
    assert client.get("/api/v1/mcp/prompts").status_code == 401
    assert client.patch("/api/v1/mcp/prompts", json={"text_generation_prompt": "x"}).status_code == 401


def test_read_scoped_key_allowed_on_get_prompts(authed_client, agent_token_factory):
    token = agent_token_factory(["read"])
    headers = {"Authorization": f"Bearer {token}"}

    resp = authed_client.get("/api/v1/mcp/prompts", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["site_id"] == "default"
    assert data["text_generation_prompt"] == "Test Persona Default"
    assert data["image_generation_prompt"] == "Test Image Style Default"
    assert data["post_quality_checklist"] == "1. Check spelling"
    assert "extractive_prompts" in data
    assert "summary" in data["extractive_prompts"]
    assert "faqs" in data["extractive_prompts"]
    assert "no new facts" in data["extractive_prompts"]["summary"].lower()
    assert "no new facts" in data["extractive_prompts"]["faqs"].lower()


def test_read_scoped_key_rejected_on_update_prompts(authed_client, agent_token_factory):
    token = agent_token_factory(["read"])
    headers = {"Authorization": f"Bearer {token}"}

    resp = authed_client.patch(
        "/api/v1/mcp/prompts",
        json={"text_generation_prompt": "New Persona"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "lacks required scope: write" in resp.json()["detail"]


def test_write_scoped_key_updates_prompts_sparsely(authed_client, agent_token_factory):
    token = agent_token_factory(["read", "write"])
    headers = {"Authorization": f"Bearer {token}"}

    # Sparse update text prompt only
    resp = authed_client.patch(
        "/api/v1/mcp/prompts",
        json={"text_generation_prompt": "Updated text prompt"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["text_generation_prompt"] == "Updated text prompt"
    assert data["image_generation_prompt"] == "Test Image Style Default"  # preserved
    assert data["post_quality_checklist"] == "1. Check spelling"  # preserved

    # Sparse update image prompt only
    resp = authed_client.patch(
        "/api/v1/mcp/prompts",
        json={"image_generation_prompt": "Cinematic 35mm film photography"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["text_generation_prompt"] == "Updated text prompt"  # preserved
    assert data["image_generation_prompt"] == "Cinematic 35mm film photography"

    # Verify persistent state via GET
    get_resp = authed_client.get("/api/v1/mcp/prompts", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["image_generation_prompt"] == "Cinematic 35mm film photography"


def test_get_site_config_includes_prompts(authed_client, agent_token_factory):
    token = agent_token_factory(["read"])
    headers = {"Authorization": f"Bearer {token}"}

    resp = authed_client.get("/api/v1/mcp/site-config", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "prompts" in body
    assert body["prompts"]["text_generation_prompt"] == "Test Persona Default"
    assert body["prompts"]["image_generation_prompt"] == "Test Image Style Default"
    assert body["prompts"]["post_quality_checklist"] == "1. Check spelling"
    assert "extractive_prompts" in body
    assert "summary" in body["extractive_prompts"]
    assert "faqs" in body["extractive_prompts"]
    assert "sitename" in body
    assert "agent" in body
    assert body["agent"]["ai_publish_autonomy"] == "require_approval"
    assert body["agent"]["ai_metadata_scope"] == "allow_metadata"


def test_get_site_config_tells_glowbot_sitename_and_autonomy(authed_client, agent_token_factory):
    from services.ai_settings_service import load_ai_settings, save_ai_settings

    token = agent_token_factory(["read"])
    headers = {"Authorization": f"Bearer {token}"}
    try:
        patch = authed_client.patch("/api/sites/default", json={"sitename": "Wiki Site"})
        assert patch.status_code == 200, patch.text
        existing = load_ai_settings("default")
        save_ai_settings("default", {**existing, "ai_publish_autonomy": "autonomous"})

        resp = authed_client.get("/api/v1/mcp/site-config", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["sitename"] == "Wiki Site"
        assert body["agent"]["ai_publish_autonomy"] == "autonomous"

        prompts = authed_client.get("/api/v1/mcp/prompts", headers=headers)
        assert prompts.status_code == 200
        pdata = prompts.json()
        assert pdata["sitename"] == "Wiki Site"
        assert pdata["ai_publish_autonomy"] == "autonomous"
    finally:
        authed_client.patch("/api/sites/default", json={"sitename": ""})


def test_multisite_prompts_isolation(authed_client, agent_token_factory):
    from services.site_service import create_site, get_site

    if get_site("secondary") is None:
        create_site("secondary", "Secondary Site")

    save_ai_settings("secondary", {
        "text_generation_prompt": "Secondary Persona",
        "image_generation_prompt": "Secondary Image Style",
        "post_quality_checklist": "Secondary Checklist",
    })

    token_default = agent_token_factory(["read"], site_id="default")
    token_secondary = agent_token_factory(["read"], site_id="secondary")

    resp_default = authed_client.get(
        "/api/v1/mcp/prompts", headers={"Authorization": f"Bearer {token_default}"}
    )
    resp_secondary = authed_client.get(
        "/api/v1/mcp/prompts", headers={"Authorization": f"Bearer {token_secondary}"}
    )

    assert resp_default.status_code == 200
    assert resp_default.json()["text_generation_prompt"] == "Test Persona Default"
    assert resp_default.json()["site_id"] == "default"

    assert resp_secondary.status_code == 200
    assert resp_secondary.json()["text_generation_prompt"] == "Secondary Persona"
    assert resp_secondary.json()["site_id"] == "secondary"
