"""Session 5 / PR-C + Session 6 / PR-D — extractive ``POST /api/ai/extract``.

The wand is preview-only. Persistence is the editor (or Session 7 dashboard).
``field=summary`` and ``field=faqs`` are accepted.
"""

from __future__ import annotations

import json

import respx

from routers.ai_proxy import FAQS_EXTRACT_SYSTEM_PROMPT, SUMMARY_EXTRACT_SYSTEM_PROMPT

UPSTREAM_CHAT_URL = "https://api.openai.com/v1/chat/completions"

BODY = (
    "Helsinki is the capital of Finland. The city sits on the Gulf of Finland "
    "and is known for its harbour, design district, and winter darkness."
)
NUTSHELL = "Helsinki is Finland's capital on the Gulf of Finland."
EXPLAINER = (
    "PenCMS stores FAQs as a first-class list of question and answer pairs on "
    "the post. Empty lists emit no FAQPage schema. Poetry and wire briefs should "
    "leave the list empty rather than inventing Q&A. A Backgrounder uses the same "
    "list with different chrome. The wand is extractive: it only restates what "
    "the body already answers."
)
FAQ_PAIRS = [
    {
        "q": "How does PenCMS store FAQs?",
        "a": "As a first-class list of question and answer pairs on the post.",
    },
    {
        "q": "What happens when the FAQ list is empty?",
        "a": "Empty lists emit no FAQPage schema.",
    },
    {
        "q": "Should poetry get invented FAQs?",
        "a": "Poetry and wire briefs should leave the list empty rather than inventing Q&A.",
    },
    {
        "q": "What is a Backgrounder?",
        "a": "A Backgrounder uses the same list with different chrome.",
    },
]
POEM = (
    "Roses are red.\nViolets are blue.\nThe harbour light flickers twice, then none."
)
EXISTING_FAQS = [{"q": "Old question?", "a": "Old answer."}]


def _headers(**extra):
    headers = {
        "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
        "X-Pen-AI-Key": "sk-fake",
        "X-Pen-AI-Model": "gpt-4o",
    }
    headers.update(extra)
    return headers


def _payload(**extra):
    payload = {
        "field": "summary",
        "body": BODY,
        "current_value": "",
        "replace": False,
    }
    payload.update(extra)
    return payload


def test_extract_requires_authentication(client):
    resp = client.post("/api/ai/extract", json=_payload())
    assert resp.status_code == 401


def test_extract_empty_summary_fills(authed_client):
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(UPSTREAM_CHAT_URL).respond(
            200, json={"choices": [{"message": {"content": NUTSHELL}}]}
        )
        resp = authed_client.post(
            "/api/ai/extract",
            headers=_headers(),
            json=_payload(current_value=""),
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["field"] == "summary"
    assert data["value"] == NUTSHELL
    assert route.called


def test_extract_whitespace_current_value_is_empty(authed_client):
    with respx.mock(assert_all_called=True) as mock:
        mock.post(UPSTREAM_CHAT_URL).respond(
            200, json={"choices": [{"message": {"content": NUTSHELL}}]}
        )
        resp = authed_client.post(
            "/api/ai/extract",
            headers=_headers(),
            json=_payload(current_value="   \n\t  "),
        )
    assert resp.status_code == 200
    assert resp.json()["value"] == NUTSHELL


def test_extract_nonempty_refuses_without_replace(authed_client):
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(UPSTREAM_CHAT_URL).respond(
            200, json={"choices": [{"message": {"content": "should not run"}}]}
        )
        resp = authed_client.post(
            "/api/ai/extract",
            headers=_headers(),
            json=_payload(current_value="An existing nutshell.", replace=False),
        )
    assert resp.status_code == 409, resp.text
    detail = resp.json()["detail"]
    assert detail["code"] == "non_empty"
    assert detail["field"] == "summary"
    assert "replace=true" in detail["message"]
    assert not route.called


def test_extract_replace_applies(authed_client):
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(UPSTREAM_CHAT_URL).respond(
            200, json={"choices": [{"message": {"content": NUTSHELL}}]}
        )
        resp = authed_client.post(
            "/api/ai/extract",
            headers=_headers(),
            json=_payload(current_value="An existing nutshell.", replace=True),
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["value"] == NUTSHELL
    assert route.called


def test_extract_empty_body_returns_400(authed_client):
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(UPSTREAM_CHAT_URL).respond(
            200, json={"choices": [{"message": {"content": "nope"}}]}
        )
        resp = authed_client.post(
            "/api/ai/extract",
            headers=_headers(),
            json=_payload(body="   "),
        )
    assert resp.status_code == 400
    assert "Body text is required" in resp.json()["detail"]
    assert not route.called


def test_extract_unknown_field_returns_400(authed_client):
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(UPSTREAM_CHAT_URL).respond(
            200, json={"choices": [{"message": {"content": "nope"}}]}
        )
        resp = authed_client.post(
            "/api/ai/extract",
            headers=_headers(),
            json=_payload(field="deck"),
        )
    assert resp.status_code == 400
    assert "Unsupported extract field" in resp.json()["detail"]
    assert not route.called


def test_extract_prompt_is_extractive(authed_client):
    """Contract coverage: the upstream payload must constrain no-new-facts."""
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(UPSTREAM_CHAT_URL).respond(
            200, json={"choices": [{"message": {"content": NUTSHELL}}]}
        )
        resp = authed_client.post(
            "/api/ai/extract",
            headers=_headers(),
            json=_payload(),
        )
    assert resp.status_code == 200
    sent = route.calls.last.request
    payload = json.loads(sent.content)
    messages = payload["messages"]
    system = messages[0]["content"]
    user = messages[1]["content"]
    assert messages[0]["role"] == "system"
    assert system == SUMMARY_EXTRACT_SYSTEM_PROMPT
    assert "no new facts" in system.lower()
    assert "extractive" in system.lower()
    assert "already appear in the body" in system.lower()
    assert BODY in user
    assert payload["temperature"] == 0.2
    assert payload["stream"] is False
    assert "max_tokens" not in payload
    assert "text_generation_prompt" not in system.lower()


def test_extract_strips_fences_and_summary_prefix(authed_client):
    with respx.mock(assert_all_called=True) as mock:
        mock.post(UPSTREAM_CHAT_URL).respond(
            200,
            json={
                "choices": [
                    {"message": {"content": '```\nSummary: Helsinki is Finland\'s capital.\n```'}}
                ]
            },
        )
        resp = authed_client.post(
            "/api/ai/extract",
            headers=_headers(),
            json=_payload(),
        )
    assert resp.status_code == 200
    assert resp.json()["value"] == "Helsinki is Finland's capital."


def test_extract_reads_content_parts(authed_client):
    """Multimodal-style content arrays must yield the text part, not a Python repr."""
    with respx.mock(assert_all_called=True) as mock:
        mock.post(UPSTREAM_CHAT_URL).respond(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "thinking", "text": "scratchpad"},
                                {"type": "text", "text": NUTSHELL},
                            ]
                        }
                    }
                ]
            },
        )
        resp = authed_client.post(
            "/api/ai/extract",
            headers=_headers(),
            json=_payload(),
        )
    assert resp.status_code == 200
    assert resp.json()["value"] == NUTSHELL


def test_extract_empty_content_with_reasoning_returns_502(authed_client):
    """Reasoning-only payloads (content null, tokens spent on thinking) must not
    look like a successful empty nutshell."""
    with respx.mock(assert_all_called=True) as mock:
        mock.post(UPSTREAM_CHAT_URL).respond(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "reasoning_content": "long internal chain of thought " * 20,
                        }
                    }
                ],
                "usage": {"prompt_tokens": 705, "completion_tokens": 400},
            },
        )
        resp = authed_client.post(
            "/api/ai/extract",
            headers=_headers(),
            json=_payload(),
        )
    assert resp.status_code == 502
    assert "no summary text" in resp.json()["detail"]


def test_extract_missing_model_returns_400(authed_client):
    resp = authed_client.post(
        "/api/ai/extract",
        headers={
            "X-Pen-AI-Base-URL": "https://api.openai.com/v1",
            "X-Pen-AI-Key": "sk-fake",
        },
        json=_payload(),
    )
    assert resp.status_code == 400
    assert "Model must be specified" in resp.json()["detail"]


def test_extract_ai_disabled_returns_400(authed_client):
    import config

    ini_path = config.BASE_DIR / "config.ini"
    with open(ini_path, "w") as f:
        f.write("[General]\nuse_ai = false\n")
    try:
        resp = authed_client.post(
            "/api/ai/extract",
            headers=_headers(),
            json=_payload(),
        )
        assert resp.status_code == 400
        assert "AI features are disabled" in resp.json()["detail"]
    finally:
        if ini_path.exists():
            ini_path.unlink()


def _faqs_payload(**extra):
    payload = {
        "field": "faqs",
        "body": EXPLAINER,
        "current_value": [],
        "replace": False,
    }
    payload.update(extra)
    return payload


def test_extract_faqs_empty_current_returns_list(authed_client):
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(UPSTREAM_CHAT_URL).respond(
            200,
            json={"choices": [{"message": {"content": json.dumps(FAQ_PAIRS)}}]},
        )
        resp = authed_client.post(
            "/api/ai/extract",
            headers=_headers(),
            json=_faqs_payload(current_value=[]),
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["field"] == "faqs"
    assert data["value"] == FAQ_PAIRS
    assert 3 <= len(data["value"]) <= 8
    assert route.called


def test_extract_faqs_nonempty_refuses_without_replace(authed_client):
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(UPSTREAM_CHAT_URL).respond(
            200, json={"choices": [{"message": {"content": "should not run"}}]}
        )
        resp = authed_client.post(
            "/api/ai/extract",
            headers=_headers(),
            json=_faqs_payload(current_value=EXISTING_FAQS, replace=False),
        )
    assert resp.status_code == 409, resp.text
    detail = resp.json()["detail"]
    assert detail["code"] == "non_empty"
    assert detail["field"] == "faqs"
    assert "replace=true" in detail["message"]
    assert not route.called


def test_extract_faqs_replace_applies(authed_client):
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(UPSTREAM_CHAT_URL).respond(
            200,
            json={"choices": [{"message": {"content": json.dumps(FAQ_PAIRS)}}]},
        )
        resp = authed_client.post(
            "/api/ai/extract",
            headers=_headers(),
            json=_faqs_payload(current_value=EXISTING_FAQS, replace=True),
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["field"] == "faqs"
    assert data["value"] == FAQ_PAIRS
    assert route.called


def test_extract_faqs_prompt_is_extractive(authed_client):
    """Skip-if-not-Q&A contract: already answers, empty list, no persona."""
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(UPSTREAM_CHAT_URL).respond(
            200,
            json={"choices": [{"message": {"content": json.dumps(FAQ_PAIRS)}}]},
        )
        resp = authed_client.post(
            "/api/ai/extract",
            headers=_headers(),
            json=_faqs_payload(),
        )
    assert resp.status_code == 200
    sent = route.calls.last.request
    payload = json.loads(sent.content)
    messages = payload["messages"]
    system = messages[0]["content"]
    user = messages[1]["content"]
    assert messages[0]["role"] == "system"
    assert system == FAQS_EXTRACT_SYSTEM_PROMPT
    assert "already answers" in system.lower()
    assert "skip if not q&a-shaped" in system.lower()
    assert "[]" in system
    assert "no new facts" in system.lower()
    assert EXPLAINER in user
    assert payload["temperature"] == 0.2
    assert payload["stream"] is False
    assert "max_tokens" not in payload
    assert "text_generation_prompt" not in system.lower()


def test_extract_faqs_poem_returns_empty_list(authed_client):
    with respx.mock(assert_all_called=True) as mock:
        mock.post(UPSTREAM_CHAT_URL).respond(
            200, json={"choices": [{"message": {"content": "[]"}}]}
        )
        resp = authed_client.post(
            "/api/ai/extract",
            headers=_headers(),
            json=_faqs_payload(body=POEM, current_value=[]),
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["field"] == "faqs"
    assert data["value"] == []


def test_extract_faqs_invalid_json_coerced_to_empty(authed_client):
    with respx.mock(assert_all_called=True) as mock:
        mock.post(UPSTREAM_CHAT_URL).respond(
            200, json={"choices": [{"message": {"content": "not a JSON array"}}]}
        )
        resp = authed_client.post(
            "/api/ai/extract",
            headers=_headers(),
            json=_faqs_payload(body=POEM, current_value=[]),
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["value"] == []
