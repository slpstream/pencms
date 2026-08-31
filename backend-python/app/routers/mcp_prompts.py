"""MCP tools for site AI persona, generation prompts, and quality checklists."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from models.user import UserPublic
from routers.auth import get_current_user
from routers.mcp_tools import DEFAULT_QUALITY_CHECKLIST, require_scope, resolve_mcp_site_id
from services.ai_settings_service import agent_house_facts, load_ai_settings, save_ai_settings
from services.extract_prompts import extractive_prompts_payload

router = APIRouter(prefix="/api/v1", tags=["mcp"])


class UpdateSitePromptsBody(BaseModel):
    """Sparse update payload for site-bound AI prompts."""

    text_generation_prompt: Optional[str] = Field(
        None, description="Text generation / editorial persona prompt. Empty string clears."
    )
    image_generation_prompt: Optional[str] = Field(
        None, description="Image generation guidance / visual style prompt. Empty string clears."
    )
    post_quality_checklist: Optional[str] = Field(
        None, description="Post quality review checklist. Empty string resets to default."
    )


@router.get(
    "/mcp/prompts",
    operation_id="get_site_prompts",
    dependencies=[Depends(require_scope("read"))],
)
async def get_site_prompts(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Read configured AI persona, image guidance, quality checklist, and extractive prompts."""
    site_id = resolve_mcp_site_id(request)
    settings = load_ai_settings(site_id)
    checklist = settings.get("post_quality_checklist", "") or DEFAULT_QUALITY_CHECKLIST
    facts = agent_house_facts(site_id)
    return {
        "text_generation_prompt": settings.get("text_generation_prompt", "") or "",
        "image_generation_prompt": settings.get("image_generation_prompt", "") or "",
        "post_quality_checklist": checklist,
        "extractive_prompts": extractive_prompts_payload(),
        "sitename": facts["sitename"],
        "ai_publish_autonomy": facts["ai_publish_autonomy"],
        "ai_metadata_scope": facts["ai_metadata_scope"],
        "site_id": site_id,
    }


@router.patch(
    "/mcp/prompts",
    operation_id="update_site_prompts",
    dependencies=[Depends(require_scope("write"))],
)
async def update_site_prompts(
    request: Request,
    body: UpdateSitePromptsBody,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Sparse update of AI persona, image guidance, or quality checklist for the bound site.

    Omitted fields are preserved. Empty strings clear the field. Requires scope ``write``.
    """
    site_id = resolve_mcp_site_id(request)
    existing = load_ai_settings(site_id)
    updates: Dict[str, Any] = {}

    if body.text_generation_prompt is not None:
        updates["text_generation_prompt"] = body.text_generation_prompt
    if body.image_generation_prompt is not None:
        updates["image_generation_prompt"] = body.image_generation_prompt
    if body.post_quality_checklist is not None:
        updates["post_quality_checklist"] = body.post_quality_checklist

    if updates:
        merged = {**existing, **updates}
        save_ai_settings(site_id, merged)

    refreshed = load_ai_settings(site_id)
    checklist = refreshed.get("post_quality_checklist", "") or DEFAULT_QUALITY_CHECKLIST
    facts = agent_house_facts(site_id)
    return {
        "text_generation_prompt": refreshed.get("text_generation_prompt", "") or "",
        "image_generation_prompt": refreshed.get("image_generation_prompt", "") or "",
        "post_quality_checklist": checklist,
        "extractive_prompts": extractive_prompts_payload(),
        "sitename": facts["sitename"],
        "ai_publish_autonomy": facts["ai_publish_autonomy"],
        "ai_metadata_scope": facts["ai_metadata_scope"],
        "site_id": site_id,
    }
