import ipaddress
import json
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import config
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from models.user import UserPublic
from pydantic import BaseModel, ConfigDict
from routers.auth import get_current_user
from services.ai_settings_service import (
    load_ai_settings,
    save_ai_settings,
)
from services.extract_prompts import (
    FAQS_EXTRACT_SYSTEM_PROMPT,
    SUMMARY_EXTRACT_SYSTEM_PROMPT,
)
from services.localization_policy_service import POLICY_KEY
from services.site_service import resolve_human_site_id

router = APIRouter(prefix="/ai", tags=["ai"])


# ---------------------------------------------------------------------------
# Phase 5: Dynamic Schema Discovery
# ---------------------------------------------------------------------------
#
# `GET /api/ai/schemas` returns the parsed `collections.yaml` +
# `taxonomy.yaml` payload so the sidebar can serialize it into the system
# prompt at request time. This ensures that when the user adds a new
# collection or taxonomy term, the AI assistant discovers it on the next
# request without any code change.
#
# The route lives in the AI router (not the taxonomy router) per the plan:
# MCP and the sidebar consume the same shape, and we want to keep AI
# schema concerns in one place so a future "advertised-vs-hidden" filter
# has a single home.
#
# Auth: same `get_current_user` dependency as the chat route. The schemas
# themselves are not secret (they're YAML files in the repo), but we still
# gate the endpoint so an unauthenticated crawler can't enumerate the
# site's content shape.
@router.get("/schemas")
async def get_ai_schemas(
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(resolve_human_site_id),
) -> Dict[str, Any]:
    """Return collection schemas + taxonomy for AI prompt assembly.

    Response shape::

        {
          "collections": { "posts": { ...from collections.yaml... } },
          "taxonomy":     { "vocabularies": {...}, "primary_vocabulary": ... },
          "required_fields": [...]   # conditionally-required by taxonomy.yaml
        }
    """
    if not is_ai_enabled():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI features are disabled. Please enable them in Site Settings.",
        )
    snap = config.load_taxonomy_for_site(site_id)
    return {
        "collections": config.load_collections_for_site(site_id),
        "taxonomy": {
            "vocabularies": snap["vocabularies"],
            "primary_vocabulary": snap["primary_vocabulary"],
        },
        "required_fields": snap["required_fields"],
        "site_id": site_id,
    }


@router.get("/settings")
async def get_ai_settings(
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(resolve_human_site_id),
):
    """Read AI prompts and guardrails for the active Content site."""
    try:
        return load_ai_settings(site_id)
    except Exception as e:
        raise HTTPException(500, f"Failed to read AI settings: {e}")


@router.put("/settings")
async def update_ai_settings(
    settings: Dict[str, Any],
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(resolve_human_site_id),
):
    """Write AI prompts and guardrails for the active Content site."""
    try:
        if POLICY_KEY in settings:
            raise ValueError(
                "Update localization policy through /api/v1/translations/config."
            )
        return save_ai_settings(
            site_id,
            settings,
            validate_localization_bindings=False,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to write AI settings: {e}")


class ChatMessage(BaseModel):
    role: str
    content: Optional[Any] = None  # str or List[dict] for multimodal (vision)
    name: Optional[str] = None
    tool_calls: Optional[List[dict]] = None
    tool_call_id: Optional[str] = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    messages: List[ChatMessage]
    model: Optional[str] = None
    stream: Optional[bool] = False
    max_tokens: Optional[int] = None
    tools: Optional[List[dict]] = None
    tool_choice: Optional[str] = "auto"
    # Stable surface ids: editor | navigation | customize (scaffolding for concierge)
    surface: Optional[str] = None


class ImageRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    prompt: str
    model: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    size: Optional[str] = None
    resolution: Optional[str] = None
    n: Optional[int] = None
    response_format: Optional[str] = "b64_json"


def is_ai_enabled() -> bool:
    """Check config.ini to see if AI features are enabled."""
    import configparser
    import sys
    try:
        cp = configparser.ConfigParser()
        cp.read(config.BASE_DIR / "config.ini")
        # In a pytest test run, config.ini might not be fully initialized or present in the temp_data_root.
        # So we default to True for tests, and False for production.
        fallback = "pytest" in sys.modules
        return cp.getboolean("General", "use_ai", fallback=fallback)
    except Exception:
        return "pytest" in sys.modules


def is_valid_url(url: str) -> bool:
    """SSRF guard validating endpoint schemes and IP ranges."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Allow localhost
        if hostname.lower() == "localhost":
            return True

        try:
            ip = ipaddress.ip_address(hostname)
            # Allow loopback (127.0.0.1, ::1)
            if ip.is_loopback:
                return True
            # Reject link-local (169.254.0.0/16), multicast, reserved, and
            # unspecified (0.0.0.0) IP addresses. `0.0.0.0` routes to
            # localhost on most stacks and is a common SSRF bypass.
            # Note: RFC 1918 Private LAN ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
            # are allowed to enable connecting to local endpoints in home labs / internal subnets.
            if (
                ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                return False
        except ValueError:
            # Hostname/domain name is treated as allowed for resolving
            pass
        return True
    except Exception:
        return False


def _is_loopback_host(hostname: str) -> bool:
    if not hostname:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def resolve_chat_upstream(
    *,
    x_pen_ai_key: Optional[str],
    x_pen_ai_base_url: Optional[str],
    x_pen_ai_model: Optional[str],
    body_model: Optional[str] = None,
    default_base_url: str = "https://api.openai.com/v1",
) -> Tuple[str, str, Dict[str, str]]:
    """Gate AI chat-completions calls (enabled, SSRF, Anthropic, key, model).

    Returns ``(endpoint, model, headers)``. Shared by ``/ai/chat`` and
    ``/ai/extract`` so Session 6 can reuse the same upstream contract.
    """
    if not is_ai_enabled():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI features are disabled. Please enable them in Site Settings.",
        )
    base_url = x_pen_ai_base_url or default_base_url
    if not is_valid_url(base_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or restricted Base URL.",
        )
    if "api.anthropic.com" in base_url:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Anthropic adapter not yet implemented",
        )
    is_local = _is_loopback_host(urlparse(base_url).hostname or "")
    if not is_local and not x_pen_ai_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI Provider API Key is required for non-local endpoints.",
        )
    model = body_model or x_pen_ai_model
    if not model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model must be specified in request body or headers.",
        )
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if x_pen_ai_key and not is_local:
        headers["Authorization"] = f"Bearer {x_pen_ai_key}"
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    return endpoint, model, headers


def _upstream_error_detail(resp: httpx.Response) -> Any:
    detail = resp.text
    if detail.strip().startswith("<"):
        return (
            f"Upstream provider returned HTML (status code {resp.status_code}). "
            "Please verify your Endpoint URL (Base URL)."
        )
    try:
        err_json = json.loads(detail)
        if "error" in err_json:
            return err_json["error"]
        if "detail" in err_json:
            return err_json["detail"]
    except Exception:
        pass
    return detail


# Session 5 / PR-C — extractive field fill. Session 6 / PR-D adds ``faqs``.
EXTRACTABLE_FIELDS = frozenset({"summary", "faqs"})
EXTRACT_BODY_MAX_CHARS = 32000
FAQS_EXTRACT_MAX_PAIRS = 8


class ExtractRequest(BaseModel):
    """Preview-only extractive fill. The caller writes the field after Apply."""

    field: str
    body: str = ""
    current_value: Optional[Any] = None
    replace: bool = False


def _current_value_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return not bool(value)


def _truncate_extract_body(body: str) -> str:
    if len(body) <= EXTRACT_BODY_MAX_CHARS:
        return body
    return body[:EXTRACT_BODY_MAX_CHARS] + "\n\n[...truncated...]"


def _content_to_text(content: Any) -> str:
    """Flatten OpenAI-style ``content`` (string or list of parts) to text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") in {"thinking", "thought", "reasoning"}:
                    continue
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


def _visible_message_text(data: Any) -> str:
    """Read the assistant's visible text; ignore reasoning-only channels."""
    try:
        choice = data["choices"][0]
    except (KeyError, IndexError, TypeError):
        return ""
    if not isinstance(choice, dict):
        return ""
    message = choice.get("message")
    if isinstance(message, dict):
        text = _content_to_text(message.get("content"))
        if text.strip():
            return text
        text = _content_to_text(message.get("output_text"))
        if text.strip():
            return text
    text = _content_to_text(choice.get("text"))
    if text.strip():
        return text
    return ""


def _clean_extract_text(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1].strip()
    lowered = text.lower()
    for prefix in ("summary:", "nutshell:"):
        if lowered.startswith(prefix):
            text = text[len(prefix) :].strip()
            break
    return text


def _parse_faqs_extract(raw: str) -> List[Dict[str, str]]:
    """Lenient parse of extractive FAQ JSON. Invalid / non-Q&A → ``[]``, never 500."""
    text = _clean_extract_text(raw)
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    out: List[Dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        q = str(item["q"] if item.get("q") is not None else "").strip()
        a = str(item["a"] if item.get("a") is not None else "").strip()
        if not q or not a:
            continue
        out.append({"q": q, "a": a})
        if len(out) >= FAQS_EXTRACT_MAX_PAIRS:
            break
    return out


@router.post("/chat")
async def ai_chat_proxy(
    body: ChatRequest,
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(resolve_human_site_id),
    x_pen_ai_key: Optional[str] = Header(None, alias="X-Pen-AI-Key"),
    x_pen_ai_base_url: Optional[str] = Header(None, alias="X-Pen-AI-Base-URL"),
    x_pen_ai_model: Optional[str] = Header(None, alias="X-Pen-AI-Model"),
):
    endpoint, model, headers = resolve_chat_upstream(
        x_pen_ai_key=x_pen_ai_key,
        x_pen_ai_base_url=x_pen_ai_base_url,
        x_pen_ai_model=x_pen_ai_model,
        body_model=body.model,
    )

    # surface is PenCMS-only; never forward it to the upstream provider
    payload = body.model_dump(exclude_none=True, exclude={"surface"})

    # Text Generation persona applies only to the Prose/editor surface
    text_prompt = load_ai_settings(site_id).get("text_generation_prompt", "") or ""

    if body.surface == "editor" and text_prompt and text_prompt.strip():
        # Wrap the text prompt with clean instructions to distinguish post generation style vs chat assistant persona
        wrapped_prompt = (
            "## CRITICAL SYSTEM INSTRUCTION: PERSONA SEGREGATION\n"
            "You must strictly separate your conversational persona from the style of the content you generate:\n"
            "1. **Your Chat Persona**: In all your conversational responses/chat bubbles to the user, you MUST speak as a normal, friendly, professional, and helpful SEO/writing assistant. Under no circumstances should you speak in the style of the custom prompt (e.g., do NOT speak like a pirate, do NOT use pirate speak, slang, or custom characters in your chat messages).\n"
            "2. **Post/Post Content**: The custom style prompt below applies ONLY to the actual post/post draft, body, headlines, and content you write or edit using tools (e.g., inside the `body` parameter of `write_content_file`, `replace_selection`, or `insert_at_cursor`):\n"
            f"   > \"{text_prompt.strip()}\"\n"
            "Note: If the custom style prompt contains absolute instructions like 'every sentence', 'always', 'all text', or similar, these rules apply SOLELY to the post content you produce and write to files, NOT to your conversational replies to the user."
        )
        # Inject text_prompt. We can prepend a system message, or append to the existing system message if present.
        messages = list(body.messages)
        if messages and messages[0].role == "system":
            # Append/prepend text_prompt to the system message
            if isinstance(messages[0].content, str):
                messages[0].content = f"{messages[0].content}\n\n{wrapped_prompt}"
            else:
                messages.insert(1, ChatMessage(role="system", content=wrapped_prompt))
        else:
            messages.insert(0, ChatMessage(role="system", content=wrapped_prompt))

        # update payload's messages:
        payload["messages"] = [m.model_dump(exclude_none=True) for m in messages]

    payload["model"] = model

    # Forward request
    if body.stream:
        client = httpx.AsyncClient(timeout=120.0)
        try:
            req = client.build_request("POST", endpoint, json=payload, headers=headers)
            resp = await client.send(req, stream=True)

            if resp.status_code != 200:
                await resp.aread()
                detail = _upstream_error_detail(resp)
                await resp.aclose()
                await client.aclose()
                raise HTTPException(status_code=resp.status_code, detail=detail)

            async def stream_generator():
                try:
                    async for line in resp.aiter_lines():
                        yield f"{line}\n"
                finally:
                    await resp.aclose()
                    await client.aclose()

            return StreamingResponse(stream_generator(), media_type="text/event-stream")

        except httpx.RequestError as exc:
            await client.aclose()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to connect to the upstream AI provider: {str(exc)}",
            )
        except Exception:
            await client.aclose()
            raise
    else:
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                resp = await client.post(endpoint, json=payload, headers=headers)
                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail=_upstream_error_detail(resp),
                    )
                return resp.json()
            except httpx.RequestError as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to connect to the upstream AI provider: {str(exc)}",
                )


@router.post("/images")
async def ai_images_proxy(
    body: ImageRequest,
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(resolve_human_site_id),
    x_pen_ai_key: Optional[str] = Header(None, alias="X-Pen-AI-Key"),
    x_pen_ai_base_url: Optional[str] = Header(None, alias="X-Pen-AI-Base-URL"),
    x_pen_ai_model: Optional[str] = Header(None, alias="X-Pen-AI-Model"),
):
    if not is_ai_enabled():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI features are disabled. Please enable them in Site Settings.",
        )
    base_url = x_pen_ai_base_url or "https://nano-gpt.com/api/v1/images"

    # 1. SSRF URL Check
    if not is_valid_url(base_url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or restricted Base URL.",
        )

    # 2. Determine loopback / localhost (for Ollama/LM Studio local auth exception)
    parsed = urlparse(base_url)
    hostname = parsed.hostname or ""
    is_local = False
    if hostname.lower() == "localhost":
        is_local = True
    else:
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_loopback:
                is_local = True
        except ValueError:
            pass

    # 3. Enforce API Key for non-local endpoints
    if not is_local and not x_pen_ai_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI Provider API Key is required for non-local endpoints.",
        )

    # 4. Resolve the target endpoint URL
    if base_url.endswith("/images") or base_url.endswith("/images/generations"):
        endpoint = base_url
    else:
        endpoint = f"{base_url.rstrip('/')}/images/generations"

    # 5. Build and normalize payload
    payload = body.model_dump(exclude_none=True)
    
    # Load per-site AI settings for add-on image prompt
    image_prompt = load_ai_settings(site_id).get("image_generation_prompt", "") or ""

    if image_prompt and image_prompt.strip():
        original_prompt = payload.get("prompt", "")
        if original_prompt:
            payload["prompt"] = f"{original_prompt}, {image_prompt.strip()}"
        else:
            payload["prompt"] = image_prompt.strip()

    model = body.model or x_pen_ai_model
    if not model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model must be specified in request body or headers.",
        )
    payload["model"] = model

    # If the endpoint is Plan B (/images/generations)
    if endpoint.endswith("/images/generations"):
        if "size" not in payload:
            if "resolution" in payload:
                payload["size"] = payload["resolution"]
            elif "width" in payload and "height" in payload:
                payload["size"] = f"{payload['width']}x{payload['height']}"
        payload.pop("width", None)
        payload.pop("height", None)
        payload.pop("resolution", None)
    # If the endpoint is Plan A (/images)
    else:
        if "resolution" not in payload:
            if "size" in payload:
                payload["resolution"] = payload["size"]
            elif "width" in payload and "height" in payload:
                payload["resolution"] = f"{payload['width']}x{payload['height']}"
        payload.pop("width", None)
        payload.pop("height", None)
        payload.pop("size", None)

    # 6. Configure headers
    headers = {"Content-Type": "application/json"}
    if x_pen_ai_key and not is_local:
        if "nano-gpt.com" in base_url and "/api/v1/" in base_url:
            headers["x-api-key"] = x_pen_ai_key
        else:
            headers["Authorization"] = f"Bearer {x_pen_ai_key}"

    # 7. Forward request
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(endpoint, json=payload, headers=headers)
            if resp.status_code != 200:
                detail = resp.text
                if detail.strip().startswith("<"):
                    detail = f"Upstream provider returned HTML (status code {resp.status_code}). Please verify your Endpoint URL (Base URL)."
                else:
                    try:
                        err_json = json.loads(detail)
                        if "error" in err_json:
                            detail = err_json["error"]
                        elif "detail" in err_json:
                            detail = err_json["detail"]
                    except Exception:
                        pass
                raise HTTPException(status_code=resp.status_code, detail=str(detail))
            return resp.json()
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to connect to the upstream AI provider: {str(exc)}",
            )


@router.post("/extract")
async def ai_extract_proxy(
    body: ExtractRequest,
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(resolve_human_site_id),
    x_pen_ai_key: Optional[str] = Header(None, alias="X-Pen-AI-Key"),
    x_pen_ai_base_url: Optional[str] = Header(None, alias="X-Pen-AI-Base-URL"),
    x_pen_ai_model: Optional[str] = Header(None, alias="X-Pen-AI-Model"),
) -> Dict[str, Any]:
    """Constrained extractive fill. Returns a preview; does not write frontmatter.

    Session 5 / PR-C: ``field=summary``. Session 6 / PR-D: also ``field=faqs``.
    Never injects ``text_generation_prompt`` (extractive, not stylized).
    ``site_id`` is resolved for the same cookie/header path as ``/ai/chat``.
    """
    field = (body.field or "").strip()
    if field not in EXTRACTABLE_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported extract field '{field}'.",
        )
    source = (body.body or "").strip()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Body text is required to extract.",
        )
    if not _current_value_empty(body.current_value) and not body.replace:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "non_empty",
                "field": field,
                "message": f"{field} is already set. Pass replace=true to overwrite.",
            },
        )

    endpoint, model, headers = resolve_chat_upstream(
        x_pen_ai_key=x_pen_ai_key,
        x_pen_ai_base_url=x_pen_ai_base_url,
        x_pen_ai_model=x_pen_ai_model,
    )
    truncated = _truncate_extract_body(source)
    if field == "faqs":
        system_prompt = FAQS_EXTRACT_SYSTEM_PROMPT
        user_content = (
            "Extract 3–8 questions this body already answers as a JSON array of "
            '{"q","a"} objects. If the piece is not Q&A-shaped, return [].\n\n---\n'
            f"{truncated}\n---"
        )
    else:
        system_prompt = SUMMARY_EXTRACT_SYSTEM_PROMPT
        user_content = (
            "Extract a nutshell summary of this body. "
            "Return only the nutshell text.\n\n---\n"
            f"{truncated}\n---"
        )
    # Do not set a tight max_tokens. Reasoning models spend that budget on
    # thinking and then return empty ``message.content`` (the wand saw this
    # as "empty nutshell" while the provider still billed output tokens).
    # /ai/chat also omits max_tokens. Prompt already asks for 1–3 sentences.
    payload = {
        "model": model,
        "stream": False,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(endpoint, json=payload, headers=headers)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=_upstream_error_detail(resp),
                )
            data = resp.json()
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to connect to the upstream AI provider: {str(exc)}",
            )
    raw = _visible_message_text(data)
    if field == "faqs":
        value: Any = _parse_faqs_extract(raw)
    else:
        value = _clean_extract_text(raw)
        if not value:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "The model returned no summary text. Reasoning models can spend "
                    "the whole output budget on thinking and leave content empty — try again."
                ),
            )
    return {
        "ok": True,
        "field": field,
        "value": value,
    }

