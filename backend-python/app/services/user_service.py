import os
import uuid
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.user import SiteMembership, User, UserAuth, UserPublic
from config import BASE_DIR

USERS_DIR = BASE_DIR / "data" / "users"

ALLOWED_ROLES = frozenset({"admin", "author"})
INSTALL_WIDE_CAPS = frozenset({"users:manage", "manage:sites"})


def utc_now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _ensure_users_dir():
    USERS_DIR.mkdir(parents=True, exist_ok=True)


def _count_user_yaml_files() -> int:
    _ensure_users_dir()
    try:
        return sum(1 for name in os.listdir(USERS_DIR) if name.endswith(".yaml"))
    except FileNotFoundError:
        return 0


def _user_from_data(data: dict, *, persist_bootstrap: bool = True) -> User:
    """Parse a user YAML dict and stamp the sole operator as bootstrap admin."""
    public = data.get("public") if isinstance(data.get("public"), dict) else {}
    missing_bootstrap = "is_bootstrap" not in public
    user = User(**data)
    if missing_bootstrap and _count_user_yaml_files() == 1:
        user.public.is_bootstrap = True
        user.public.role = "admin"
        if persist_bootstrap:
            save_user(user)
    return user

def get_user_by_uuid(uuid: str) -> Optional[User]:
    _ensure_users_dir()
    filepath = USERS_DIR / f"{uuid}.yaml"
    if not filepath.exists():
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return _user_from_data(data)
    except Exception as e:
        print(f"Error loading user {uuid}: {e}")
        return None

def get_user_by_username(username: str) -> Optional[User]:
    _ensure_users_dir()
    for filename in os.listdir(USERS_DIR):
        if filename.endswith(".yaml"):
            try:
                filepath = USERS_DIR / filename
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data.get("public", {}).get("username", "").lower() == username.lower():
                        return _user_from_data(data)
            except Exception:
                continue
    return None

def save_user(user: User) -> bool:
    _ensure_users_dir()
    filepath = USERS_DIR / f"{user.public.uuid}.yaml"
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.safe_dump(user.model_dump(), f)
        return True
    except Exception as e:
        print(f"Error saving user {user.public.uuid}: {e}")
        return False

def list_users() -> List[UserPublic]:
    return [u.public for u in iter_users()]


def iter_users() -> List[User]:
    """Load all full User records from disk (including auth.agent_keys)."""
    _ensure_users_dir()
    users: List[User] = []
    for filename in os.listdir(USERS_DIR):
        if not filename.endswith(".yaml"):
            continue
        try:
            filepath = USERS_DIR / filename
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                users.append(_user_from_data(data))
        except Exception as e:
            print(f"Error loading user from {filename}: {e}")
            continue
    return users


def count_agent_keys_for_site(site_id: str) -> int:
    """Count agent keys bound to site_id across all users."""
    count = 0
    for user in iter_users():
        for key in user.auth.agent_keys:
            sid = getattr(key, "site_id", None)
            if sid is None and isinstance(key, dict):
                sid = key.get("site_id")
            if (sid or "default") == site_id:
                count += 1
    return count


def reassign_agent_keys_site(old_site_id: str, new_site_id: str) -> int:
    """Rewrite agent_keys site_id old → new across all users. Returns keys updated."""
    if old_site_id == new_site_id:
        return 0
    updated = 0
    for user in iter_users():
        changed = False
        for key in user.auth.agent_keys:
            sid = getattr(key, "site_id", None)
            if sid is None and isinstance(key, dict):
                sid = key.get("site_id", "default")
                if (sid or "default") == old_site_id:
                    key["site_id"] = new_site_id
                    changed = True
                    updated += 1
            elif (sid or "default") == old_site_id:
                key.site_id = new_site_id
                changed = True
                updated += 1
        if changed:
            save_user(user)
    return updated


def revoke_agent_keys_for_site(site_id: str) -> int:
    """Remove all agent keys bound to site_id. Returns keys revoked."""
    revoked = 0
    for user in iter_users():
        before = len(user.auth.agent_keys)
        kept = []
        for key in user.auth.agent_keys:
            sid = getattr(key, "site_id", None)
            if sid is None and isinstance(key, dict):
                sid = key.get("site_id")
            if (sid or "default") == site_id:
                revoked += 1
            else:
                kept.append(key)
        if len(kept) != before:
            user.auth.agent_keys = kept
            save_user(user)
    return revoked


def _require_user(user_uuid: str) -> User:
    user = get_user_by_uuid(user_uuid)
    if user is None:
        raise KeyError(user_uuid)
    return user


def _assert_not_bootstrap(user: User) -> None:
    if user.public.is_bootstrap:
        raise PermissionError("cannot_modify_bootstrap")


def normalize_username(username: str) -> str:
    name = (username or "").strip()
    if not name or " " in name:
        raise ValueError("Username must not contain spaces.")
    return name


def validate_role(role: str) -> str:
    r = (role or "").strip()
    if r not in ALLOWED_ROLES:
        raise ValueError("role must be admin or author")
    return r


def validate_capabilities(caps: Optional[List[str]]) -> List[str]:
    from services.authz import ALLOWED_AGENT_SCOPES, ordered_caps

    cleaned = [c for c in (caps or []) if c]
    unknown = set(cleaned) - set(ALLOWED_AGENT_SCOPES)
    if unknown:
        raise ValueError(f"Invalid capabilities: {sorted(unknown)}")
    return ordered_caps(cleaned)


def _coerce_memberships(memberships: Optional[List[Any]]) -> List[SiteMembership]:
    from services.site_service import ensure_sites_initialized, get_site, validate_site_id

    ensure_sites_initialized()
    out: List[SiteMembership] = []
    seen: set = set()
    for item in memberships or []:
        if isinstance(item, SiteMembership):
            site_id = item.site_id
            caps = list(item.capabilities or [])
        elif isinstance(item, dict):
            site_id = item.get("site_id")
            caps = list(item.get("capabilities") or [])
        else:
            raise ValueError("Invalid membership")
        try:
            site_id = validate_site_id(site_id)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        if get_site(site_id) is None:
            raise ValueError(f"Unknown site_id: {site_id}")
        if site_id in seen:
            continue
        seen.add(site_id)
        caps = validate_capabilities(caps)
        if not caps:
            continue
        out.append(SiteMembership(site_id=site_id, capabilities=caps))
    return out


def user_admin_view(user: User) -> Dict[str, Any]:
    """Public profile plus stored (unexpanded) memberships. No secrets."""
    body = user.public.model_dump()
    body["memberships"] = [
        {
            "site_id": m.site_id,
            "capabilities": list(m.capabilities or []),
        }
        for m in (user.auth.memberships or [])
    ]
    body["must_change_password"] = bool(
        getattr(user.auth, "must_change_password", False)
    )
    return body


def get_user_sites(user_uuid: str) -> List[str]:
    user = _require_user(user_uuid)
    return [m.site_id for m in (user.auth.memberships or []) if m.site_id]


def create_user(
    *,
    username: str,
    password: str,
    display_name: Optional[str] = None,
    role: str = "author",
    memberships: Optional[List[Any]] = None,
    bio: Optional[str] = None,
    avatar: Optional[str] = None,
    website: Optional[str] = None,
) -> User:
    from services.auth_service import get_password_hash

    username = normalize_username(username)
    if get_user_by_username(username) is not None:
        raise ValueError("Username already exists")
    if not (password or "").strip():
        raise ValueError("password is required")
    role = validate_role(role)
    new_uuid = str(uuid.uuid4())
    user = User(
        public=UserPublic(
            uuid=new_uuid,
            username=username,
            display_name=(display_name or username).strip() or username,
            role=role,
            status="active",
            is_bootstrap=False,
            bio=bio,
            avatar=avatar,
            website=website,
            created_at=utc_now_stamp(),
        ),
        auth=UserAuth(
            password_hash=get_password_hash(password),
            agent_keys=[],
            memberships=_coerce_memberships(memberships),
            must_change_password=True,
        ),
        vault=None,
    )
    if not save_user(user):
        raise RuntimeError("Failed to save user")
    return user


def set_membership(
    user_uuid: str,
    site_id: str,
    capabilities: List[str],
    *,
    actor_uuid: str,
) -> User:
    from services.site_service import ensure_sites_initialized, get_site, validate_site_id

    user = _require_user(user_uuid)
    ensure_sites_initialized()
    try:
        site_id = validate_site_id(site_id)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    if get_site(site_id) is None:
        raise ValueError(f"Unknown site_id: {site_id}")
    caps = validate_capabilities(list(capabilities or []))
    if user.public.uuid == actor_uuid and INSTALL_WIDE_CAPS.intersection(caps):
        raise PermissionError("cannot_modify_self")

    memberships = list(user.auth.memberships or [])
    if not caps:
        user.auth.memberships = [m for m in memberships if m.site_id != site_id]
    else:
        found = False
        for membership in memberships:
            if membership.site_id == site_id:
                membership.capabilities = caps
                found = True
                break
        if not found:
            memberships.append(SiteMembership(site_id=site_id, capabilities=caps))
        user.auth.memberships = memberships
    if not save_user(user):
        raise RuntimeError("Failed to save user")
    return user


def suspend_user(user_uuid: str, *, actor_uuid: str) -> User:
    user = _require_user(user_uuid)
    _assert_not_bootstrap(user)
    if user.public.uuid == actor_uuid:
        raise PermissionError("cannot_modify_self")
    user.public.status = "blocked"
    if not save_user(user):
        raise RuntimeError("Failed to save user")
    return user


def activate_user(user_uuid: str) -> User:
    user = _require_user(user_uuid)
    user.public.status = "active"
    if not save_user(user):
        raise RuntimeError("Failed to save user")
    return user


def delete_user(user_uuid: str, *, actor_uuid: str) -> None:
    user = _require_user(user_uuid)
    _assert_not_bootstrap(user)
    if user.public.uuid == actor_uuid:
        raise PermissionError("cannot_delete_self")
    filepath = USERS_DIR / f"{user.public.uuid}.yaml"
    try:
        filepath.unlink()
    except FileNotFoundError as exc:
        raise KeyError(user_uuid) from exc


def reset_user_password(user_uuid: str, password: str) -> User:
    from services.auth_service import get_password_hash

    user = _require_user(user_uuid)
    if not (password or "").strip():
        raise ValueError("password is required")
    user.auth.password_hash = get_password_hash(password)
    user.auth.must_change_password = True
    if not save_user(user):
        raise RuntimeError("Failed to save user")
    return user


def patch_user(
    user_uuid: str,
    *,
    actor_uuid: str,
    username: Optional[str] = None,
    display_name: Optional[str] = None,
    bio: Optional[str] = None,
    avatar: Optional[str] = None,
    website: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    is_bootstrap: Optional[bool] = None,
) -> User:
    user = _require_user(user_uuid)
    is_self = user.public.uuid == actor_uuid

    if is_bootstrap is not None and is_bootstrap != user.public.is_bootstrap:
        if user.public.is_bootstrap or is_self:
            raise PermissionError(
                "cannot_modify_bootstrap" if user.public.is_bootstrap else "cannot_modify_self"
            )
        raise PermissionError("cannot_modify_bootstrap")

    if role is not None:
        new_role = validate_role(role)
        if new_role != user.public.role:
            if user.public.is_bootstrap:
                raise PermissionError("cannot_modify_bootstrap")
            if is_self:
                raise PermissionError("cannot_modify_self")
            user.public.role = new_role

    if status is not None:
        if status not in ("active", "blocked"):
            raise ValueError("status must be active or blocked")
        if status != user.public.status:
            if user.public.is_bootstrap and status == "blocked":
                raise PermissionError("cannot_modify_bootstrap")
            if is_self and status == "blocked":
                raise PermissionError("cannot_modify_self")
            user.public.status = status

    if username is not None:
        new_name = normalize_username(username)
        existing = get_user_by_username(new_name)
        if existing is not None and existing.public.uuid != user.public.uuid:
            raise ValueError("Username already exists")
        user.public.username = new_name

    if display_name is not None:
        user.public.display_name = display_name
    if bio is not None:
        user.public.bio = bio
    if avatar is not None:
        user.public.avatar = avatar
    if website is not None:
        user.public.website = website

    if not save_user(user):
        raise RuntimeError("Failed to save user")
    return user


def touch_last_login(user: User) -> None:
    user.public.last_login_at = utc_now_stamp()
    save_user(user)
