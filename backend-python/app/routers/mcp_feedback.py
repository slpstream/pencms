"""MCP tools for remote feedback relay sync."""

from fastapi import APIRouter, Depends, Request

from models.user import UserPublic
from routers.auth import get_current_user
from routers.mcp_tools import require_scope, resolve_mcp_site_id
from services.feedback_service import sync_from_relay

router = APIRouter(prefix="/api/v1", tags=["mcp"])


@router.post(
    "/mcp/feedback/sync",
    operation_id="sync_remote_feedback",
    dependencies=[Depends(require_scope("write"))],
)
async def sync_remote_feedback(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> dict:
    """Drain the public feedback relay into fb-* stub pages for this site.

    Requires scope ``write``. Site comes from the agent JWT ``site_id`` (or the
    human active-site preference). Missing relay keys return
    ``written: 0`` / ``no_relay_configured``; a down relay returns
    ``relay_unreachable`` — never HTTP 500.
    """
    site_id = resolve_mcp_site_id(request)
    return await sync_from_relay(site_id)
