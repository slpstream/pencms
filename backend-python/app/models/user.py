from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional, List
import hashlib

class UserPublic(BaseModel):
    uuid: str
    username: str
    display_name: str
    role: str = "author" # admin, author, agent
    status: Literal["active", "blocked"] = "active"
    is_bootstrap: bool = False
    bio: Optional[str] = None
    avatar: Optional[str] = None
    website: Optional[str] = None
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None


class SiteMembership(BaseModel):
    site_id: str
    capabilities: List[str] = Field(default_factory=list)

class AgentKeyMetadata(BaseModel):
    key_id: str
    hash: str
    name: str
    created_at: str
    scopes: List[str] = Field(default_factory=lambda: ["read", "write"])
    site_id: str = "default"

class UserAuth(BaseModel):
    password_hash: str
    agent_keys: List[AgentKeyMetadata] = Field(default_factory=list)
    memberships: List[SiteMembership] = Field(default_factory=list)
    must_change_password: bool = False

    @field_validator('agent_keys', mode='before')
    @classmethod
    def migrate_agent_keys(cls, v):
        if not isinstance(v, list): return v
        new_list = []
        for i, item in enumerate(v):
            if isinstance(item, str):
                new_list.append({
                    "key_id": f"ak_{hashlib.sha256(item.encode('utf-8')).hexdigest()[:24]}",
                    "hash": item,
                    "name": f"Legacy Key {i+1}",
                    "created_at": "2026-05-16",
                    "scopes": ["read", "write"],
                    "site_id": "default",
                })
            elif isinstance(item, dict):
                item = dict(item)
                if not item.get("key_id") and item.get("hash"):
                    item["key_id"] = (
                        "ak_"
                        + hashlib.sha256(
                            str(item["hash"]).encode("utf-8")
                        ).hexdigest()[:24]
                    )
                if "scopes" not in item:
                    item["scopes"] = ["read", "write"]
                if not item.get("site_id"):
                    item["site_id"] = "default"
                new_list.append(item)
            else:
                new_list.append(item)
        return new_list

class User(BaseModel):
    public: UserPublic
    auth: UserAuth
    # The vault is stored separately or as an opaque string
    vault: Optional[str] = None # Encrypted AES-256-GCM blob

class TokenRequest(BaseModel):
    agent_key: str

class VaultUpdateRequest(BaseModel):
    vault: str
