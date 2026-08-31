"""REST supervision and telemetry endpoints for exact-language siblings."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from routers.sites import _preflight_language_slug_collisions
from routers.v1 import resolve_v1_site_id, verify_api_key
from services.ai_settings_service import load_ai_settings, save_ai_settings
from services.i18n_run_service import list_runs, start_run, update_run
from services.i18n_service import ContentI18nError, normalize_language_config
from services.localization_policy_service import (
    POLICY_KEY,
    normalize_localization_policy,
)
from services.site_service import get_site, update_site
from services.translation_service import (
    TranslationAuthorizationError,
    actor_context_from_state,
    TranslationConflictError,
    TranslationNotFoundError,
    require_active_config,
    page_payload,
    plan_translation_run,
    review_translation_sibling,
    translation_config,
    translation_coverage,
)
from services.ui_strings_service import (
    replace_ui_string_overrides,
    resolve_ui_strings,
)


router = APIRouter(prefix="/v1/translations", tags=["translations"])


class LocalizationTargetPolicyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: str
    model: str
    agent_key_id: str
    review_policy: str = "require_review"


class LocalizationPolicyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    targets: dict[str, LocalizationTargetPolicyBody] = Field(default_factory=dict)


class TranslationConfigBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: str
    languages: list[str]
    language_labels: dict[str, str] = Field(default_factory=dict)
    translation_automation_paused: bool = False
    automation_policy: Optional[LocalizationPolicyBody] = None


class ReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str
    note: Optional[str] = Field(default=None, max_length=500)


class UiStringOverridesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overrides: dict[str, str]


class RunStartBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    target_languages: list[str] = Field(default_factory=list)


class RunUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Optional[str] = None
    counts: Optional[dict[str, int]] = None
    error: Optional[str] = Field(default=None, max_length=500)


def _raise_translation_error(exc: Exception) -> None:
    if isinstance(exc, TranslationNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, TranslationConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, TranslationAuthorizationError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, ContentI18nError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail=f"Translation run not found: {exc.args[0]}") from exc
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


def _require_agent_scope(actor, scope: str) -> None:
    if actor.is_agent and scope not in actor.scopes:
        raise HTTPException(
            status_code=403, detail=f"Agent key lacks required scope: {scope}"
        )


@router.get("/config")
async def get_translation_config(
    request: Request,
    username: str = Depends(verify_api_key),
    site_id: str = Depends(resolve_v1_site_id),
):
    _require_agent_scope(actor_context_from_state(request, site_id), "read")
    return translation_config(site_id)


@router.put("/config")
async def put_translation_config(
    body: TranslationConfigBody,
    request: Request,
    username: str = Depends(verify_api_key),
    site_id: str = Depends(resolve_v1_site_id),
):
    actor = actor_context_from_state(request, site_id)
    if actor.is_agent:
        raise HTTPException(status_code=403, detail="Human admin required")
    current = get_site(site_id)
    if current is None:
        raise HTTPException(status_code=404, detail=f"Unknown site_id: {site_id}")
    try:
        normalized = normalize_language_config(
            language=body.language,
            languages=body.languages,
            language_labels=body.language_labels,
            translation_automation_paused=body.translation_automation_paused,
        )
        await _preflight_language_slug_collisions(
            site_id,
            language=normalized.language,
            languages=normalized.languages,
        )
        current_ai_settings = load_ai_settings(site_id)
        requested_policy = (
            body.automation_policy.model_dump()
            if body.automation_policy is not None
            else current_ai_settings.get(POLICY_KEY)
        )
        normalized_policy = normalize_localization_policy(
            site_id,
            requested_policy,
            default_language=normalized.language,
            configured_languages=normalized.languages,
            validate_bindings=True,
        )
        update_site(
            site_id,
            language=normalized.language,
            languages=normalized.languages,
            language_labels=normalized.language_labels,
            translation_automation_paused=normalized.translation_automation_paused,
        )
        save_ai_settings(
            site_id,
            {**current_ai_settings, POLICY_KEY: normalized_policy},
        )
        return translation_config(site_id)
    except Exception as exc:
        _raise_translation_error(exc)


@router.get("/coverage")
async def get_translation_coverage(
    request: Request,
    language: Optional[str] = Query(default=None),
    username: str = Depends(verify_api_key),
    site_id: str = Depends(resolve_v1_site_id),
):
    try:
        _require_agent_scope(actor_context_from_state(request, site_id), "read")
        return await translation_coverage(site_id, language=language)
    except Exception as exc:
        _raise_translation_error(exc)


@router.get("/strings")
async def get_translation_strings(
    request: Request,
    language: Optional[str] = Query(default=None),
    username: str = Depends(verify_api_key),
    site_id: str = Depends(resolve_v1_site_id),
):
    try:
        _require_agent_scope(actor_context_from_state(request, site_id), "read")
        return await resolve_ui_strings(site_id, language)
    except Exception as exc:
        _raise_translation_error(exc)


@router.put("/strings")
async def put_translation_strings(
    body: UiStringOverridesBody,
    request: Request,
    language: str = Query(...),
    username: str = Depends(verify_api_key),
    site_id: str = Depends(resolve_v1_site_id),
):
    actor = actor_context_from_state(request, site_id)
    if actor.is_agent:
        raise HTTPException(status_code=403, detail="Human admin required")
    try:
        return await replace_ui_string_overrides(
            site_id,
            language,
            body.overrides,
        )
    except Exception as exc:
        _raise_translation_error(exc)


@router.post("/{slug}/{language}/review")
async def review_translation(
    slug: str,
    language: str,
    body: ReviewBody,
    request: Request,
    username: str = Depends(verify_api_key),
    site_id: str = Depends(resolve_v1_site_id),
):
    try:
        page = await review_translation_sibling(
            slug=slug,
            language=language,
            actor=actor_context_from_state(request, site_id),
            decision=body.decision,
            note=body.note,
        )
        return {"message": f"Translation {body.decision} recorded", "entry": page_payload(page)}
    except Exception as exc:
        _raise_translation_error(exc)


@router.get("/runs")
async def get_translation_runs(
    request: Request,
    limit: int = Query(default=25, ge=1, le=100),
    username: str = Depends(verify_api_key),
    site_id: str = Depends(resolve_v1_site_id),
):
    _require_agent_scope(actor_context_from_state(request, site_id), "read")
    return {"runs": list_runs(site_id, limit=limit)}


@router.post("/runs", status_code=status.HTTP_201_CREATED)
async def start_translation_run(
    body: RunStartBody,
    request: Request,
    username: str = Depends(verify_api_key),
    site_id: str = Depends(resolve_v1_site_id),
):
    actor = actor_context_from_state(request, site_id)
    try:
        config = require_active_config(site_id)
        effective_config = translation_config(site_id)
        policy_targets = list(
            effective_config.get("automation_policy", {}).get("targets", {})
        )
        targets = body.target_languages or (
            policy_targets
            if actor.is_agent
            and effective_config.get("automation_policy", {}).get("enabled")
            else [code for code in config.languages if code != config.language]
        )
        policy_snapshot = plan_translation_run(
            actor=actor,
            mode=body.mode,
            target_languages=targets,
        )
        return start_run(
            site_id=site_id,
            actor=actor.kind,
            actor_id=actor.actor_id,
            mode=body.mode,
            target_languages=targets,
            policy_snapshot=policy_snapshot,
        )
    except Exception as exc:
        _raise_translation_error(exc)


@router.patch("/runs/{run_id}")
async def patch_translation_run(
    run_id: str,
    body: RunUpdateBody,
    request: Request,
    username: str = Depends(verify_api_key),
    site_id: str = Depends(resolve_v1_site_id),
):
    actor = actor_context_from_state(request, site_id)
    try:
        if actor.is_agent and "write" not in actor.scopes:
            raise TranslationAuthorizationError(
                "Agent key lacks required scope: write"
            )
        return update_run(
            site_id=site_id,
            run_id=run_id,
            actor=actor.kind,
            actor_id=actor.actor_id,
            status=body.status,
            counts=body.counts,
            error=body.error,
        )
    except Exception as exc:
        _raise_translation_error(exc)
