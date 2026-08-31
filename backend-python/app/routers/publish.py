"""Publish-to-host API — config, probe, Deploy Grants, full deploy, and export zip.

V1 surface: GET/PUT ``/api/publish/target``, GET ``/api/publish/providers``,
POST ``/api/publish/test``, POST ``/api/publish/run``, GET ``/api/publish/status``,
GET/POST/DELETE ``/api/publish/grant``, POST ``/api/publish/export-zip``.

Interactive: ZK vault (``X-Vault-Publish-Pass``) or install Ed25519 key.
Agentic: scope ``publish`` + enrolled Deploy Grant (server ciphertext).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from models.user import UserPublic
from routers.auth import get_current_user
from services.authz import assert_capability, require_capability
from services import publish_grants
from services.publish_deploy import (
    ExportBusyError,
    PublishBusyError,
    begin_run,
    export_site_zip,
    get_run_status,
    run_publish,
)
from services.publish_providers import (
    PublishDeployError,
    get_provider,
    list_providers,
)
from services.publish_providers.registry import (
    ProviderNotEnabledError,
    UnknownPublishProviderError,
)
from services.site_service import (
    PUBLISH_SECRET_KEYS,
    get_publish_target,
    set_publish_target,
)
from services.storage_provider import vault_secrets

router = APIRouter(prefix="/publish", tags=["publish"])


class PublishTargetPutBody(BaseModel):
    """Save host/user/path/auth/public_url for a site. Never includes passwords."""

    # Allow extras so registered Pro yaml_fields and secret-key rejection work.
    model_config = ConfigDict(extra="allow")

    site: str = Field(..., description="Target site id")
    provider: Optional[str] = "sftp"
    host: Optional[str] = None
    port: Optional[int] = 22
    username: Optional[str] = None
    remote_path: Optional[str] = None
    auth_method: Optional[str] = "password"
    public_url: Optional[str] = None
    last_published_at: Optional[str] = None
    last_status: Optional[str] = None
    agent_publish: Optional[str] = None
    github_owner: Optional[str] = None
    github_repo: Optional[str] = None
    github_pages_branch: Optional[str] = None
    github_pages_cname: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None


class PublishTestBody(BaseModel):
    """Probe the saved publish target. Password is ephemeral (never persisted)."""

    site: str = Field(..., description="Target site id")
    password: Optional[str] = Field(
        None,
        description="One-shot password for curl smoke; prefer vault header",
    )


class PublishRunBody(BaseModel):
    """Start a full build + SFTP upload for a site."""

    site: str = Field(..., description="Target site id")
    password: Optional[str] = Field(
        None,
        description="One-shot password for curl smoke; prefer vault header (humans only)",
    )
    force_full: bool = Field(
        False,
        description="Skip incremental diff; full-tree scp then orphan deletes",
    )


class PublishGrantEnrollBody(BaseModel):
    """Enroll a Deploy Grant. Password optional when vault header is set."""

    site: str = Field(..., description="Target site id")
    password: Optional[str] = Field(
        None,
        description="SFTP password to copy into grant store (or use vault header)",
    )


class PublishExportZipBody(BaseModel):
    """Build the active site and return a downloadable static zip."""

    site: str = Field(..., description="Site id to build and zip")


def _reject_secret_keys(raw: Dict[str, Any]) -> None:
    hits = [
        k
        for k in raw
        if str(k).lower() in PUBLISH_SECRET_KEYS or str(k).lower() == "password"
    ]
    if hits:
        raise HTTPException(
            status_code=400,
            detail=(
                "Publish passwords must not be sent to this endpoint; "
                f"remove: {', '.join(sorted(hits))}"
            ),
        )


def _publish_secret_key(
    site_id: str,
    *,
    auth_method: str = "password",
    provider: Optional[str] = None,
) -> str:
    """Vault key for the active provider (SFTP password or platform token)."""
    try:
        inst = get_provider(provider)
        key = inst.vault_key(site_id)
        if key:
            return key
    except (UnknownPublishProviderError, ProviderNotEnabledError):
        pass
    return f"PUBLISH_SFTP_PASS:{site_id}"


def _peek_token_payload(request: Request) -> Dict[str, Any]:
    """Decode JWT without aud check (human + agent). Raises 401 if missing/invalid."""
    from services.auth_service import decode_access_token
    import jwt as pyjwt

    token = None
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
    if not token:
        token = request.cookies.get("pen_jwt")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return decode_access_token(token)
    except pyjwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token") from e


def _is_agent(payload: Dict[str, Any]) -> bool:
    return payload.get("type") == "agent"


def _require_human(request: Request) -> Dict[str, Any]:
    """Operator-only actions (Deploy Grant, export zip) reject agent JWTs."""
    payload = _peek_token_payload(request)
    if _is_agent(payload):
        raise HTTPException(
            status_code=403,
            detail="This action requires a human admin session",
        )
    return payload


def _agent_site_and_scopes(payload: Dict[str, Any]) -> Tuple[str, list]:
    scopes = payload.get("scopes") or []
    if not isinstance(scopes, list):
        scopes = list(scopes) if scopes else []
    site_id = payload.get("site_id")
    if not site_id:
        raise HTTPException(status_code=403, detail="Agent token missing site_id claim")
    return str(site_id), scopes


@router.get("/providers")
async def get_providers(
    current_user: UserPublic = Depends(get_current_user),
    _: UserPublic = Depends(require_capability("publish")),
) -> Dict[str, List[Dict[str, Any]]]:
    """List publish provider catalog (enabled + coming-soon stubs)."""
    return {"providers": list_providers()}


@router.get("/target")
async def get_target(
    request: Request,
    site: str = Query(..., description="Site id"),
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Read the non-secret publish target for a site."""
    assert_capability(request, "publish", site_id=site)
    try:
        return get_publish_target(site)
    except ValueError as e:
        detail = str(e)
        if detail.startswith("Unknown site_id"):
            raise HTTPException(status_code=404, detail=detail) from e
        raise HTTPException(status_code=400, detail=detail) from e


@router.put("/target")
async def put_target(
    body: PublishTargetPutBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Save the non-secret publish target for a site.

    Passwords must never be sent here — they belong in the ZK vault.
    Unknown ``provider`` strings are rejected (400).
    """
    assert_capability(request, "publish", site_id=body.site)
    extras = getattr(body, "__pydantic_extra__", None) or {}
    _reject_secret_keys(extras)
    payload = body.model_dump(exclude_unset=True)
    site = payload.pop("site", None)
    if not site:
        raise HTTPException(status_code=400, detail="site is required")
    try:
        return set_publish_target(site, payload)
    except ValueError as e:
        detail = str(e)
        if detail.startswith("Unknown site_id"):
            raise HTTPException(status_code=404, detail=detail) from e
        raise HTTPException(status_code=400, detail=detail) from e


@router.get("/grant")
async def get_grant(
    request: Request,
    site: str = Query(..., description="Site id"),
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Non-secret Deploy Grant status (never returns host passwords)."""
    _require_human(request)
    assert_capability(request, "publish", site_id=site)
    try:
        return publish_grants.grant_status(site)
    except ValueError as e:
        detail = str(e)
        if detail.startswith("Unknown site_id"):
            raise HTTPException(status_code=404, detail=detail) from e
        raise HTTPException(status_code=400, detail=detail) from e


@router.post("/grant")
async def enroll_grant(
    body: PublishGrantEnrollBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Enroll a Deploy Grant so agents with scope ``publish`` can deploy.

    Password path: copies password from body or ``X-Vault-Publish-Pass`` into
    server-side ciphertext (leaves ZK for that secret). Key path: flag-only.
    """
    _require_human(request)
    assert_capability(request, "publish", site_id=body.site)
    try:
        target = get_publish_target(body.site)
    except ValueError as e:
        detail = str(e)
        if detail.startswith("Unknown site_id"):
            raise HTTPException(status_code=404, detail=detail) from e
        raise HTTPException(status_code=400, detail=detail) from e

    site_id = target["site_id"]
    _require_configured_target(target)
    auth_method = (target.get("auth_method") or "password").strip().lower()
    provider_id = (target.get("provider") or "sftp").strip().lower() or "sftp"

    password: Optional[str] = None
    if auth_method in ("password", "token"):
        password = (body.password or "").strip() or None
        if not password:
            password = (
                vault_secrets.get().get(
                    _publish_secret_key(
                        site_id, auth_method=auth_method, provider=provider_id
                    )
                )
                or None
            )

    try:
        return publish_grants.enroll(
            site_id, auth_method=auth_method, password=password
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/grant")
async def revoke_grant(
    request: Request,
    site: str = Query(..., description="Site id"),
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Revoke Deploy Grant (independent of agent key revoke)."""
    _require_human(request)
    assert_capability(request, "publish", site_id=site)
    try:
        return publish_grants.revoke(site)
    except ValueError as e:
        detail = str(e)
        if detail.startswith("Unknown site_id"):
            raise HTTPException(status_code=404, detail=detail) from e
        raise HTTPException(status_code=400, detail=detail) from e


def _resolve_provider_or_http(target: Dict[str, Any]):
    """Instantiate the adapter for target.provider; 400 if unknown/disabled."""
    try:
        return get_provider(target.get("provider") or "sftp")
    except (UnknownPublishProviderError, ProviderNotEnabledError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/test")
async def test_publish_connection(
    body: PublishTestBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Probe the site's saved publish target via its provider adapter.

    SFTP password auth: password from request body or ``PUBLISH_SFTP_PASS:{site}``
    (via ``X-Vault-Publish-Pass``). Key auth: install Ed25519 (BatchMode), no
    vault publish password. GitHub Pages: ``PUBLISH_GITHUB_TOKEN:{site}`` via
    ``X-Vault-Publish-Github-Token``. Other adapters resolve their vault key
    from the registered provider. Never written to ``sites.yaml`` or GET
    ``/target``.
    """
    assert_capability(request, "publish", site_id=body.site)
    try:
        target = get_publish_target(body.site)
    except ValueError as e:
        detail = str(e)
        if detail.startswith("Unknown site_id"):
            raise HTTPException(status_code=404, detail=detail) from e
        raise HTTPException(status_code=400, detail=detail) from e

    site_id = target["site_id"]
    _require_configured_target(target)

    auth_method = (target.get("auth_method") or "password").strip().lower()
    if auth_method not in ("password", "key", "token"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported publish auth_method: {auth_method}",
        )

    provider_id = (target.get("provider") or "sftp").strip().lower() or "sftp"
    password: Optional[str] = None
    if auth_method in ("password", "token"):
        password = _resolve_publish_secret(
            site_id, body.password, auth_method, provider=provider_id
        )

    provider = _resolve_provider_or_http(target)
    provider.configure(target, password=password, site_id=site_id)
    return await provider.test()


def _load_target_or_http(site: str) -> Dict[str, Any]:
    try:
        return get_publish_target(site)
    except ValueError as e:
        detail = str(e)
        if detail.startswith("Unknown site_id"):
            raise HTTPException(status_code=404, detail=detail) from e
        raise HTTPException(status_code=400, detail=detail) from e


def _require_configured_target(target: Dict[str, Any]) -> None:
    if not target.get("configured"):
        raise HTTPException(
            status_code=400,
            detail="Publish target is not configured for this site; save Settings first",
        )


def _resolve_publish_secret(
    site_id: str,
    body_password: Optional[str],
    auth_method: str,
    *,
    provider: Optional[str] = None,
) -> str:
    secret_key = _publish_secret_key(
        site_id, auth_method=auth_method, provider=provider
    )
    password = (body_password or "").strip() or None
    if not password:
        password = vault_secrets.get().get(secret_key) or None
    if not password:
        try:
            inst = get_provider(provider)
            detail = inst.missing_secret_detail(site_id)
        except (UnknownPublishProviderError, ProviderNotEnabledError):
            detail = (
                "Publish SFTP password missing: unlock the vault and set "
                f"{secret_key}, send X-Vault-Publish-Pass, or pass password "
                "in the body for smoke"
            )
        raise HTTPException(status_code=400, detail=detail)
    return password


def start_publish_run(
    site_id: str,
    background_tasks: BackgroundTasks,
    *,
    is_agent: bool,
    body_password: Optional[str] = None,
    agent_site_id: Optional[str] = None,
    agent_scopes: Optional[list] = None,
    force_full: bool = False,
) -> Dict[str, Any]:
    """Shared deploy start for REST ``/run`` and MCP ``publish_site``.

    Agents: require scope ``publish``, matching site, enrolled grant; secrets
    from grant store only. Humans: vault/body password/token or install key.
    """
    target = _load_target_or_http(site_id)
    resolved_site = target["site_id"]
    _require_configured_target(target)

    if is_agent:
        scopes = agent_scopes or []
        if "publish" not in scopes:
            raise HTTPException(
                status_code=403,
                detail="Agent key lacks required scope: publish",
            )
        if not agent_site_id or str(agent_site_id) != resolved_site:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Agent token site_id '{agent_site_id}' does not match "
                    f"publish site '{resolved_site}'"
                ),
            )
        if target.get("agent_publish") != "enrolled":
            raise HTTPException(
                status_code=403,
                detail=(
                    "Deploy Grant not enrolled for this site; "
                    "enroll under Publish → Settings"
                ),
            )

    auth_method = (target.get("auth_method") or "password").strip().lower()
    if auth_method not in ("password", "key", "token"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported publish auth_method: {auth_method}",
        )

    # Fail fast if provider is unknown / not yet implemented.
    _resolve_provider_or_http(target)
    provider_id = (target.get("provider") or "sftp").strip().lower() or "sftp"

    vault_snap = dict(vault_secrets.get() or {})
    password: Optional[str] = None

    if auth_method in ("password", "token"):
        if is_agent:
            try:
                password = publish_grants.load_password(resolved_site)
            except ValueError as e:
                raise HTTPException(status_code=403, detail=str(e)) from e
            if not password:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Deploy Grant enrolled but secret ciphertext missing; "
                        "re-enroll the grant"
                    ),
                )
        else:
            password = _resolve_publish_secret(
                resolved_site,
                body_password,
                auth_method,
                provider=provider_id,
            )
        vault_snap[
            _publish_secret_key(
                resolved_site, auth_method=auth_method, provider=provider_id
            )
        ] = password

    try:
        run = begin_run(resolved_site)
    except PublishBusyError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Publish already running for this site (task {e.task_id})",
        ) from e

    background_tasks.add_task(
        run_publish,
        resolved_site,
        vault_snap,
        password=password,
        force_full=bool(force_full),
    )
    return {
        "task_id": run["task_id"],
        "site_id": resolved_site,
        "status": "running",
    }


@router.post("/run")
async def publish_run(
    body: PublishRunBody,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Build the site and batch-upload ``dist/`` to the configured SFTP host.

    Humans: password from body or ``X-Vault-Publish-Pass``; key auth uses install
    Ed25519. Agents: scope ``publish`` + enrolled Deploy Grant (secrets from
    grant store, not vault). Poll ``GET /api/publish/status?site=``.
    """
    assert_capability(request, "publish", site_id=body.site)
    payload = _peek_token_payload(request)
    is_agent = _is_agent(payload)
    agent_site_id = None
    agent_scopes = None
    if is_agent:
        agent_site_id, agent_scopes = _agent_site_and_scopes(payload)

    return start_publish_run(
        body.site,
        background_tasks,
        is_agent=is_agent,
        body_password=None if is_agent else body.password,
        agent_site_id=agent_site_id,
        agent_scopes=agent_scopes,
        force_full=bool(body.force_full),
    )


@router.get("/status")
async def publish_status(
    request: Request,
    site: str = Query(..., description="Site id"),
    task_id: Optional[str] = Query(None, description="Optional task id from POST /run"),
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Poll the latest (or specific) publish run for a site."""
    assert_capability(request, "publish", site_id=site)
    target = _load_target_or_http(site)
    site_id = target["site_id"]
    run = get_run_status(site_id, task_id=task_id)
    if run is None:
        if task_id:
            raise HTTPException(status_code=404, detail="Task not found")
        return {
            "site_id": site_id,
            "status": "idle",
            "phase": None,
            "task_id": None,
            "started_at": None,
            "finished_at": None,
            "error": None,
            "log": [],
            "last_published_at": target.get("last_published_at"),
            "last_status": target.get("last_status"),
        }
    return {
        **run,
        "last_published_at": target.get("last_published_at"),
        "last_status": target.get("last_status"),
    }


@router.post("/export-zip")
async def publish_export_zip(
    body: PublishExportZipBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Response:
    """Build the site's static ``dist/`` and return a zip download.

    Human admin only (browser Export tab). Does not require a publish host.
    Failed builds return JSON errors — never an empty/partial zip as success.
    Autostart = browser download begins after a successful build (no offline
    preview helper is included in the archive).
    """
    _require_human(request)
    assert_capability(request, "publish", site_id=body.site)
    # Validate site exists (configured host not required).
    target = _load_target_or_http(body.site)
    site_id = target["site_id"]
    vault_snap = dict(vault_secrets.get() or {})

    try:
        data, filename = await export_site_zip(site_id, vault_snap)
    except PublishBusyError as e:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Publish already running for this site (task {e.task_id}); "
                "wait for it to finish before exporting"
            ),
        ) from e
    except ExportBusyError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Export already running for site '{e.site_id}'",
        ) from e
    except PublishDeployError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        detail = str(e)
        if detail.startswith("Unknown site_id"):
            raise HTTPException(status_code=404, detail=detail) from e
        raise HTTPException(status_code=400, detail=detail) from e

    # RFC 5987 filename* for non-ASCII safety; ASCII filename= for broad clients.
    disposition = (
        f'attachment; filename="{filename}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": disposition,
            "Content-Length": str(len(data)),
            "Cache-Control": "no-store",
        },
    )
