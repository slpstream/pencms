"""Admin API for per-site theme style overrides."""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from services.authz import assert_capability
from services.theme_style_service import (
    StyleOverrideError,
    get_style_settings,
    set_style_overrides,
)

router = APIRouter(prefix="/sites", tags=["sites"])


class StyleOverridesBody(BaseModel):
    values: Dict[str, str] = Field(default_factory=dict)
    dark: Dict[str, str] = Field(default_factory=dict)


@router.get("/{site_id}/theme/style")
async def get_site_theme_style(
    site_id: str,
    request: Request,
) -> Any:
    assert_capability(request, "write:theme", site_id=site_id)
    try:
        return get_style_settings(site_id)
    except StyleOverrideError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/{site_id}/theme/style")
async def put_site_theme_style(
    site_id: str,
    body: StyleOverridesBody,
    request: Request,
) -> Any:
    assert_capability(request, "write:theme", site_id=site_id)
    try:
        return set_style_overrides(site_id, body.values, body.dark)
    except StyleOverrideError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
