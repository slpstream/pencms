"""Site-scoped capability vocabulary shared by humans and agents.

Authorize from JWT → user YAML (never from forgeable cookies). Agent tokens
are bound to JWT scopes + site_id and must not inherit the sponsor's role.
"""

from __future__ import annotations

from typing import FrozenSet, Iterable, List, Optional, Tuple

import jwt
from fastapi import HTTPException, Request, status

from models.user import User, UserPublic
from services.auth_service import decode_access_token
from services.user_service import get_user_by_uuid

# Granular v1 vocabulary (plus monolithic read and host publish).
ALLOWED_CAPABILITIES: FrozenSet[str] = frozenset(
    {
        "read",
        "write:posts",
        "delete:posts",
        "write:pages",
        "delete:pages",
        "write:media",
        "delete:media",
        "publish:content",
        "write:menus",
        "write:authors",
        "write:seo",
        "write:theme",
        "write:taxonomy",
        "publish",
        "users:manage",
        "manage:sites",
    }
)

LEGACY_AGENT_SCOPES: FrozenSet[str] = frozenset({"read", "write", "publish"})

# Agent keys may store granular caps and/or legacy aliases.
ALLOWED_AGENT_SCOPES: FrozenSet[str] = ALLOWED_CAPABILITIES | LEGACY_AGENT_SCOPES

# Stable order for mint responses, OAuth metadata, and scope validation.
SCOPE_ORDER: Tuple[str, ...] = (
    "read",
    "write",
    "write:posts",
    "delete:posts",
    "write:pages",
    "delete:pages",
    "write:media",
    "delete:media",
    "publish:content",
    "write:menus",
    "write:authors",
    "write:seo",
    "write:theme",
    "write:taxonomy",
    "publish",
    "users:manage",
    "manage:sites",
)

# Legacy `write` expands one-way to content/theme writes + deletes + content publish.
# Host `publish`, `users:manage`, and `manage:sites` are never implied.
WRITE_EXPANSION: FrozenSet[str] = frozenset(
    {
        "write:posts",
        "delete:posts",
        "write:pages",
        "delete:pages",
        "write:media",
        "delete:media",
        "publish:content",
        "write:menus",
        "write:authors",
        "write:seo",
        "write:theme",
        "write:taxonomy",
    }
)


def ordered_allowed_scopes() -> List[str]:
    """ALLOWED_AGENT_SCOPES in SCOPE_ORDER (for OAuth scopes_supported)."""
    allowed = ALLOWED_AGENT_SCOPES
    return [s for s in SCOPE_ORDER if s in allowed]


def expand_capabilities(caps: Optional[Iterable[str]] = None) -> FrozenSet[str]:
    """One-way expansion: legacy `write` → all write:*, delete:*, publish:content.

    `write:posts` does not imply `write` or `write:theme`.
    `publish:content` does not imply host `publish`.
    """
    out = {c for c in (caps or []) if c}
    if "write" in out:
        out |= WRITE_EXPANSION
    return frozenset(out)


def caps_for_actor(
    user: User,
    *,
    site_id: str,
    token_payload: Optional[dict] = None,
) -> FrozenSet[str]:
    """Effective capabilities for this actor on site_id.

    Agents: expanded JWT scopes only (never the sponsor's admin role).
    Human admin: all ALLOWED_CAPABILITIES on every site.
    Human author: expanded memberships for site_id, else empty.
    """
    payload = token_payload or {}
    if payload.get("type") == "agent":
        scopes = payload.get("scopes") or []
        if not isinstance(scopes, (list, tuple, set, frozenset)):
            scopes = list(scopes) if scopes else []
        return expand_capabilities(scopes)
    if user.public.role == "admin":
        return ALLOWED_CAPABILITIES
    wanted = site_id or "default"
    for membership in user.auth.memberships or []:
        mid = getattr(membership, "site_id", None)
        if mid == wanted:
            return expand_capabilities(getattr(membership, "capabilities", None) or [])
    return frozenset()


def has_capability(
    user: User,
    capability: str,
    *,
    site_id: str,
    token_payload: Optional[dict] = None,
) -> bool:
    return capability in caps_for_actor(
        user, site_id=site_id, token_payload=token_payload
    )


def ordered_caps(caps: Optional[Iterable[str]] = None) -> List[str]:
    """Stable capability list: SCOPE_ORDER first, then leftover names sorted."""
    wanted = {c for c in (caps or []) if c}
    ordered = [s for s in SCOPE_ORDER if s in wanted]
    extra = sorted(wanted.difference(SCOPE_ORDER))
    return ordered + extra


def may_access_site(
    user: User,
    site_id: str,
    *,
    token_payload: Optional[dict] = None,
) -> bool:
    """May this actor bind to site_id? Agent JWT site first; never sponsor role."""
    payload = token_payload or {}
    if payload.get("type") == "agent":
        return str(payload.get("site_id") or "") == str(site_id)
    if user.public.role == "admin":
        return True
    wanted = site_id or "default"
    for membership in user.auth.memberships or []:
        if getattr(membership, "site_id", None) == wanted:
            return True
    return False


def accessible_site_ids(
    user: User,
    *,
    token_payload: Optional[dict] = None,
    all_site_ids: Iterable[str],
) -> List[str]:
    """Registry-order site ids this actor may see. Admin: all. Agent: JWT only."""
    ids = [str(s) for s in all_site_ids if s]
    payload = token_payload or {}
    if payload.get("type") == "agent":
        jwt_sid = str(payload.get("site_id") or "")
        return [sid for sid in ids if sid == jwt_sid]
    if user.public.role == "admin":
        return list(ids)
    allowed = {
        getattr(m, "site_id", None)
        for m in (user.auth.memberships or [])
        if getattr(m, "site_id", None)
    }
    return [sid for sid in ids if sid in allowed]


def reject_if_blocked(user: User) -> None:
    if getattr(user.public, "status", "active") == "blocked":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="account_suspended",
        )


def reject_if_must_change_password(
    user: User, request: Request, payload: Optional[dict] = None
) -> None:
    """403 password_change_required except /me and change-password.

    Agent JWTs skip this lock (human password hygiene only).
    """
    payload = payload or {}
    if payload.get("type") == "agent":
        return
    if not getattr(user.auth, "must_change_password", False):
        return
    method = (request.method or "").upper()
    path = (request.url.path or "").rstrip("/")
    if method == "GET" and path.endswith("/auth/me"):
        return
    if method == "POST" and path.endswith("/auth/change-password"):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="password_change_required",
    )


def token_from_request(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth.split(" ", 1)[1]
    return request.cookies.get("pen_jwt")


def resolve_request_user(request: Request) -> Tuple[User, dict]:
    """JWT (Bearer or pen_jwt) → YAML user. 401 if missing; 403 if blocked."""
    token = token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        payload = decode_access_token(token)
        uuid = payload.get("sub")
        if uuid is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    user = get_user_by_uuid(str(uuid))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists"
        )
    reject_if_blocked(user)
    reject_if_must_change_password(user, request, payload)
    return user, payload


async def require_admin(request: Request) -> UserPublic:
    """Human session whose YAML role is admin. Agent JWTs never qualify."""
    user, payload = resolve_request_user(request)
    if payload.get("type") == "agent" or user.public.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin required"
        )
    return user.public


def assert_capability(
    request: Request,
    capability: str,
    *,
    site_id: Optional[str] = None,
) -> UserPublic:
    """Raise 403 unless this actor may do `capability` on site_id.

    When site_id is omitted: agents use JWT site_id; humans use
    resolve_human_site_id. Pass an explicit resource site (path/query/body)
    so a writer on one tenant cannot mutate another via the URL.
    """
    user, payload = resolve_request_user(request)
    resolved = site_id
    if resolved is None:
        if payload.get("type") == "agent":
            resolved = payload.get("site_id")
            if not resolved:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Agent token missing site_id claim",
                )
        else:
            from services.site_service import resolve_human_site_id

            resolved = resolve_human_site_id(request)
    if not has_capability(
        user, capability, site_id=str(resolved), token_payload=payload
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"missing_capability: {capability}",
        )
    return user.public


def require_capability(capability: str):
    """FastAPI dependency factory: may this actor do `capability` on the active site?"""

    async def _check(request: Request) -> UserPublic:
        return assert_capability(request, capability)

    return _check
