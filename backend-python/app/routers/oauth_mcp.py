"""MCP OAuth resource-server discovery + colocated authorization server.

Phase 1a: Protected Resource Metadata (RFC 9728) + FastApiMCP bearer gate.
Phase 1b: AS metadata (RFC 8414), PKCE authorize/consent, token + refresh.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import secrets
import uuid
from typing import List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
import jwt
from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from models.user import UserPublic
from routers.auth import get_optional_user
from services.auth_service import (
    AGENT_TOKEN_EXPIRE_MINUTES,
    JWT_ISSUER,
    MCP_RESOURCE_URL,
    bearer_www_authenticate,
    create_agent_access_token,
    decode_agent_token,
    verify_password,
)
from services.authz import ALLOWED_AGENT_SCOPES, ordered_allowed_scopes
from services.oauth_store import (
    consume_auth_code,
    consume_refresh_token,
    store_auth_code,
    store_refresh_token,
)
from services.url_safety import UrlSafetyError, canonicalize_public_https_url
from services.user_service import get_user_by_uuid, get_user_by_username

router = APIRouter(tags=["oauth-mcp"])

ALLOWED_SCOPES = ALLOWED_AGENT_SCOPES

# Static first-party / dev client_id allowlist (no DCR).
# Keys are client_id values; values may list exact redirect_uris and/or
# allow localhost-style redirects (default True for pencms-dev).
_DEFAULT_STATIC_CLIENTS = {
    "pencms-dev": {
        "redirect_uris": [],
        "allow_loopback": True,
    },
}


def _static_clients() -> dict:
    raw = os.environ.get("OAUTH_STATIC_CLIENTS")
    if not raw:
        return dict(_DEFAULT_STATIC_CLIENTS)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return dict(_DEFAULT_STATIC_CLIENTS)


def _prm_document() -> dict:
    return {
        "resource": MCP_RESOURCE_URL,
        "authorization_servers": [JWT_ISSUER],
        "scopes_supported": ordered_allowed_scopes(),
    }


def _as_metadata() -> dict:
    return {
        "issuer": JWT_ISSUER,
        "authorization_endpoint": f"{JWT_ISSUER}/oauth/authorize",
        "token_endpoint": f"{JWT_ISSUER}/oauth/token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "scopes_supported": ordered_allowed_scopes(),
        "token_endpoint_auth_methods_supported": ["none"],
        "resource_indicators_supported": True,
        # RFC 9207: authorization responses include iss=JWT_ISSUER
        "authorization_response_iss_parameter_supported": True,
    }


@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/api/mcp")
async def protected_resource_metadata():
    """RFC 9728 Protected Resource Metadata for the MCP gateway."""
    return _prm_document()


@router.get("/.well-known/oauth-authorization-server")
async def authorization_server_metadata():
    """RFC 8414 Authorization Server Metadata."""
    return _as_metadata()


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": bearer_www_authenticate(scope="read")},
    )


async def require_mcp_bearer(request: Request) -> dict:
    """FastApiMCP AuthConfig dependency: require a valid agent Bearer JWT.

    Missing or invalid tokens return 401 with resource_metadata so MCP
    clients can discover PRM / the authorization server.
    """
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise _unauthorized("Not authenticated")

    token = auth.split(" ", 1)[1].strip()
    if not token:
        raise _unauthorized("Not authenticated")

    try:
        payload = decode_agent_token(token)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token has expired")
    except jwt.PyJWTError:
        raise _unauthorized("Invalid token")

    if payload.get("type") != "agent":
        raise _unauthorized("Invalid token")

    return payload


# ---------------------------------------------------------------------------
# Redirect URI + client_id validation
# ---------------------------------------------------------------------------


def _is_loopback_http(uri: str) -> bool:
    try:
        parsed = urlparse(uri)
    except Exception:
        return False
    if parsed.scheme != "http":
        return False
    if parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        return False
    # Any port allowed; path/query must be present as registered.
    return True


def _is_https_absolute(uri: str) -> bool:
    try:
        parsed = urlparse(uri)
    except Exception:
        return False
    return parsed.scheme == "https" and bool(parsed.netloc)


def redirect_uri_allowed(redirect_uri: str) -> bool:
    """MCP redirect rules: loopback http (any port) or HTTPS absolute."""
    return _is_loopback_http(redirect_uri) or _is_https_absolute(redirect_uri)


async def validate_client_redirect(
    client_id: str,
    redirect_uri: str,
    *,
    fetch_cimd: bool = True,
) -> None:
    """Validate client_id (CIMD or static allowlist) and redirect_uri pairing.

    When ``fetch_cimd`` is False, CIMD URLs are only syntax/SSRF-checked;
    the metadata document is not fetched. Pairing is therefore unconfirmed
    for CIMD until an authenticated fetch runs.

    Raises HTTPException on failure.
    """
    if not redirect_uri_allowed(redirect_uri):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="redirect_uri must be http://localhost|127.0.0.1 (any port) or https",
        )

    # Prefer CIMD: URL as client_id (must be public HTTPS after canonicalization)
    if urlparse(client_id).scheme:
        try:
            canonical_url = canonicalize_public_https_url(
                client_id, require_port_443=True
            )
        except UrlSafetyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or restricted client_id URL",
            )
        if not fetch_cimd:
            return
        try:
            async with httpx.AsyncClient(
                timeout=5.0, follow_redirects=False, trust_env=False
            ) as client:
                # CIMD client_id is an HTTPS URL by spec. canonicalize_public_https_url
                # enforces scheme/port/DNS/IP checks; fetch is session-gated; body is not reflected.
                # codeql[py/full-ssrf]
                resp = await client.get(
                    canonical_url,
                    headers={"Accept": "application/json"},
                )
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to fetch client ID metadata document",
                )
            if len(resp.content) > 65536:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Client metadata document exceeds maximum size limit",
                )
            meta = resp.json()
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch client ID metadata document",
            )
        uris = meta.get("redirect_uris") or []
        if redirect_uri not in uris:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="redirect_uri not registered in client metadata",
            )
        return

    # Static allowlist fallback
    clients = _static_clients()
    entry = clients.get(client_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown client_id",
        )
    exact = entry.get("redirect_uris") or []
    if redirect_uri in exact:
        return
    if entry.get("allow_loopback", False) and _is_loopback_http(redirect_uri):
        return
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="redirect_uri not allowed for this client_id",
    )


def parse_scopes(scope: Optional[str]) -> List[str]:
    if not scope or not scope.strip():
        return ["read"]
    parts = [p for p in scope.strip().split() if p]
    unknown = set(parts) - ALLOWED_SCOPES
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported scope(s): {sorted(unknown)}",
        )
    # Preserve order, dedupe
    seen = set()
    out = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _pkce_s256_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _oauth_error_redirect(
    redirect_uri: str,
    error: str,
    description: str,
    state: Optional[str] = None,
) -> RedirectResponse:
    # RFC 9207: iss closes authorization-server mix-up attacks
    params = {
        "error": error,
        "error_description": description,
        "iss": JWT_ISSUER,
    }
    if state is not None:
        params["state"] = state
    return RedirectResponse(
        url=_append_query(redirect_uri, params),
        status_code=status.HTTP_302_FOUND,
    )


def _append_query(uri: str, params: dict) -> str:
    parsed = urlparse(uri)
    existing = dict(parse_qsl(parsed.query, keep_blank_values=True))
    existing.update({k: v for k, v in params.items() if v is not None})
    return urlunparse(parsed._replace(query=urlencode(existing)))


def _html_page(title: str, body: str) -> HTMLResponse:
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <style>
    :root {{ font-family: ui-sans-serif, system-ui, sans-serif; color: #1a1a1a; }}
    body {{ max-width: 32rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.45; }}
    h1 {{ font-size: 1.25rem; margin-bottom: 0.5rem; }}
    label {{ display: block; margin: 0.75rem 0 0.25rem; font-size: 0.9rem; }}
    input[type=text], input[type=password], select {{ width: 100%; padding: 0.4rem; box-sizing: border-box; }}
    .scopes label {{ display: inline-flex; align-items: center; gap: 0.35rem; margin-right: 1rem; }}
    button {{ margin-top: 1rem; padding: 0.5rem 1rem; cursor: pointer; }}
    .err {{ color: #a40000; margin: 0.75rem 0; }}
    .meta {{ color: #555; font-size: 0.85rem; margin-bottom: 1rem; }}
  </style>
</head>
<body>
{body}
</body>
</html>"""
    return HTMLResponse(content=doc)


def _hidden_fields(params: dict) -> str:
    parts = []
    for key, value in params.items():
        if value is None:
            continue
        parts.append(
            f'<input type="hidden" name="{html.escape(key)}" value="{html.escape(str(value))}"/>'
        )
    return "\n".join(parts)


def _authorize_query_params(request: Request) -> dict:
    q = request.query_params
    return {
        "client_id": q.get("client_id"),
        "redirect_uri": q.get("redirect_uri"),
        "response_type": q.get("response_type", "code"),
        "code_challenge": q.get("code_challenge"),
        "code_challenge_method": q.get("code_challenge_method", "S256"),
        "resource": q.get("resource"),
        "scope": q.get("scope", "read"),
        "state": q.get("state"),
    }


async def _validate_authorize_params(
    params: dict, *, fetch_cimd: bool = True
) -> List[str]:
    """Validate authorize request params. Raises HTTPException (not redirect)
    when redirect_uri / client_id are unusable.
    """
    client_id = params.get("client_id")
    redirect_uri = params.get("redirect_uri")
    if not client_id or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_id and redirect_uri are required",
        )
    await validate_client_redirect(client_id, redirect_uri, fetch_cimd=fetch_cimd)

    if params.get("response_type") != "code":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="response_type must be code",
        )

    method = params.get("code_challenge_method") or "S256"
    if method == "plain":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PKCE plain is not supported; use S256",
        )
    if method != "S256":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="code_challenge_method must be S256",
        )
    challenge = params.get("code_challenge")
    if not challenge or len(challenge) < 43:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="code_challenge is required (S256)",
        )

    resource = params.get("resource")
    if resource != MCP_RESOURCE_URL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"resource must equal {MCP_RESOURCE_URL}",
        )

    return parse_scopes(params.get("scope"))


def _login_html(params: dict, error: Optional[str] = None) -> HTMLResponse:
    err = f'<p class="err">{html.escape(error)}</p>' if error else ""
    body = f"""
  <h1>PenCMS MCP — Sign in</h1>
  <p class="meta">Admin session required to authorize an MCP client.</p>
  {err}
  <form method="post" action="/oauth/authorize/login">
    {_hidden_fields(params)}
    <label for="username">Username</label>
    <input id="username" name="username" type="text" required autocomplete="username"/>
    <label for="password">Password</label>
    <input id="password" name="password" type="password" required autocomplete="current-password"/>
    <button type="submit">Sign in</button>
  </form>
"""
    return _html_page("Sign in — PenCMS MCP", body)


def _consent_html(
    params: dict,
    user: UserPublic,
    keys: list,
    scopes: List[str],
    error: Optional[str] = None,
) -> HTMLResponse:
    err = f'<p class="err">{html.escape(error)}</p>' if error else ""
    if not keys:
        body = f"""
  <h1>PenCMS MCP — Consent</h1>
  <p class="err">No agent keys found. Create one in the admin UI, then retry.</p>
  <p class="meta">Signed in as {html.escape(user.username)}</p>
"""
        return _html_page("Consent — PenCMS MCP", body)

    options = []
    for k in keys:
        scopes_label = ", ".join(k["scopes"])
        site = k.get("site_id") or "default"
        label = f"{site} · {k['name']} ({scopes_label})"
        options.append(
            f'<option value="{k["id"]}">{html.escape(label)}</option>'
        )
    scope_checks = []
    for s in ["read", "write"]:
        checked = " checked" if s in scopes else ""
        disabled = "" if s in ALLOWED_SCOPES else " disabled"
        scope_checks.append(
            f'<label><input type="checkbox" name="consent_scope" value="{s}"'
            f"{checked}{disabled}/> {s}</label>"
        )

    body = f"""
  <h1>PenCMS MCP — Authorize client</h1>
  <p class="meta">Signed in as {html.escape(user.username)}. Client:
    <code>{html.escape(params.get("client_id") or "")}</code></p>
  <p class="meta">Resource: <code>{html.escape(params.get("resource") or "")}</code></p>
  {err}
  <form method="post" action="/oauth/authorize/consent">
    {_hidden_fields(params)}
    <label for="key_index">Agent key</label>
    <select id="key_index" name="key_index" required>
      {"".join(options)}
    </select>
    <div class="scopes">
      <label>Scopes (must be ⊆ key scopes)</label>
      {"".join(scope_checks)}
    </div>
    <button type="submit">Allow</button>
  </form>
"""
    return _html_page("Consent — PenCMS MCP", body)


@router.get("/oauth/authorize")
async def oauth_authorize(request: Request):
    """OAuth 2.1 authorization endpoint — admin session + agent-key consent."""
    params = _authorize_query_params(request)
    user = await get_optional_user(request)
    fetch_cimd = user is not None
    try:
        scopes = await _validate_authorize_params(params, fetch_cimd=fetch_cimd)
    except HTTPException as exc:
        # If redirect_uri is usable, prefer OAuth error redirect for some errors.
        # Unauthenticated CIMD cannot confirm redirect_uri pairing without a fetch.
        redirect_uri = params.get("redirect_uri")
        client_id = params.get("client_id")
        if (
            redirect_uri
            and client_id
            and redirect_uri_allowed(redirect_uri)
            and exc.status_code == 400
            and "resource" in (exc.detail or "").lower()
            and (fetch_cimd or not urlparse(client_id).scheme)
        ):
            try:
                await validate_client_redirect(
                    client_id, redirect_uri, fetch_cimd=fetch_cimd
                )
                return _oauth_error_redirect(
                    redirect_uri,
                    "invalid_request",
                    str(exc.detail),
                    params.get("state"),
                )
            except HTTPException:
                pass
        raise

    if user is None:
        return _login_html(params)

    full = get_user_by_uuid(user.uuid)
    if full is None:
        return _login_html(params, error="User no longer exists")

    keys = [
        {
            "id": i,
            "name": k.name,
            "scopes": list(k.scopes),
            "site_id": getattr(k, "site_id", None) or "default",
        }
        for i, k in enumerate(full.auth.agent_keys)
    ]
    return _consent_html(params, user, keys, scopes)


@router.post("/oauth/authorize/login")
async def oauth_authorize_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    response_type: str = Form("code"),
    code_challenge: str = Form(...),
    code_challenge_method: str = Form("S256"),
    resource: str = Form(...),
    scope: str = Form("read"),
    state: Optional[str] = Form(None),
):
    """Minimal login for the authorize flow; sets pen_jwt and redirects back."""
    from services.auth_service import create_access_token

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": response_type,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "resource": resource,
        "scope": scope,
        "state": state,
    }

    user = get_user_by_username(username)
    if not user:
        user = get_user_by_uuid(username)
    if not user or not verify_password(password, user.auth.password_hash):
        return _login_html(params, error="Incorrect username or password")

    token = create_access_token(
        data={"sub": user.public.uuid, "role": user.public.role}
    )
    qs = urlencode({k: v for k, v in params.items() if v is not None})
    resp = RedirectResponse(
        url=f"/oauth/authorize?{qs}",
        status_code=status.HTTP_302_FOUND,
    )
    resp.set_cookie(
        key="pen_jwt",
        value=token,
        httponly=True,
        samesite="strict",
        max_age=60 * 24 * 7 * 60,
        secure=False,
    )
    return resp


@router.post("/oauth/authorize/consent")
async def oauth_authorize_consent(
    request: Request,
    key_index: int = Form(...),
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    response_type: str = Form("code"),
    code_challenge: str = Form(...),
    code_challenge_method: str = Form("S256"),
    resource: str = Form(...),
    scope: str = Form("read"),
    state: Optional[str] = Form(None),
    consent_scope: List[str] = Form(default=[]),
):
    """Issue a single-use auth code after admin picks an agent key + scopes."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": response_type,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "resource": resource,
        "scope": scope,
        "state": state,
    }

    user = await get_optional_user(request)
    if user is None:
        return _login_html(params, error="Session required")

    try:
        requested = await _validate_authorize_params(params)
    except HTTPException as exc:
        if redirect_uri_allowed(redirect_uri):
            try:
                await validate_client_redirect(client_id, redirect_uri)
                return _oauth_error_redirect(
                    redirect_uri,
                    "invalid_request",
                    str(exc.detail),
                    state,
                )
            except HTTPException:
                pass
        raise

    # Consent scopes from checkboxes override the query scope when present
    if consent_scope:
        granted = []
        for s in consent_scope:
            if s not in ALLOWED_SCOPES:
                continue
            if s not in granted:
                granted.append(s)
    else:
        granted = requested

    if not granted:
        full = get_user_by_uuid(user.uuid)
        keys = [
            {
                "id": i,
                "name": k.name,
                "scopes": list(k.scopes),
                "site_id": getattr(k, "site_id", None) or "default",
            }
            for i, k in enumerate(full.auth.agent_keys)
        ] if full else []
        return _consent_html(
            params, user, keys, requested, error="Select at least one scope"
        )

    full = get_user_by_uuid(user.uuid)
    if full is None:
        return _login_html(params, error="User no longer exists")

    if key_index < 0 or key_index >= len(full.auth.agent_keys):
        keys = [
            {
                "id": i,
                "name": k.name,
                "scopes": list(k.scopes),
                "site_id": getattr(k, "site_id", None) or "default",
            }
            for i, k in enumerate(full.auth.agent_keys)
        ]
        return _consent_html(
            params, user, keys, granted, error="Invalid agent key selection"
        )

    key_meta = full.auth.agent_keys[key_index]
    key_scopes = set(key_meta.scopes or [])
    if not set(granted).issubset(key_scopes):
        keys = [
            {
                "id": i,
                "name": k.name,
                "scopes": list(k.scopes),
                "site_id": getattr(k, "site_id", None) or "default",
            }
            for i, k in enumerate(full.auth.agent_keys)
        ]
        return _consent_html(
            params,
            user,
            keys,
            granted,
            error="Requested scopes exceed the selected agent key",
        )

    code = secrets.token_urlsafe(32)
    store_auth_code(
        code,
        client_id=client_id,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method or "S256",
        resource=resource,
        scopes=granted,
        user_uuid=user.uuid,
        key_index=key_index,
        key_id=key_meta.key_id,
    )

    # RFC 9207: clients must validate iss before redeeming the code
    redir_params = {"code": code, "iss": JWT_ISSUER}
    if state is not None:
        redir_params["state"] = state
    return RedirectResponse(
        url=_append_query(redirect_uri, redir_params),
        status_code=status.HTTP_302_FOUND,
    )


def _token_error(error: str, description: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "error_description": description},
    )


def _mint_token_response(
    *,
    user_uuid: str,
    role: str,
    scopes: List[str],
    client_id: str,
    resource: str,
    key_index: int,
    agent_key_name: str,
    agent_key_id: str,
    site_id: str = "default",
) -> dict:
    access = create_agent_access_token(
        {
            "sub": user_uuid,
            "role": role,
            "scopes": scopes,
            "type": "agent",
            "jti": str(uuid.uuid4()),
            "site_id": site_id or "default",
            "agent_key_name": agent_key_name,
            "agent_key_id": agent_key_id,
            "agent_key_index": key_index,
        }
    )
    refresh = secrets.token_urlsafe(48)
    store_refresh_token(
        refresh,
        client_id=client_id,
        resource=resource,
        scopes=scopes,
        user_uuid=user_uuid,
        key_index=key_index,
        key_id=agent_key_id,
    )
    return {
        "access_token": access,
        "token_type": "bearer",
        "expires_in": AGENT_TOKEN_EXPIRE_MINUTES * 60,
        "refresh_token": refresh,
        "scope": " ".join(scopes),
    }


@router.post("/oauth/token")
async def oauth_token(request: Request):
    """Token endpoint: authorization_code (+ PKCE S256) or refresh_token."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
    else:
        form = await request.form()
        body = dict(form)

    def body_string(key: str) -> Optional[str]:
        value = body.get(key)
        return value if isinstance(value, str) else None

    grant_type = body_string("grant_type")
    client_id = body_string("client_id")
    resource = body_string("resource")

    if not client_id:
        return _token_error("invalid_request", "client_id is required")

    if grant_type == "authorization_code":
        code = body_string("code")
        code_verifier = body_string("code_verifier")
        redirect_uri = body_string("redirect_uri")
        if not code or not code_verifier or not redirect_uri:
            return _token_error(
                "invalid_request",
                "code, code_verifier, and redirect_uri are required",
            )
        if resource != MCP_RESOURCE_URL:
            return _token_error(
                "invalid_target",
                f"resource must equal {MCP_RESOURCE_URL}",
            )

        # Reject explicit plain PKCE if a client somehow sends the method
        method = body_string("code_challenge_method")
        if method == "plain":
            return _token_error(
                "invalid_request",
                "PKCE plain is not supported; use S256",
            )

        record = consume_auth_code(code)
        if record is None:
            return _token_error("invalid_grant", "Invalid or expired authorization code")

        if record.client_id != client_id:
            return _token_error("invalid_grant", "client_id mismatch")
        if record.redirect_uri != redirect_uri:
            return _token_error("invalid_grant", "redirect_uri mismatch")
        if record.resource != resource:
            return _token_error("invalid_grant", "resource mismatch")
        if record.code_challenge_method != "S256":
            return _token_error("invalid_grant", "PKCE plain is not supported")

        expected = _pkce_s256_challenge(code_verifier)
        if not secrets.compare_digest(expected, record.code_challenge):
            return _token_error("invalid_grant", "PKCE verification failed")

        user = get_user_by_uuid(record.user_uuid)
        if user is None:
            return _token_error("invalid_grant", "User no longer exists")

        key_matches = [
            (index, key)
            for index, key in enumerate(user.auth.agent_keys)
            if record.key_id and key.key_id == record.key_id
        ]
        if len(key_matches) != 1:
            return _token_error("invalid_grant", "Selected agent key was revoked")
        current_key_index, key_meta = key_matches[0]
        if not set(record.scopes).issubset(set(key_meta.scopes)):
            return _token_error("invalid_grant", "Selected agent key scopes changed")
        site_id = getattr(key_meta, "site_id", None) or "default"

        return _mint_token_response(
            user_uuid=user.public.uuid,
            role=user.public.role,
            scopes=record.scopes,
            client_id=client_id,
            resource=MCP_RESOURCE_URL,
            key_index=current_key_index,
            site_id=site_id,
            agent_key_name=key_meta.name,
            agent_key_id=key_meta.key_id,
        )

    if grant_type == "refresh_token":
        refresh = body_string("refresh_token")
        if not refresh:
            return _token_error("invalid_request", "refresh_token is required")
        if resource != MCP_RESOURCE_URL:
            return _token_error(
                "invalid_target",
                f"resource must equal {MCP_RESOURCE_URL}",
            )

        record = consume_refresh_token(refresh)
        if record is None:
            return _token_error("invalid_grant", "Invalid or expired refresh token")
        if record.client_id != client_id:
            return _token_error("invalid_grant", "client_id mismatch")
        if record.resource != resource:
            return _token_error("invalid_grant", "resource mismatch")

        user = get_user_by_uuid(record.user_uuid)
        if user is None:
            return _token_error("invalid_grant", "User no longer exists")

        key_matches = [
            (index, key)
            for index, key in enumerate(user.auth.agent_keys)
            if record.key_id and key.key_id == record.key_id
        ]
        if len(key_matches) != 1:
            return _token_error("invalid_grant", "Selected agent key was revoked")
        current_key_index, key_meta = key_matches[0]
        if not set(record.scopes).issubset(set(key_meta.scopes)):
            return _token_error("invalid_grant", "Selected agent key scopes changed")
        site_id = getattr(key_meta, "site_id", None) or "default"

        return _mint_token_response(
            user_uuid=user.public.uuid,
            role=user.public.role,
            scopes=record.scopes,
            client_id=client_id,
            resource=MCP_RESOURCE_URL,
            key_index=current_key_index,
            site_id=site_id,
            agent_key_name=key_meta.name,
            agent_key_id=key_meta.key_id,
        )

    return _token_error(
        "unsupported_grant_type",
        "grant_type must be authorization_code or refresh_token",
    )
