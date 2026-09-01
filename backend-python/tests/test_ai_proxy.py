"""Phase 1 invariants for the AI proxy endpoint.

These tests lock in the contract documented in
`core/docs/AI-PenCMS-implementation_plan.md` § "Phase 1 — Critical
implementation notes". They mock the upstream provider with `respx` so no
real network call is made.

Scope:
- Auth (cookie + Bearer).
- SSRF guard on `X-Pen-AI-Base-URL`.
- Anthropic hard-fail (501).
- Local-endpoint keyless exception (Ollama).
- Non-local endpoint without key → 400.
- Missing model → 400.
- Upstream error relay (401 from provider → 401 to client).
- Streaming `[DONE]` relay.
- Non-streaming JSON pass-through.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

UPSTREAM_CHAT_URL = "https://api.openai.com/v1/chat/completions"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_ai_chat_requires_authentication(client):
    """No cookie, no Bearer → 401 from get_current_user."""
    resp = client.post(
        "/api/ai/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401


def test_ai_chat_accepts_bearer_token(authed_client):
    """Agent Bearer tokens (the MCP gateway auth path) must work too."""
    # `authed_client` logged in via cookie; mint a Bearer by exchanging an
    # agent key so we can test the same code path the MCP gateway will use.
    resp = authed_client.post(
        "/api/auth/keys", json={"name": "ai-proxy-bearer", "scopes": ["read", "write"]}
    )
    assert resp.status_code == 200
    raw_key = resp.json()["key"]

    resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
    assert resp.status_code == 200
    bearer = resp.json()["access_token"]

    # Use the bearer with a mocked Ollama (local → no API key required).
    with respx.mock(base_url="http://localhost:11434") as mock:
        mock.post("/v1/chat/completions").respond(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        )
        resp = authed_client.post(
            "/api/ai/chat",
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Pen-AI-Base-URL": "http://localhost:11434/v1",
                "X-Pen-AI-Model": "llama3",
            },
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
            },
        )
    assert resp.status_code == 200
    assert resp.json()["choices"][0]["message"]["content"] == "ok"


# ---------------------------------------------------------------------------
# SSRF guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/v1",  # cloud metadata endpoint
        "http://0.0.0.0:8000/v1",  # unspecified network
        "ftp://example.com/v1",  # disallowed scheme
        "file:///etc/passwd",  # disallowed scheme
        "javascript:alert(1)",  # disallowed scheme
    ],
)
def test_ssrf_rejected(authed_client, url):
    resp = authed_client.post(
        "/api/ai/chat",
        headers={
            "X-Pen-AI-Base-URL": url,
            "X-Pen-AI-Key": "sk-fake",
            "X-Pen-AI-Model": "gpt-4o",
        },
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        },
    )
    assert resp.status_code == 400
    assert "Invalid or restricted Base URL" in resp.json()["detail"]


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434/v1",  # Ollama
        "http://127.0.0.1:11434/v1",  # loopback IP
    ],
)
def test_ssrf_loopback_allowed_keyless(authed_client, url):
    """Loopback endpoints pass the SSRF guard AND qualify for the keyless
    exception (local Ollama / LM Studio don't require an API key)."""
    with respx.mock(base_url=url.rsplit("/v1", 1)[0]) as mock:
        mock.post("/v1/chat/completions").respond(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        )
        resp = authed_client.post(
            "/api/ai/chat",
            headers={
                "X-Pen-AI-Base-URL": url,
                "X-Pen-AI-Model": "llama3",
            },
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
            },
        )
    assert resp.status_code == 200


def test_ssrf_rfc1918_allowed_but_requires_key(authed_client):
    """RFC1918 private ranges (10/172.16/192.168) pass the SSRF guard —
    they're allowed to enable home-lab connectivity — but they are NOT
    considered loopback, so they still require an API key.

    This is a deliberate two-tier policy:
      - SSRF guard:   allows RFC1918 (home labs can reach a provider on the LAN)
      - Keyless exception: only true loopback (Ollama on the same box)
    """
    url = "http://192.168.1.100:8080/v1"

    # 1. Without a key → 400 "API Key is required" (NOT "Invalid Base URL" —
    #    which proves the SSRF guard let the URL through).
    resp = authed_client.post(
        "/api/ai/chat",
        headers={
            "X-Pen-AI-Base-URL": url,
            "X-Pen-AI-Model": "llama3",
        },
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        },
    )
    assert resp.status_code == 400
    assert "API Key is required" in resp.json()["detail"]

    # 2. With a key → the request reaches the (mocked) upstream.
    with respx.mock(base_url="http://192.168.1.100:8080") as mock:
        mock.post("/v1/chat/completions").respond(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        )
        resp = authed_client.post(
            "/api/ai/chat",
            headers={
                "X-Pen-AI-Base-URL": url,
                "X-Pen-AI-Key": "sk-lan-key",
                "X-Pen-AI-Model": "llama3",
            },
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
            },
        )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Provider routing
# ---------------------------------------------------------------------------


def test_anthropic_endpoint_returns_501(authed_client):
    resp = authed_client.post(
        "/api/ai/chat",
        headers={
            "X-Pen-AI-Base-URL": "https://api.anthropic.com/v1",
            "X-Pen-AI-Key": "sk-ant-fake",
            "X-Pen-AI-Model": "claude-3",
        },
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        },
    )
    assert resp.status_code == 501
    assert "Anthropic adapter" in resp.json()["detail"]


def test_anthropic_path_spoof_is_not_treated_as_anthropic(authed_client):
    """Substring host checks must not 501 when api.anthropic.com is only in the path."""
    with respx.mock(base_url="https://evil.example") as mock:
        mock.post("/api.anthropic.com/v1/chat/completions").respond(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        )
        resp = authed_client.post(
            "/api/ai/chat",
            headers={
                "X-Pen-AI-Base-URL": "https://evil.example/api.anthropic.com/v1",
                "X-Pen-AI-Key": "sk-fake",
                "X-Pen-AI-Model": "gpt-4o",
            },
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
            },
        )
    assert resp.status_code == 200
    assert resp.json()["choices"][0]["message"]["content"] == "ok"


def test_non_local_endpoint_requires_api_key(authed_client):
    """A hosted provider without an API key must be rejected before any
    upstream call is attempted."""
    resp = authed_client.post(
        "/api/ai/chat",
        headers={
            "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
            # No X-Pen-AI-Key
            "X-Pen-AI-Model": "gpt-4o",
        },
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        },
    )
    assert resp.status_code == 400
    assert "API Key is required" in resp.json()["detail"]


def test_missing_model_returns_400(authed_client):
    """If neither the body nor the header specifies a model, we must fail
    fast rather than letting the upstream return an opaque error.

    No respx mock is registered: if the proxy incorrectly forwards the
    request, the test will fail with a network/connection error rather
    than a false-negative 200."""
    resp = authed_client.post(
        "/api/ai/chat",
        headers={
            "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
            "X-Pen-AI-Key": "sk-fake",
            # No X-Pen-AI-Model
        },
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
            # No model in body either
        },
    )
    assert resp.status_code == 400
    assert "Model must be specified" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Upstream error relay
# ---------------------------------------------------------------------------


def test_upstream_401_is_relayed(authed_client):
    """When the provider rejects the key (401), the proxy must relay the
    status code and a meaningful body — not a 500 or a hang."""
    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").respond(
            401, json={"error": "Invalid API key"}
        )
        resp = authed_client.post(
            "/api/ai/chat",
            headers={
                "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
                "X-Pen-AI-Key": "sk-invalid",
                "X-Pen-AI-Model": "gpt-4o",
            },
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
            },
        )
    assert resp.status_code == 401
    # The detail must surface the upstream message, not a generic string.
    body = resp.json()
    assert "Invalid API key" in str(body.get("detail", ""))


def test_upstream_html_response_is_sanitised(authed_client):
    """Some providers return HTML error pages (e.g. a 502 from a gateway in
    front of the LLM). The proxy must not pass raw HTML through as detail."""
    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").respond(
            502,
            text="<html><body>Bad Gateway</body></html>",
        )
        resp = authed_client.post(
            "/api/ai/chat",
            headers={
                "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
                "X-Pen-AI-Key": "sk-fake",
                "X-Pen-AI-Model": "gpt-4o",
            },
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
            },
        )
    assert resp.status_code == 502
    detail = str(resp.json().get("detail", ""))
    assert "<html>" not in detail.lower()
    assert "HTML" in detail or "Endpoint URL" in detail


# ---------------------------------------------------------------------------
# Non-streaming happy path
# ---------------------------------------------------------------------------


def test_non_streaming_passthrough(authed_client):
    payload = {
        "choices": [{"message": {"role": "assistant", "content": "Hello world"}}]
    }
    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").respond(200, json=payload)
        resp = authed_client.post(
            "/api/ai/chat",
            headers={
                "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
                "X-Pen-AI-Key": "sk-fake",
                "X-Pen-AI-Model": "gpt-4o",
            },
            json={
                "messages": [{"role": "user", "content": "Say hello"}],
                "stream": False,
            },
        )
    assert resp.status_code == 200
    assert resp.json() == payload


def test_authorization_header_forwarded_to_upstream(authed_client):
    """The proxy must attach `Authorization: Bearer {api_key}` when calling
    a non-local upstream. This is the zero-knowledge contract: the key
    travels per-request, never persisted."""
    captured = {}

    def _capture(request: httpx.Request):
        captured["auth"] = request.headers.get("authorization", "")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").mock(side_effect=_capture)
        authed_client.post(
            "/api/ai/chat",
            headers={
                "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
                "X-Pen-AI-Key": "sk-test-key-123",
                "X-Pen-AI-Model": "gpt-4o",
            },
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
            },
        )
    assert captured["auth"] == "Bearer sk-test-key-123"


def test_no_authorization_header_for_local_upstream(authed_client):
    """Local upstreams (Ollama) must NOT receive an Authorization header —
    Ollama rejects it with 401 if a key is configured in its config."""
    captured = {}

    def _capture(request: httpx.Request):
        captured["auth"] = request.headers.get("authorization", "")
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    with respx.mock(base_url="http://localhost:11434") as mock:
        mock.post("/v1/chat/completions").mock(side_effect=_capture)
        authed_client.post(
            "/api/ai/chat",
            headers={
                "X-Pen-AI-Base-URL": "http://localhost:11434/v1",
                # Even if a key is mistakenly provided, local endpoints
                # must not forward it (matches `is_local` branch in code).
                "X-Pen-AI-Key": "sk-should-be-ignored",
                "X-Pen-AI-Model": "llama3",
            },
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
            },
        )
    assert captured["auth"] == ""


# ---------------------------------------------------------------------------
# Streaming happy path
# ---------------------------------------------------------------------------


def test_streaming_relays_sse_chunks_and_done_sentinel(authed_client):
    """The proxy must forward each `data:` line as-is, including `[DONE]`,
    so the sidebar's SSE parser receives the same shape it would from a
    direct connection to the provider."""
    sse_body = (
        b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
        b'data: {"choices":[{"delta":{"content":" world"}}]}\n\n'
        b"data: [DONE]\n\n"
    )
    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").respond(
            200, content=sse_body, headers={"content-type": "text/event-stream"}
        )
        resp = authed_client.post(
            "/api/ai/chat",
            headers={
                "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
                "X-Pen-AI-Key": "sk-fake",
                "X-Pen-AI-Model": "gpt-4o",
            },
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    # The proxy must forward the bytes verbatim — including the [DONE]
    # sentinel and the inter-event blank lines. This is what the sidebar's
    # SSE parser depends on.
    received = resp.content
    assert b'data: {"choices":[{"delta":{"content":"Hello"}}]}' in received
    assert b'data: {"choices":[{"delta":{"content":" world"}}]}' in received
    assert b"data: [DONE]" in received


def test_streaming_upstream_error_relayed_as_error_status(authed_client):
    """If the upstream errors *during* the streaming request setup (i.e.
    before the first chunk), the proxy must relay the status code rather
    than return a 200 with an empty stream."""
    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").respond(
            429, json={"error": "Rate limit exceeded"}
        )
        resp = authed_client.post(
            "/api/ai/chat",
            headers={
                "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
                "X-Pen-AI-Key": "sk-fake",
                "X-Pen-AI-Model": "gpt-4o",
            },
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
    assert resp.status_code == 429
    assert "Rate limit" in str(resp.json().get("detail", ""))


# ---------------------------------------------------------------------------
# Body / model fallback
# ---------------------------------------------------------------------------


def test_body_model_overrides_header_model(authed_client):
    """If the request body specifies `model`, it must win over the
    `X-Pen-AI-Model` header — this is how per-request model overrides
    work (e.g. the sidebar letting the user pick a different model)."""
    captured = {}

    def _capture(request: httpx.Request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").mock(side_effect=_capture)
        authed_client.post(
            "/api/ai/chat",
            headers={
                "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
                "X-Pen-AI-Key": "sk-fake",
                "X-Pen-AI-Model": "gpt-4o",
            },
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "model": "gpt-4o-mini",  # override
                "stream": False,
            },
        )
    assert captured["body"]["model"] == "gpt-4o-mini"


def test_header_model_used_when_body_omits_model(authed_client):
    captured = {}

    def _capture(request: httpx.Request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").mock(side_effect=_capture)
        authed_client.post(
            "/api/ai/chat",
            headers={
                "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
                "X-Pen-AI-Key": "sk-fake",
                "X-Pen-AI-Model": "gpt-4o-mini",
            },
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                # No `model` field → header model must be injected
            },
        )
    assert captured["body"]["model"] == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Tool calling support
# ---------------------------------------------------------------------------


def test_tool_calling_payload_relayed(authed_client):
    """The proxy must accept `tools` and `tool_choice` in the request body,
    and messages containing `tool_calls` or `tool_call_id` / `name`."""
    captured = {}

    def _capture(request: httpx.Request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_123",
                                    "type": "function",
                                    "function": {
                                        "name": "get_site_config",
                                        "arguments": "{}"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        )

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_site_config",
                "description": "Read site settings",
                "parameters": {"type": "object", "properties": {}}
            }
        }
    ]

    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").mock(side_effect=_capture)
        resp = authed_client.post(
            "/api/ai/chat",
            headers={
                "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
                "X-Pen-AI-Key": "sk-fake",
                "X-Pen-AI-Model": "gpt-4o",
            },
            json={
                "messages": [
                    {"role": "user", "content": "Get config"},
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "get_site_config",
                                    "arguments": "{}"
                                }
                            }
                        ]
                    },
                    {
                        "role": "tool",
                        "name": "get_site_config",
                        "tool_call_id": "call_123",
                        "content": "{\"sitename\": \"PenCMS\"}"
                    }
                ],
                "model": "gpt-4o",
                "stream": False,
                "tools": tools,
                "tool_choice": "auto"
            },
        )

    assert resp.status_code == 200
    assert "tool_calls" in resp.json()["choices"][0]["message"]
    
    # Assert upstream captured body has all tool keys
    body = captured["body"]
    assert body["tools"] == tools
    assert body["tool_choice"] == "auto"
    assert body["messages"][1]["tool_calls"][0]["id"] == "call_123"
    assert body["messages"][2]["role"] == "tool"
    assert body["messages"][2]["tool_call_id"] == "call_123"
    assert body["messages"][2]["name"] == "get_site_config"


# ---------------------------------------------------------------------------
# AI Images Proxy Tests
# ---------------------------------------------------------------------------


def test_ai_images_requires_authentication(client):
    """No cookie, no Bearer → 401 from get_current_user."""
    resp = client.post(
        "/api/ai/images",
        json={"prompt": "test image"},
    )
    assert resp.status_code == 401


def test_ai_images_ssrf_rejected(authed_client):
    """Verify SSRF protection rejects cloud metadata IP or invalid schemes."""
    resp = authed_client.post(
        "/api/ai/images",
        headers={
            "X-Pen-AI-Base-URL": "http://169.254.169.254/v1",
            "X-Pen-AI-Key": "sk-fake",
            "X-Pen-AI-Model": "stable-diffusion",
        },
        json={"prompt": "test image"},
    )
    assert resp.status_code == 400
    assert "Invalid or restricted Base URL" in resp.json()["detail"]


def test_ai_images_key_required_non_local(authed_client):
    """Non-local endpoints require an API Key."""
    resp = authed_client.post(
        "/api/ai/images",
        headers={
            "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
            "X-Pen-AI-Model": "dall-e-3",
        },
        json={"prompt": "test image"},
    )
    assert resp.status_code == 400
    assert "AI Provider API Key is required" in resp.json()["detail"]


def test_ai_images_key_not_required_local(authed_client):
    """Local endpoints (e.g. localhost Ollama) do not require an API Key."""
    with respx.mock(base_url="http://localhost:11434") as mock:
        mock.post("/v1/images/generations").respond(
            200, json={"data": [{"b64_json": "fake_base64"}]}
        )
        resp = authed_client.post(
            "/api/ai/images",
            headers={
                "X-Pen-AI-Base-URL": "http://localhost:11434/v1",
                "X-Pen-AI-Model": "stable-diffusion",
            },
            json={"prompt": "test image"},
        )
    assert resp.status_code == 200
    assert resp.json()["data"][0]["b64_json"] == "fake_base64"


def test_ai_images_missing_model(authed_client):
    """Model must be specified in headers or body."""
    resp = authed_client.post(
        "/api/ai/images",
        headers={
            "X-Pen-AI-Base-URL": "http://localhost:11434/v1",
        },
        json={"prompt": "test image"},
    )
    assert resp.status_code == 400
    assert "Model must be specified" in resp.json()["detail"]


def test_ai_images_upstream_error_relay(authed_client):
    """Relay downstream errors from upstream provider."""
    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/images/generations").respond(
            401, json={"error": {"message": "Invalid API Key"}}
        )
        resp = authed_client.post(
            "/api/ai/images",
            headers={
                "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
                "X-Pen-AI-Key": "sk-invalid",
                "X-Pen-AI-Model": "dall-e-3",
            },
            json={"prompt": "test image"},
        )
    assert resp.status_code == 401
    assert "Invalid API Key" in resp.json()["detail"]


def test_ai_images_payload_normalization_plan_a(authed_client):
    """Plan A endpoint: verify that size/width/height converts to resolution, resolution is sent, and size/width/height are deleted.
    Also verify that x-api-key header is used instead of Authorization.
    """
    captured = {}

    def _capture(request):
        captured["body"] = json.loads(request.read())
        captured["headers"] = request.headers
        return httpx.Response(200, json={"data": [{"b64_json": "plan_a"}]})

    with respx.mock(base_url="https://nano-gpt.com") as mock:
        mock.post("/api/v1/images").mock(side_effect=_capture)
        resp = authed_client.post(
            "/api/ai/images",
            headers={
                "X-Pen-AI-Base-URL": "https://nano-gpt.com/api/v1/images",
                "X-Pen-AI-Key": "sk-fake",
                "X-Pen-AI-Model": "qwen-image",
            },
            json={
                "prompt": "test image",
                "size": "512x512",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["data"][0]["b64_json"] == "plan_a"
    assert "size" not in captured["body"]
    assert "width" not in captured["body"]
    assert "height" not in captured["body"]
    assert captured["body"]["resolution"] == "512x512"
    assert captured["headers"].get("x-api-key") == "sk-fake"
    assert "Authorization" not in captured["headers"]


def test_ai_images_nano_gpt_path_spoof_uses_bearer(authed_client):
    """nano-gpt.com in the path must not switch auth to x-api-key."""
    captured = {}

    def _capture(request):
        captured["headers"] = request.headers
        return httpx.Response(200, json={"data": [{"b64_json": "spoof"}]})

    with respx.mock(base_url="https://evil.example") as mock:
        mock.post("/nano-gpt.com/api/v1/images").mock(side_effect=_capture)
        resp = authed_client.post(
            "/api/ai/images",
            headers={
                "X-Pen-AI-Base-URL": "https://evil.example/nano-gpt.com/api/v1/images",
                "X-Pen-AI-Key": "sk-fake",
                "X-Pen-AI-Model": "qwen-image",
            },
            json={"prompt": "test image"},
        )

    assert resp.status_code == 200
    assert captured["headers"].get("Authorization") == "Bearer sk-fake"
    assert "x-api-key" not in captured["headers"]


def test_ai_images_payload_normalization_plan_b(authed_client):
    """Plan B endpoint: verify that width/height/resolution convert to size, size is sent, and others are deleted.
    Also verify that Authorization header is used.
    """
    captured = {}

    def _capture(request):
        captured["body"] = json.loads(request.read())
        captured["headers"] = request.headers
        return httpx.Response(200, json={"data": [{"b64_json": "plan_b"}]})

    with respx.mock(base_url="https://nano-gpt.com") as mock:
        mock.post("/v1/images/generations").mock(side_effect=_capture)
        resp = authed_client.post(
            "/api/ai/images",
            headers={
                "X-Pen-AI-Base-URL": "https://nano-gpt.com/v1/images/generations",
                "X-Pen-AI-Key": "sk-fake",
                "X-Pen-AI-Model": "qwen-image",
            },
            json={
                "prompt": "test image",
                "width": 512,
                "height": 512,
            },
        )

    assert resp.status_code == 200
    assert resp.json()["data"][0]["b64_json"] == "plan_b"
    assert "width" not in captured["body"]
    assert "height" not in captured["body"]
    assert "resolution" not in captured["body"]
    assert captured["body"]["size"] == "512x512"
    assert captured["headers"].get("Authorization") == "Bearer sk-fake"
    assert "x-api-key" not in captured["headers"]


def test_ai_disabled_blocks_endpoints(authed_client):
    """When use_ai is set to false in config.ini, proxy endpoints must return 400."""
    import config
    ini_path = config.BASE_DIR / "config.ini"
    
    # Write disabled config
    with open(ini_path, "w") as f:
        f.write("[General]\nuse_ai = false\n")
        
    try:
        # 1. Chat proxy
        resp = authed_client.post(
            "/api/ai/chat",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 400
        assert "AI features are disabled" in resp.json()["detail"]

        # 2. Images proxy
        resp = authed_client.post(
            "/api/ai/images",
            json={"prompt": "test"},
        )
        assert resp.status_code == 400
        assert "AI features are disabled" in resp.json()["detail"]

        # 3. Schemas endpoint
        resp = authed_client.get("/api/ai/schemas")
        assert resp.status_code == 400
        assert "AI features are disabled" in resp.json()["detail"]

        # 4. Extractive fill (Session 5 / PR-C)
        resp = authed_client.post(
            "/api/ai/extract",
            json={"field": "summary", "body": "Helsinki is the capital of Finland."},
        )
        assert resp.status_code == 400
        assert "AI features are disabled" in resp.json()["detail"]
    finally:
        # Clean up config.ini
        if ini_path.exists():
            ini_path.unlink()


def test_prompt_settings_endpoint_and_injection(authed_client):
    """Verify Prompt Settings can be read, written, and injected into text/image payloads."""
    import config
    from services.ai_settings_service import settings_path_for_site

    settings_file = settings_path_for_site("default")
    legacy_file = config.BASE_DIR / "data" / "ai-settings.json"

    # 1. Test get settings defaults
    if settings_file.exists():
        settings_file.unlink()
    if legacy_file.exists():
        legacy_file.unlink()

    resp = authed_client.get("/api/ai/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["text_generation_prompt"] == ""
    assert data["image_generation_prompt"] == ""
    assert data["post_quality_checklist"] == ""

    # 2. Test put settings
    payload = {
        "ai_publish_autonomy": "autonomous",
        "ai_metadata_scope": "body_only",
        "text_generation_prompt": "Always write in French.",
        "image_generation_prompt": "Use 8k resolution, photorealistic.",
        "post_quality_checklist": "1. Is it written in French?"
    }
    resp = authed_client.put("/api/ai/settings", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["text_generation_prompt"] == "Always write in French."
    assert data["image_generation_prompt"] == "Use 8k resolution, photorealistic."
    assert data["post_quality_checklist"] == "1. Is it written in French?"
    assert settings_file.exists()

    # Verify persistence
    resp = authed_client.get("/api/ai/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["text_generation_prompt"] == "Always write in French."
    assert data["post_quality_checklist"] == "1. Is it written in French?"

    # 3. Test text prompt injection into chat proxy (editor surface only)
    captured_chat = {}
    def _capture_chat(request: httpx.Request):
        captured_chat["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "Bonjour"}}]})

    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").mock(side_effect=_capture_chat)
        resp = authed_client.post(
            "/api/ai/chat",
            headers={
                "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
                "X-Pen-AI-Key": "sk-fake",
                "X-Pen-AI-Model": "gpt-4o",
            },
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "surface": "editor",
            },
        )
    expected_wrapped_1 = (
        "## CRITICAL SYSTEM INSTRUCTION: PERSONA SEGREGATION\n"
        "You must strictly separate your conversational persona from the style of the content you generate:\n"
        "1. **Your Chat Persona**: In all your conversational responses/chat bubbles to the user, you MUST speak as a normal, friendly, professional, and helpful SEO/writing assistant. Under no circumstances should you speak in the style of the custom prompt (e.g., do NOT speak like a pirate, do NOT use pirate speak, slang, or custom characters in your chat messages).\n"
        "2. **Post/Post Content**: The custom style prompt below applies ONLY to the actual post/post draft, body, headlines, and content you write or edit using tools (e.g., inside the `body` parameter of `write_content_file`, `replace_selection`, or `insert_at_cursor`):\n"
        "   > \"Always write in French.\"\n"
        "Note: If the custom style prompt contains absolute instructions like 'every sentence', 'always', 'all text', or similar, these rules apply SOLELY to the post content you produce and write to files, NOT to your conversational replies to the user."
    )
    assert resp.status_code == 200
    messages = captured_chat["body"]["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == expected_wrapped_1
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Hello"
    assert "surface" not in captured_chat["body"]

    # Test text prompt prepended to an existing system message
    captured_chat_system = {}
    def _capture_chat_system(request: httpx.Request):
        captured_chat_system["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "Bonjour"}}]})

    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").mock(side_effect=_capture_chat_system)
        resp = authed_client.post(
            "/api/ai/chat",
            headers={
                "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
                "X-Pen-AI-Key": "sk-fake",
                "X-Pen-AI-Model": "gpt-4o",
            },
            json={
                "messages": [
                    {"role": "system", "content": "Initial system instructions."},
                    {"role": "user", "content": "Hello"}
                ],
                "surface": "editor",
            },
        )
    assert resp.status_code == 200
    messages = captured_chat_system["body"]["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == f"Initial system instructions.\n\n{expected_wrapped_1}"
    assert "surface" not in captured_chat_system["body"]

    # Non-editor surfaces must not receive PERSONA SEGREGATION / text_generation_prompt
    for non_editor_surface in ("navigation", "customize"):
        captured_skip = {}

        def _capture_skip(request: httpx.Request, _cap=captured_skip):
            _cap["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
            )

        with respx.mock(base_url="https://api.openai.com") as mock:
            mock.post("/v1/chat/completions").mock(side_effect=_capture_skip)
            resp = authed_client.post(
                "/api/ai/chat",
                headers={
                    "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
                    "X-Pen-AI-Key": "sk-fake",
                    "X-Pen-AI-Model": "gpt-4o",
                },
                json={
                    "messages": [
                        {"role": "system", "content": "Surface system prompt."},
                        {"role": "user", "content": "Hello"},
                    ],
                    "surface": non_editor_surface,
                },
            )
        assert resp.status_code == 200
        skip_messages = captured_skip["body"]["messages"]
        assert len(skip_messages) == 2
        assert skip_messages[0]["content"] == "Surface system prompt."
        assert "PERSONA SEGREGATION" not in skip_messages[0]["content"]
        assert "Always write in French." not in skip_messages[0]["content"]
        assert "surface" not in captured_skip["body"]

    # Omitting surface is opt-in: no persona injection
    captured_omit = {}

    def _capture_omit(request: httpx.Request):
        captured_omit["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
        )

    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").mock(side_effect=_capture_omit)
        resp = authed_client.post(
            "/api/ai/chat",
            headers={
                "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
                "X-Pen-AI-Key": "sk-fake",
                "X-Pen-AI-Model": "gpt-4o",
            },
            json={
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
    assert resp.status_code == 200
    omit_messages = captured_omit["body"]["messages"]
    assert len(omit_messages) == 1
    assert omit_messages[0]["role"] == "user"
    assert omit_messages[0]["content"] == "Hello"

    # 4. Test image prompt injection into image proxy
    captured_img = {}
    def _capture_img(request: httpx.Request):
        captured_img["body"] = json.loads(request.content)
        return httpx.Response(200, json={"data": [{"b64_json": "plan_b"}]})
        
    with respx.mock(base_url="https://nano-gpt.com") as mock:
        mock.post("/v1/images/generations").mock(side_effect=_capture_img)
        resp = authed_client.post(
            "/api/ai/images",
            headers={
                "X-Pen-AI-Base-URL": "https://nano-gpt.com/v1/images/generations",
                "X-Pen-AI-Key": "sk-fake",
                "X-Pen-AI-Model": "qwen-image",
            },
            json={
                "prompt": "Draw a cat",
                "width": 512,
                "height": 512,
            },
        )
    assert resp.status_code == 200
    assert captured_img["body"]["prompt"] == "Draw a cat, Use 8k resolution, photorealistic."

    # Clean up
    if settings_file.exists():
        settings_file.unlink()


def test_ai_settings_per_site_isolation_and_legacy_migrate(authed_client):
    """Per-site prompts/guardrails do not bleed; legacy file maps to default only."""
    import json

    import config
    from services.ai_settings_service import load_ai_settings, settings_path_for_site
    from services.site_service import create_site, ensure_sites_initialized, get_site

    ensure_sites_initialized()
    if get_site("aiwiki") is None:
        create_site("aiwiki", "AI Wiki")
    site_b = "aiwiki"

    default_path = settings_path_for_site("default")
    wiki_path = settings_path_for_site(site_b)
    legacy = config.BASE_DIR / "data" / "ai-settings.json"
    for p in (default_path, wiki_path, legacy):
        if p.exists():
            p.unlink()

    # Legacy install-global file becomes default on first load
    legacy.parent.mkdir(parents=True, exist_ok=True)
    with open(legacy, "w", encoding="utf-8") as f:
        json.dump(
            {
                "ai_publish_autonomy": "autonomous",
                "ai_metadata_scope": "body_only",
                "text_generation_prompt": "Legacy default voice.",
                "image_generation_prompt": "",
                "post_quality_checklist": "Legacy checklist",
            },
            f,
        )

    migrated = load_ai_settings("default")
    assert migrated["text_generation_prompt"] == "Legacy default voice."
    assert migrated["ai_publish_autonomy"] == "autonomous"
    assert default_path.exists()
    assert not legacy.exists()

    # Other site (no file) gets empty prompts + conservative guardrails
    wiki_defaults = load_ai_settings(site_b)
    assert wiki_defaults["text_generation_prompt"] == ""
    assert wiki_defaults["image_generation_prompt"] == ""
    assert wiki_defaults["post_quality_checklist"] == ""
    assert wiki_defaults["ai_publish_autonomy"] == "require_approval"
    assert wiki_defaults["ai_metadata_scope"] == "allow_metadata"

    # PUT via API for site_b must not change default
    resp = authed_client.put(
        "/api/ai/settings",
        headers={"X-Pen-Site-Id": site_b},
        json={
            "ai_publish_autonomy": "restricted",
            "ai_metadata_scope": "body_only",
            "text_generation_prompt": "Wiki voice only.",
            "image_generation_prompt": "Wiki images.",
            "post_quality_checklist": "Wiki QA",
        },
    )
    assert resp.status_code == 200
    assert wiki_path.exists()

    resp = authed_client.get("/api/ai/settings", headers={"X-Pen-Site-Id": site_b})
    assert resp.status_code == 200
    assert resp.json()["text_generation_prompt"] == "Wiki voice only."
    assert resp.json()["ai_publish_autonomy"] == "restricted"

    resp = authed_client.get("/api/ai/settings", headers={"X-Pen-Site-Id": "default"})
    assert resp.status_code == 200
    assert resp.json()["text_generation_prompt"] == "Legacy default voice."
    assert resp.json()["ai_publish_autonomy"] == "autonomous"

    # Chat injection uses active site prompts (site_b), not default
    captured_chat = {}

    def _capture_chat(request: httpx.Request):
        captured_chat["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
        )

    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").mock(side_effect=_capture_chat)
        resp = authed_client.post(
            "/api/ai/chat",
            headers={
                "X-Pen-Site-Id": site_b,
                "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
                "X-Pen-AI-Key": "sk-fake",
                "X-Pen-AI-Model": "gpt-4o",
            },
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "surface": "editor",
            },
        )
    assert resp.status_code == 200
    assert "Wiki voice only." in captured_chat["body"]["messages"][0]["content"]
    assert "Legacy default voice." not in captured_chat["body"]["messages"][0]["content"]
    assert "surface" not in captured_chat["body"]

    for p in (default_path, wiki_path, legacy):
        if p.exists():
            p.unlink()
