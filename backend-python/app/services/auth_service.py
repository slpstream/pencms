import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
import os
from typing import Optional

# We should ideally have this in config, but we can generate one for now if missing.
JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days (human session cookies)

# MCP / agent token hygiene (Phase 0). Production should set absolute URLs.
JWT_ISSUER = os.environ.get("JWT_ISSUER", "http://localhost").rstrip("/")
MCP_RESOURCE_URL = os.environ.get(
    "MCP_RESOURCE_URL", f"{JWT_ISSUER}/api/mcp"
).rstrip("/")
AGENT_TOKEN_EXPIRE_MINUTES = int(os.environ.get("AGENT_TOKEN_EXPIRE_MINUTES", "15"))

PRM_PATH = "/.well-known/oauth-protected-resource"
PRM_PATH_QUALIFIED = "/.well-known/oauth-protected-resource/api/mcp"


def prm_metadata_url() -> str:
    """Absolute URL for Protected Resource Metadata (RFC 9728)."""
    return f"{JWT_ISSUER}{PRM_PATH}"


def bearer_www_authenticate(*, scope: str = "read", error: Optional[str] = None) -> str:
    """Build a WWW-Authenticate Bearer challenge for MCP discovery / step-up."""
    parts = [f'resource_metadata="{prm_metadata_url()}"']
    if error:
        parts.append(f'error="{error}"')
    parts.append(f'scope="{scope}"')
    return "Bearer " + ", ".join(parts)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ValueError:
        return False

def get_password_hash(password: str) -> str:
    """Returns a bcrypt hash of the password."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_access_token(
    data: dict,
    expires_delta: timedelta = None,
    *,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
) -> str:
    """Creates a signed JWT access token.

    Human login omits issuer/audience. Agent / MCP tokens pass both.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    if issuer is not None:
        to_encode["iss"] = issuer
    if audience is not None:
        to_encode["aud"] = audience
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_agent_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Mint a short-lived agent JWT bound to JWT_ISSUER and MCP_RESOURCE_URL."""
    if expires_delta is None:
        expires_delta = timedelta(minutes=AGENT_TOKEN_EXPIRE_MINUTES)
    return create_access_token(
        data,
        expires_delta=expires_delta,
        issuer=JWT_ISSUER,
        audience=MCP_RESOURCE_URL,
    )


def decode_access_token(
    token: str,
    *,
    audience: Optional[str] = None,
    issuer: Optional[str] = None,
) -> dict:
    """Decodes and verifies a JWT access token. Raises jwt.PyJWTError if invalid.

    Pass audience/issuer only when validating agent/MCP tokens. Human session
    tokens must be decoded without audience checks.
    """
    options = {}
    kwargs = {
        "algorithms": [JWT_ALGORITHM],
    }
    if audience is not None:
        kwargs["audience"] = audience
    else:
        options["verify_aud"] = False
    if issuer is not None:
        kwargs["issuer"] = issuer
    if options:
        kwargs["options"] = options
    return jwt.decode(token, JWT_SECRET, **kwargs)


def decode_agent_token(token: str) -> dict:
    """Decode an agent token, enforcing iss and aud against configured URLs."""
    return decode_access_token(
        token,
        audience=MCP_RESOURCE_URL,
        issuer=JWT_ISSUER,
    )
