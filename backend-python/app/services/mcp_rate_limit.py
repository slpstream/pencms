"""In-process MCP loop-guard (not a substitute for Caddy).

Sliding-window counter keyed by agent_key_id (fallback: JWT sub). Applies
only to Bearer agent JWTs on ``/api/mcp`` and ``/api/v1/mcp/*``. Human
admin cookie sessions are not counted.

Default on. Disable with ``PENCMS_RATE_LIMIT_MCP=0``. Ceiling:
``PENCMS_RATE_LIMIT_MCP_PER_MIN`` (default 120).
"""

from __future__ import annotations

import math
import os
import threading
import time
from collections import deque
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

RATE_LIMIT_ENV = "PENCMS_RATE_LIMIT_MCP"
RATE_LIMIT_PER_MIN_ENV = "PENCMS_RATE_LIMIT_MCP_PER_MIN"
DEFAULT_PER_MIN = 120
WINDOW_SECONDS = 60.0


def rate_limit_enabled() -> bool:
    raw = os.environ.get(RATE_LIMIT_ENV)
    if raw is None or not str(raw).strip():
        return True
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def max_requests_per_min() -> int:
    raw = os.environ.get(RATE_LIMIT_PER_MIN_ENV, "").strip()
    if not raw:
        return DEFAULT_PER_MIN
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_PER_MIN
    return max(1, value)


def is_mcp_agent_path(path: str) -> bool:
    if path == "/api/mcp" or path.startswith("/api/mcp/"):
        return True
    if path == "/api/v1/mcp" or path.startswith("/api/v1/mcp/"):
        return True
    return False


class SlidingWindowLimiter:
    """Per-key monotonic sliding window. Process-local; resets on restart."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def hit(
        self, key: str, *, limit: int, window: float = WINDOW_SECONDS, now: Optional[float] = None
    ) -> tuple[bool, int, int]:
        """Return (allowed, remaining, retry_after_seconds)."""
        now = time.monotonic() if now is None else now
        cutoff = now - window
        with self._lock:
            queue = self._hits.get(key)
            if queue is None:
                queue = deque()
                self._hits[key] = queue
            while queue and queue[0] <= cutoff:
                queue.popleft()
            if len(queue) >= limit:
                retry = int(max(1, math.ceil(queue[0] + window - now)))
                return False, 0, retry
            queue.append(now)
            remaining = limit - len(queue)
            return True, remaining, 0


limiter = SlidingWindowLimiter()


def _bearer_token(request: Request) -> Optional[str]:
    authorization = request.headers.get("Authorization") or ""
    if authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        return token or None
    return None


def agent_rate_limit_key(request: Request) -> Optional[str]:
    """Stable bucket for an agent Bearer JWT, or None to skip limiting."""
    token = _bearer_token(request)
    if not token:
        return None
    try:
        from services.auth_service import decode_access_token

        payload = decode_access_token(token)
    except Exception:
        return None
    if payload.get("type") != "agent":
        return None
    key_id = payload.get("agent_key_id")
    if key_id:
        return f"agent:{key_id}"
    sub = payload.get("sub")
    if sub:
        return f"sub:{sub}"
    return "agent:unknown"


def _rate_limit_headers(limit: int, remaining: int, retry_after: int) -> dict[str, str]:
    reset = int(time.time()) + max(retry_after, 0)
    return {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(max(0, remaining)),
        "X-RateLimit-Reset": str(reset),
    }


class McpRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS" or not rate_limit_enabled():
            return await call_next(request)
        if not is_mcp_agent_path(request.url.path):
            return await call_next(request)
        key = agent_rate_limit_key(request)
        if key is None:
            return await call_next(request)

        limit = max_requests_per_min()
        allowed, remaining, retry_after = limiter.hit(key, limit=limit)
        headers = _rate_limit_headers(limit, remaining, retry_after)
        if not allowed:
            headers["Retry-After"] = str(retry_after)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": {
                        "error": "rate_limited",
                        "message": "Too many MCP requests for this agent key.",
                        "retry_after": retry_after,
                    }
                },
                headers=headers,
            )
        response = await call_next(request)
        for name, value in headers.items():
            response.headers[name] = value
        return response
