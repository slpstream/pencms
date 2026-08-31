from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Tuple
import re
import secrets

from models.user import User, UserPublic, TokenRequest, VaultUpdateRequest, AgentKeyMetadata
from services.user_service import get_user_by_username, get_user_by_uuid, save_user, touch_last_login, utc_now_stamp
from services.auth_service import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_agent_access_token,
)
from services.authz import (
    ALLOWED_AGENT_SCOPES,
    SCOPE_ORDER,
    accessible_site_ids,
    caps_for_actor,
    ordered_caps,
    reject_if_blocked,
    require_admin,
    resolve_request_user,
)
from services.storage_provider import vault_secrets
from services.vault_headers import secrets_from_request

router = APIRouter(prefix="/auth", tags=["auth"])

AGENT_KEY_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


def validate_agent_key_name(name: str) -> str:
    """Normalize and validate a human-facing agent key name (slug)."""
    normalized = (name or "").strip().lower()
    if not AGENT_KEY_NAME_RE.match(normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid name. Use 2–64 chars: lowercase letters, digits, "
                "hyphens or underscores (e.g. cursor, claude, writing-partner)."
            ),
        )
    return normalized


def validate_agent_scopes(scopes: List[str]) -> List[str]:
    if not set(scopes).issubset(ALLOWED_AGENT_SCOPES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scopes. Allowed: {set(ALLOWED_AGENT_SCOPES)}",
        )
    wanted = set(scopes)
    ordered = [s for s in SCOPE_ORDER if s in wanted]
    if not ordered:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one scope is required",
        )
    return ordered


def session_payload(
    user: User,
    request: Request,
    *,
    token_payload: Optional[dict] = None,
    message: Optional[str] = None,
) -> dict:
    """Login and /auth/me share this shape so Alpine has one session object.

    ``user`` stays UserPublic-only. Memberships/caps are top-level so PUT
    /profile cannot round-trip them. Agent tokens never copy sponsor memberships.
    """
    from services.edition import get_edition
    from services.site_service import (
        DEFAULT_SITE_ID,
        HUMAN_SITE_COOKIE,
        HUMAN_SITE_HEADER,
        ensure_sites_initialized,
        list_sites,
        validate_site_id,
    )

    payload = token_payload or {}
    ensure_sites_initialized()
    all_ids = [s.id for s in list_sites()]
    is_agent = payload.get("type") == "agent"

    if is_agent:
        memberships: List[dict] = []
    else:
        memberships = [
            {
                "site_id": m.site_id,
                "capabilities": list(m.capabilities or []),
            }
            for m in (user.auth.memberships or [])
        ]

    accessible = accessible_site_ids(
        user, token_payload=payload, all_site_ids=all_ids
    )

    if is_agent:
        jwt_sid = str(payload.get("site_id") or "")
        if jwt_sid in accessible:
            active = jwt_sid
        elif accessible:
            active = accessible[0]
        else:
            active = jwt_sid or DEFAULT_SITE_ID
    else:
        raw = request.headers.get(HUMAN_SITE_HEADER)
        if raw is None or not str(raw).strip():
            raw = request.cookies.get(HUMAN_SITE_COOKIE)
        preferred = None
        if raw and str(raw).strip():
            try:
                preferred = validate_site_id(raw)
            except ValueError:
                preferred = None
        if preferred and preferred in accessible:
            active = preferred
        elif DEFAULT_SITE_ID in accessible and not preferred:
            active = DEFAULT_SITE_ID
        elif accessible:
            active = accessible[0]
        else:
            active = DEFAULT_SITE_ID

    caps = ordered_caps(
        caps_for_actor(user, site_id=str(active), token_payload=payload)
    )
    body = {
        "user": user.public,
        "vault": user.vault,
        "must_change_password": bool(
            getattr(user.auth, "must_change_password", False)
        ),
        "memberships": memberships,
        "accessible_sites": accessible,
        "active_site_id": active,
        "capabilities": caps,
        "edition": get_edition(),
    }
    if message:
        return {"message": message, **body}
    return body


def mint_agent_key_for_user(
    user: User, name: str, scopes: List[str], site_id: str
) -> Tuple[str, AgentKeyMetadata]:
    """Create a pen-sk-… secret and metadata; append to user.auth.agent_keys.

    Caller must ``save_user``. Raises 400 if name already exists on this user
    or site_id is unknown.
    """
    from datetime import datetime
    from services.site_service import (
        DEFAULT_SITE_ID,
        ensure_sites_initialized,
        get_site,
        validate_site_id,
    )

    name = validate_agent_key_name(name)
    scopes = validate_agent_scopes(scopes)
    ensure_sites_initialized()
    try:
        site_id = validate_site_id(site_id or DEFAULT_SITE_ID)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if get_site(site_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown site_id: {site_id}",
        )

    for existing in user.auth.agent_keys:
        if isinstance(existing, AgentKeyMetadata) and existing.name == name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An agent key named '{name}' already exists",
            )
        if isinstance(existing, dict) and existing.get("name") == name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An agent key named '{name}' already exists",
            )

    token = f"pen-sk-{secrets.token_hex(24)}"
    meta = AgentKeyMetadata(
        key_id=f"ak_{secrets.token_hex(12)}",
        hash=get_password_hash(token),
        name=name,
        created_at=datetime.now().strftime("%Y-%m-%d"),
        scopes=scopes,
        site_id=site_id,
    )
    user.auth.agent_keys.append(meta)
    return token, meta

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str

async def get_current_user(request: Request) -> UserPublic:
    """FastAPI Dependency to get the current authenticated user from cookie or bearer token."""
    site_id = (request.headers.get("X-Pen-Site-Id") or "").strip() or "default"
    vault_secrets.set(secrets_from_request(request.headers, site_id))

    user, _payload = resolve_request_user(request)
    return user.public

async def get_optional_user(request: Request) -> Optional[UserPublic]:
    """FastAPI Dependency to get the current authenticated user, but return None if not authenticated."""
    site_id = (request.headers.get("X-Pen-Site-Id") or "").strip() or "default"
    vault_secrets.set(secrets_from_request(request.headers, site_id))

    token = None

    # 1. Check Authorization header (Bearer token for agents/API)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]

    # 2. Check cookies (for human web users)
    if not token:
        token = request.cookies.get("pen_jwt")

    if not token:
        return None

    try:
        user, _payload = resolve_request_user(request)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            raise
        return None
    return user.public


@router.get("/status")
async def system_status():
    """Check if the system has any users initialized."""
    from services.user_service import list_users
    return {"initialized": len(list_users()) > 0}

@router.post("/setup")
async def setup_first_user(req: RegisterRequest):
    """Bootstrap endpoint to create the very first user (admin). Fails if any users exist."""
    from services.user_service import list_users
    import uuid
    from models.user import UserAuth
    
    if " " in req.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must not contain spaces."
        )
        
    existing_users = list_users()
    if len(existing_users) > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System already initialized. Registration is disabled."
        )
        
    new_uuid = str(uuid.uuid4())
    hashed = get_password_hash(req.password)
    
    new_user = User(
        public=UserPublic(
            uuid=new_uuid,
            username=req.username,
            display_name=req.username, # Fallback to username initially
            role="admin",
            status="active",
            is_bootstrap=True,
            created_at=utc_now_stamp(),
        ),
        auth=UserAuth(password_hash=hashed, agent_keys=[]),
        vault=None
    )
    
    if save_user(new_user):
        return {"message": "First user created successfully", "uuid": new_uuid}
    raise HTTPException(status_code=500, detail="Failed to create user")

@router.post("/login")
async def login(req: LoginRequest, response: Response, request: Request):
    """Human login endpoint. Issues an HttpOnly cookie and returns the user's encrypted vault."""
    # We can login by email or uuid, but the prompt says email is primary
    # We can login by username or uuid
    user = get_user_by_username(req.username)
    if not user:
        # Fallback to check if they typed their UUID
        user = get_user_by_uuid(req.username)
        
    if not user or not verify_password(req.password, user.auth.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    reject_if_blocked(user)
    touch_last_login(user)

    # Create JWT
    access_token = create_access_token(data={"sub": user.public.uuid, "role": user.public.role})
    
    # Set HttpOnly cookie. SameSite=Strict to prevent CSRF. 
    # Secure=True should be used in production (HTTPS).
    response.set_cookie(
        key="pen_jwt",
        value=access_token,
        httponly=True,
        samesite="strict",
        max_age=60 * 24 * 7 * 60, # 7 days in seconds
        secure=False, # Set to True in production with HTTPS
    )
    
    return session_payload(user, request, token_payload={}, message="Login successful")

@router.get("/keys")
async def list_agent_keys(current_user: UserPublic = Depends(require_admin)):
    """List metadata for agent keys."""
    from models.user import AgentKeyMetadata
    from datetime import datetime
    user = get_user_by_uuid(current_user.uuid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Migration and Metadata extraction
    sanitized_keys = []
    needs_save = False
    
    for i, key_data in enumerate(user.auth.agent_keys):
        # Handle migration from old List[str] if necessary
        if isinstance(key_data, str):
            new_meta = AgentKeyMetadata(
                key_id=f"ak_{secrets.token_hex(12)}",
                hash=key_data,
                name=f"Legacy Key {i+1}",
                created_at=datetime.now().strftime("%Y-%m-%d")
            )
            user.auth.agent_keys[i] = new_meta
            key_data = new_meta
            needs_save = True
        
        sanitized_keys.append({
            "id": i,
            "key_id": key_data.key_id,
            "name": key_data.name,
            "created_at": key_data.created_at,
            "scopes": key_data.scopes,
            "site_id": getattr(key_data, "site_id", None) or "default",
        })
    
    if needs_save:
        save_user(user)
        
    return {"keys": sanitized_keys}

class CreateKeyRequest(BaseModel):
    name: str = Field(..., description="Human label for this agent, e.g. blog-cursor")
    scopes: List[str] = Field(default_factory=lambda: ["read"])
    site_id: str = Field(
        default="default",
        description="Site this key is bound to, e.g. default",
    )

@router.post("/keys")
async def create_agent_key(
    req: CreateKeyRequest,
    current_user: UserPublic = Depends(require_admin)
):
    """Generate a new named agent key, hash it, and store it with metadata."""
    user = get_user_by_uuid(current_user.uuid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token, meta = mint_agent_key_for_user(user, req.name, req.scopes, req.site_id)
    if save_user(user):
        return {
            "key": token,
            "name": meta.name,
            "key_id": meta.key_id,
            "scopes": meta.scopes,
            "site_id": meta.site_id,
            "message": "Key created successfully.",
        }
    raise HTTPException(status_code=500, detail="Failed to save key")

@router.delete("/keys/{index}")
async def revoke_agent_key(index: int, current_user: UserPublic = Depends(require_admin)):
    """Revoke an agent key by index."""
    user = get_user_by_uuid(current_user.uuid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if 0 <= index < len(user.auth.agent_keys):
        user.auth.agent_keys.pop(index)
        if save_user(user):
            return {"message": "Key revoked successfully"}
    raise HTTPException(status_code=400, detail="Invalid key index")


class PatchKeyRequest(BaseModel):
    site_id: str = Field(..., description="Reassign this key to another site")


@router.patch("/keys/{index}")
async def patch_agent_key(
    index: int,
    req: PatchKeyRequest,
    current_user: UserPublic = Depends(require_admin),
):
    """Reassign an agent key's site_id without reminting the secret.

    Existing JWTs keep the old site_id claim until they expire; new tokens
    from /api/auth/token (and OAuth refresh) pick up the updated binding.
    """
    from services.site_service import (
        ensure_sites_initialized,
        get_site,
        validate_site_id,
    )

    user = get_user_by_uuid(current_user.uuid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not (0 <= index < len(user.auth.agent_keys)):
        raise HTTPException(status_code=400, detail="Invalid key index")

    ensure_sites_initialized()
    try:
        site_id = validate_site_id(req.site_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if get_site(site_id) is None:
        raise HTTPException(
            status_code=400, detail=f"Unknown site_id: {site_id}"
        )

    key_meta = user.auth.agent_keys[index]
    if isinstance(key_meta, AgentKeyMetadata):
        key_meta.site_id = site_id
    elif isinstance(key_meta, dict):
        key_meta["site_id"] = site_id
    else:
        raise HTTPException(status_code=400, detail="Invalid key metadata")

    if save_user(user):
        return {
            "id": index,
            "name": getattr(key_meta, "name", None)
            or (key_meta.get("name") if isinstance(key_meta, dict) else None),
            "site_id": site_id,
            "message": (
                "Key site reassigned. Existing JWTs keep the old site_id "
                "until expiry; mint a new token to use the new site."
            ),
        }
    raise HTTPException(status_code=500, detail="Failed to save key")


@router.post("/token")
async def login_for_agent_token(req: TokenRequest):
    """Agent login endpoint. Issues a Bearer token based on static API key."""
    # Since agent_key is unique, we must find the user who has this key.
    # In a real system, we'd hash the provided key and look it up.
    # Since we store bcrypt hashes of agent keys, we have to iterate users.
    # For a small user base, this is fine. For large, we'd need a different index.
    from services.user_service import USERS_DIR
    import os, yaml
    
    valid_user = None
    matching_scopes = []
    matching_site_id = "default"
    matching_key_name = None
    matching_key_id = None
    matching_key_index = None
    for filename in os.listdir(USERS_DIR):
        if not filename.endswith(".yaml"): continue
        try:
            filepath = USERS_DIR / filename
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                u = User(**data)
                for key_index, key_meta in enumerate(u.auth.agent_keys):
                    if verify_password(req.agent_key, key_meta.hash):
                        valid_user = u
                        matching_scopes = key_meta.scopes
                        matching_site_id = getattr(key_meta, "site_id", None) or "default"
                        matching_key_name = key_meta.name
                        matching_key_id = key_meta.key_id
                        matching_key_index = key_index
                        break
            if valid_user:
                break
        except Exception:
            continue
            
    if not valid_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent key",
        )
        
    access_token = create_agent_access_token(data={
        "sub": valid_user.public.uuid,
        "role": valid_user.public.role,
        "scopes": matching_scopes,
        "type": "agent",
        "site_id": matching_site_id,
        "agent_key_name": matching_key_name,
        "agent_key_id": matching_key_id,
        "agent_key_index": matching_key_index,
    })
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/vault")
async def get_vault(current_user: UserPublic = Depends(get_current_user)):
    """Fetch the encrypted vault for the current user."""
    user = get_user_by_uuid(current_user.uuid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"vault": user.vault}

@router.put("/vault")
async def update_vault(req: VaultUpdateRequest, current_user: UserPublic = Depends(get_current_user)):
    """Update the encrypted vault for the current user."""
    print(f"Updating vault for user {current_user.uuid}")
    user = get_user_by_uuid(current_user.uuid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.vault = req.vault
    if save_user(user):
        print("Vault saved successfully to disk")
        return {"message": "Vault updated successfully"}
    raise HTTPException(status_code=500, detail="Failed to save vault")

@router.get("/me")
async def get_me(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
):
    """Fetch the session profile: public user, vault, memberships, active-site caps."""
    user, payload = resolve_request_user(request)
    return session_payload(user, request, token_payload=payload)

@router.put("/profile")
async def update_profile(req: UserPublic, current_user: UserPublic = Depends(get_current_user)):
    """Update the user's public profile metadata."""
    print(f"Updating profile for user {current_user.uuid}")
    user = get_user_by_uuid(current_user.uuid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Protection: Do not allow changing UUID, role, status, or bootstrap via this endpoint
    req.uuid = user.public.uuid
    req.role = user.public.role
    req.status = user.public.status
    req.is_bootstrap = user.public.is_bootstrap
    req.created_at = user.public.created_at
    req.last_login_at = user.public.last_login_at
    
    user.public = req
    if save_user(user):
        print("Profile saved successfully to disk")
        return {"message": "Profile updated successfully", "user": user.public}
    raise HTTPException(status_code=500, detail="Failed to save profile")


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, request: Request):
    """Change the authenticated human user's own password."""
    user, payload = resolve_request_user(request)
    if payload.get("type") == "agent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed",
        )
    if not (req.new_password or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="password is required"
        )
    if not verify_password(req.current_password, user.auth.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    user.auth.password_hash = get_password_hash(req.new_password)
    user.auth.must_change_password = False
    if save_user(user):
        return {
            "message": "Password changed successfully",
            "must_change_password": False,
        }
    raise HTTPException(status_code=500, detail="Failed to save password")


@router.post("/logout")
async def logout(response: Response):
    """Clear the JWT cookie."""
    response.delete_cookie(key="pen_jwt", samesite="strict")
    return {"message": "Logged out successfully"}


# ---------------------------------------------------------------------------
# Agent-assisted key bootstrap (approve-code; Option B)
# ---------------------------------------------------------------------------

class BootstrapRequestCodeBody(BaseModel):
    name: str
    scopes: List[str] = Field(default_factory=lambda: ["read"])
    site_id: str = Field(
        default="default",
        description="Site this key will be bound to",
    )


class BootstrapVerifyBody(BaseModel):
    user_code: str


class BootstrapApproveBody(BaseModel):
    user_code: str
    deny: bool = False


@router.post("/agent/request-code")
async def agent_request_code(req: BootstrapRequestCodeBody):
    """Agent starts bootstrap: returns a short user_code for admin approval."""
    from services.bootstrap_store import (
        BOOTSTRAP_TTL_SECONDS,
        create_bootstrap_request,
    )
    from services.site_service import (
        ensure_sites_initialized,
        get_site,
        validate_site_id,
    )

    name = validate_agent_key_name(req.name)
    scopes = validate_agent_scopes(req.scopes)
    ensure_sites_initialized()
    try:
        site_id = validate_site_id(req.site_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if get_site(site_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown site_id: {site_id}",
        )
    try:
        record = create_bootstrap_request(name=name, scopes=scopes, site_id=site_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many bootstrap requests; wait a moment and retry",
        )
    return {
        "user_code": record.user_code,
        "expires_in": BOOTSTRAP_TTL_SECONDS,
        "name": record.name,
        "scopes": record.scopes,
        "site_id": record.site_id,
        "message": (
            "Ask the site admin to approve this code under "
            "Settings → AI → Agent Keys → Pending approvals, then call "
            "POST /api/auth/agent/verify-code with the same user_code."
        ),
    }


@router.get("/agent/pending")
async def agent_list_pending(current_user: UserPublic = Depends(require_admin)):
    """Admin: list pending / approved-not-consumed bootstrap requests."""
    from services.bootstrap_store import list_pending_bootstrap

    return {"pending": list_pending_bootstrap()}


@router.post("/agent/approve")
async def agent_approve_code(
    req: BootstrapApproveBody,
    current_user: UserPublic = Depends(require_admin),
):
    """Admin: approve or deny a bootstrap user_code."""
    from services.bootstrap_store import set_bootstrap_status

    status_value = "denied" if req.deny else "approved"
    result = set_bootstrap_status(
        req.user_code,
        status_value,
        sponsor_uuid=None if req.deny else current_user.uuid,
    )
    if result is None:
        raise HTTPException(
            status_code=400,
            detail="Unknown, expired, or already finalized bootstrap code",
        )
    return {"message": f"Bootstrap request {status_value}", **result}


@router.post("/agent/verify-code")
async def agent_verify_code(req: BootstrapVerifyBody, response: Response):
    """Agent completes bootstrap after admin approval; returns pen-sk-… once."""
    from services.bootstrap_store import mark_bootstrap_consumed, peek_bootstrap

    record = peek_bootstrap(req.user_code)
    if record is None or record.status in ("expired", "denied", "consumed"):
        raise HTTPException(
            status_code=400,
            detail="Invalid, expired, denied, or already used bootstrap code",
        )
    if record.status == "pending":
        response.status_code = status.HTTP_202_ACCEPTED
        return {
            "status": "pending",
            "message": "Waiting for admin approval",
            "retry_after": 3,
        }
    if record.status != "approved":
        raise HTTPException(
            status_code=400,
            detail="Invalid, expired, denied, or already used bootstrap code",
        )

    if not record.sponsor_uuid:
        raise HTTPException(
            status_code=500,
            detail="Approved bootstrap missing sponsor; contact admin",
        )
    user = get_user_by_uuid(record.sponsor_uuid)
    if not user:
        raise HTTPException(status_code=500, detail="Sponsor user no longer exists")

    # Mint first; only consume the code after a successful save.
    token, meta = mint_agent_key_for_user(
        user, record.name, record.scopes, record.site_id or "default"
    )
    if not save_user(user):
        raise HTTPException(status_code=500, detail="Failed to save agent key")
    if not mark_bootstrap_consumed(req.user_code):
        # Key was saved; code may have raced — still return the key once.
        pass
    return {
        "key": token,
        "name": meta.name,
        "scopes": meta.scopes,
        "site_id": meta.site_id,
        "message": (
            "Store this key securely (e.g. ~/.pencms/credentials with mode 0600). "
            "It will not be shown again."
        ),
    }
