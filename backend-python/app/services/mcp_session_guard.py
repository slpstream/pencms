"""Streamable HTTP helpers for curl-style MCP clients.

- Missing / ``*/*`` Accept → JSON+SSE (SDK otherwise returns 406).
- Authenticated JSON-RPC other than ``initialize`` without ``mcp-session-id``
  → 400 (otherwise a new uninitialized session).
- ``initialize`` JSON result also carries ``sessionId`` (header still set).
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

MCP_SESSION_HEADER = "mcp-session-id"
DEFAULT_ACCEPT = "application/json, text/event-stream"
SESSION_REQUIRED_DETAIL = (
    "Echo the Mcp-Session-Id header from initialize on every later POST "
    "to /api/mcp (tools/list, tools/call, notifications). "
    "REST /api/v1/mcp/* does not use a session. "
    "initialize JSON also includes result.sessionId."
)


def _is_mcp_gateway(path: str) -> bool:
    return path == "/api/mcp" or path.startswith("/api/mcp/")


def _has_credentials(headers: list[tuple[bytes, bytes]]) -> bool:
    for name, value in headers:
        key = name.decode("latin-1").lower()
        if key in ("authorization", "cookie") and value.strip():
            return True
    return False


def jsonrpc_methods(payload: Any) -> list[str]:
    if isinstance(payload, dict):
        method = payload.get("method")
        return [method] if isinstance(method, str) else []
    if isinstance(payload, list):
        methods: list[str] = []
        for item in payload:
            if isinstance(item, dict) and isinstance(item.get("method"), str):
                methods.append(item["method"])
        return methods
    return []


def allows_without_session(methods: Iterable[str]) -> bool:
    names = list(methods)
    if not names:
        return True
    return any(name == "initialize" for name in names)


def compat_accept_value(accept: str) -> Optional[str]:
    """Return a rewritten Accept value, or None to keep the original."""
    raw = (accept or "").strip()
    if not raw or raw == "*/*":
        return DEFAULT_ACCEPT
    types = [part.strip().split(";")[0].lower() for part in raw.split(",") if part.strip()]
    if not types:
        return DEFAULT_ACCEPT
    if "*/*" in types:
        return DEFAULT_ACCEPT
    has_json = any(t == "application/json" or t.startswith("application/json+") for t in types)
    has_sse = any(t == "text/event-stream" for t in types)
    if has_json and has_sse:
        return None
    if has_json and not has_sse:
        return f"{raw}, text/event-stream"
    if has_sse and not has_json:
        return f"{raw}, application/json"
    return None


def _replace_header(
    headers: list[tuple[bytes, bytes]], name: str, value: str
) -> list[tuple[bytes, bytes]]:
    lower = name.lower()
    kept = [(n, v) for n, v in headers if n.decode("latin-1").lower() != lower]
    kept.append((name.encode("latin-1"), value.encode("latin-1")))
    return kept


def _header_value(headers: list[tuple[bytes, bytes]], name: str) -> str:
    lower = name.lower()
    for n, v in headers:
        if n.decode("latin-1").lower() == lower:
            return v.decode("latin-1")
    return ""


def inject_session_id_json(body: bytes, session_id: str) -> bytes:
    if not session_id or not body:
        return body
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return body
    if not isinstance(payload, dict):
        return body
    result = payload.get("result")
    if not isinstance(result, dict):
        return body
    result.setdefault("sessionId", session_id)
    payload["result"] = result
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


class McpSessionGuardMiddleware:
    """ASGI wrapper: Accept compat, session 400, initialize sessionId in JSON."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path") or ""
        if not _is_mcp_gateway(path):
            await self.app(scope, receive, send)
            return

        headers = list(scope.get("headers") or [])
        header_map = {
            name.decode("latin-1").lower(): value.decode("latin-1")
            for name, value in headers
        }
        new_accept = compat_accept_value(header_map.get("accept") or "")
        if new_accept:
            headers = _replace_header(headers, "accept", new_accept)
            scope = {**scope, "headers": headers}
            header_map["accept"] = new_accept

        if scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        body = await request.body()

        async def replay_receive():
            return {"type": "http.request", "body": body, "more_body": False}

        try:
            payload = json.loads(body.decode("utf-8") or "null")
        except (UnicodeDecodeError, json.JSONDecodeError):
            await self.app(scope, replay_receive, send)
            return

        methods = jsonrpc_methods(payload)
        if (
            not header_map.get(MCP_SESSION_HEADER)
            and _has_credentials(headers)
            and not allows_without_session(methods)
        ):
            response = JSONResponse(
                status_code=400,
                content={
                    "detail": SESSION_REQUIRED_DETAIL,
                    "error": "mcp_session_required",
                },
            )
            await response(scope, replay_receive, send)
            return

        is_init = "initialize" in methods
        if not is_init:
            await self.app(scope, replay_receive, send)
            return

        start: dict | None = None
        chunks: list[bytes] = []

        async def send_wrapper(message):
            nonlocal start
            if message["type"] == "http.response.start":
                start = message
                return
            if message["type"] != "http.response.body":
                await send(message)
                return
            chunks.append(message.get("body") or b"")
            if message.get("more_body"):
                return
            raw = b"".join(chunks)
            resp_headers = list((start or {}).get("headers") or [])
            session = _header_value(resp_headers, MCP_SESSION_HEADER)
            ctype = _header_value(resp_headers, "content-type").lower()
            if session and "application/json" in ctype:
                raw = inject_session_id_json(raw, session)
                resp_headers = _replace_header(
                    resp_headers, "content-length", str(len(raw))
                )
            await send(
                {
                    "type": "http.response.start",
                    "status": (start or {}).get("status", 200),
                    "headers": resp_headers,
                }
            )
            await send({"type": "http.response.body", "body": raw, "more_body": False})

        await self.app(scope, replay_receive, send_wrapper)
