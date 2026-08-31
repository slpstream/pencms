"""Shared exact-language translation operations for REST and MCP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from models.page import Page, PageFrontmatter, PageResponse, utc_now_iso
from services.file_service import (
    content_identity_for_path,
    delete_page,
    get_site_language_config,
    iter_canonical_files,
    list_sibling_records,
    read_page,
    resolve_path,
    translation_peer_summaries,
    write_page,
)
from services.ai_settings_service import load_ai_settings
from services.i18n_run_service import get_run
from services.i18n_service import ContentI18nError, is_live_translation, normalize_requested_language
from services.publish_autonomy import (
    autonomy_for_site,
    clear_review_if_published,
    enforce_publish_autonomy,
)
from services.localization_policy_service import (
    POLICY_KEY,
    effective_localization_policy,
    require_active_agent_key,
    select_run_policy,
)


SERVER_PROVENANCE_FIELDS = {
    "created_by",
    "created_by_id",
    "updated_by",
    "updated_by_id",
    "run_id",
    "needs_review",
    "reviewed_by",
    "reviewed_at",
    "review_decision",
    "review_note",
}


class TranslationNotFoundError(LookupError):
    pass


class TranslationConflictError(RuntimeError):
    pass


class TranslationAuthorizationError(PermissionError):
    pass


@dataclass(frozen=True)
class ActorContext:
    kind: str
    actor_id: str
    site_id: str
    scopes: tuple[str, ...] = ()
    key_id: Optional[str] = None

    @property
    def is_agent(self) -> bool:
        return self.kind == "agent"


def actor_context_from_state(request: Any, site_id: str) -> ActorContext:
    return ActorContext(
        kind=getattr(request.state, "actor_kind", "human"),
        actor_id=str(getattr(request.state, "actor_id", "human")),
        site_id=site_id,
        scopes=tuple(getattr(request.state, "actor_scopes", ())),
        key_id=getattr(request.state, "actor_key_id", None),
    )


def translation_config(site_id: str) -> dict[str, Any]:
    config = get_site_language_config(site_id)
    ai_settings = load_ai_settings(site_id)
    return {
        "language": config.language,
        "languages": config.languages,
        "language_labels": config.language_labels,
        "translation_automation_paused": config.translation_automation_paused,
        "i18n_active": config.active,
        "automation_policy": effective_localization_policy(
            site_id,
            ai_settings.get(POLICY_KEY),
            default_language=config.language,
            configured_languages=config.languages,
        ),
    }


def require_active_config(site_id: str):
    config = get_site_language_config(site_id)
    if not config.active:
        raise ContentI18nError(
            f"Site '{site_id}' i18n is inactive. Fix: configure at least two "
            "unique languages including the default language."
        )
    return config


def require_translation_write(actor: ActorContext) -> None:
    config = require_active_config(actor.site_id)
    if actor.is_agent:
        if "write" not in actor.scopes:
            raise TranslationAuthorizationError("Agent key lacks required scope: write")
        try:
            require_active_agent_key(
                key_id=actor.key_id,
                site_id=actor.site_id,
                required_scopes=("write",),
            )
        except PermissionError as exc:
            raise TranslationAuthorizationError(str(exc)) from exc
        if config.translation_automation_paused:
            raise TranslationAuthorizationError(
                "Translation automation is paused for this site; human/manual writes remain available."
            )


def require_policy_target_binding(
    actor: ActorContext, target_language: str
) -> Optional[dict[str, Any]]:
    """Enforce an enabled policy's current named-key binding for agent mutations."""
    if not actor.is_agent:
        return None
    config = get_site_language_config(actor.site_id)
    policy = effective_localization_policy(
        actor.site_id,
        load_ai_settings(actor.site_id).get(POLICY_KEY),
        default_language=config.language,
        configured_languages=config.languages,
    )
    if not policy.get("policy_valid", False):
        raise TranslationAuthorizationError(
            "Localization automation policy is invalid; a human must repair it before agent writes."
        )
    if not policy.get("enabled"):
        return None
    target = policy.get("targets", {}).get(target_language)
    if target is None:
        raise TranslationAuthorizationError(
            f"No enabled localization policy is configured for target '{target_language}'."
        )
    if target.get("agent_key_id") != actor.key_id:
        raise TranslationAuthorizationError(
            f"Agent key is not bound to localization target '{target_language}'."
        )
    if not target.get("binding_valid", False):
        raise TranslationAuthorizationError(
            f"Localization target '{target_language}' has an invalid named-key binding."
        )
    return target


def plan_translation_run(
    *,
    actor: ActorContext,
    mode: str,
    target_languages: list[str],
) -> dict[str, Any]:
    config = require_active_config(actor.site_id)
    for language in target_languages:
        if language not in config.languages or language == config.language:
            raise ValueError(f"Invalid translation run target language: {language}")
    if actor.is_agent:
        require_translation_write(actor)
        try:
            return select_run_policy(
                site_id=actor.site_id,
                raw=load_ai_settings(actor.site_id).get(POLICY_KEY),
                default_language=config.language,
                configured_languages=config.languages,
                actor_key_id=actor.key_id,
                mode=mode,
                target_languages=target_languages,
            )
        except PermissionError as exc:
            raise TranslationAuthorizationError(str(exc)) from exc
    return {
        "policy_applied": False,
        "operation": mode,
        "model": None,
        "agent_key_id": None,
        "agent_key_name": None,
        "review_policy": "require_review",
    }


def reject_spoofed_provenance(frontmatter: Optional[dict[str, Any]]) -> None:
    supplied = sorted(SERVER_PROVENANCE_FIELDS.intersection((frontmatter or {}).keys()))
    if supplied:
        raise ValueError(
            "Server-owned provenance/workflow fields may not be supplied: "
            + ", ".join(supplied)
        )


def content_provenance(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: metadata.get(key)
        for key in (
            "created_by",
            "created_by_id",
            "updated_by",
            "updated_by_id",
            "run_id",
            "needs_review",
            "reviewed_by",
            "reviewed_at",
            "review_decision",
            "review_note",
        )
        if key in metadata
    }


def page_payload(page: PageResponse) -> dict[str, Any]:
    return {
        "frontmatter": page.frontmatter,
        "body": page.content,
        "composite": page.composite,
        "partials": page.partials or {},
        "language": page.language,
        "translation_group": page.translation_group,
        "translations": [
            peer.model_dump(exclude_none=True) for peer in (page.translations or [])
        ],
        "provenance": content_provenance(page.frontmatter),
    }


def validated_run_id(actor: ActorContext, run_id: Optional[str]) -> Optional[str]:
    if not run_id:
        return None
    record = get_run(actor.site_id, run_id)
    if record is None:
        raise ValueError(f"Unknown translation run_id: {run_id}")
    if record.get("actor") != actor.kind or record.get("actor_id") != actor.actor_id:
        raise TranslationAuthorizationError(
            "Translation run belongs to a different site-bound actor"
        )
    if record.get("status") != "running":
        raise TranslationConflictError("Translation run is already finished")
    return run_id


def validated_translation_run(
    actor: ActorContext, run_id: Optional[str], target_language: str
) -> Optional[str]:
    """Require a bound policy snapshot for agent writes when policy is enabled."""
    policy_target = require_policy_target_binding(actor, target_language)
    if actor.is_agent and policy_target is not None and not run_id:
        raise TranslationAuthorizationError(
            "Enabled localization policy requires an active bound translation run."
        )
    validated = validated_run_id(actor, run_id)
    if not actor.is_agent or policy_target is None:
        return validated
    record = get_run(actor.site_id, validated or "")
    if (
        record is None
        or not record.get("policy_applied")
        or record.get("agent_key_id") != actor.key_id
        or target_language not in (record.get("target_languages") or [])
    ):
        raise TranslationAuthorizationError(
            "Translation run is not bound to this agent key and target language."
        )
    return validated


def run_requires_review(
    actor: ActorContext, run_id: Optional[str], target_language: str
) -> bool:
    if not actor.is_agent:
        return False
    if not run_id:
        return True
    record = get_run(actor.site_id, run_id)
    if record is None:
        return True
    if target_language not in (record.get("target_languages") or []):
        raise TranslationAuthorizationError(
            "Translation run is not authorized for this target language"
        )
    return record.get("review_policy") != "allow_unreviewed_draft"


def stamp_actor_provenance(
    metadata: dict[str, Any],
    *,
    actor: ActorContext,
    existing: Optional[dict[str, Any]] = None,
    run_id: Optional[str] = None,
    require_agent_review: bool = False,
) -> dict[str, Any]:
    stamped = dict(metadata)
    prior = existing or {}
    if prior.get("created_by"):
        stamped["created_by"] = prior.get("created_by")
        stamped["created_by_id"] = prior.get("created_by_id")
    else:
        stamped["created_by"] = actor.kind
        stamped["created_by_id"] = actor.actor_id
    stamped["updated_by"] = actor.kind
    stamped["updated_by_id"] = actor.actor_id
    if run_id is not None:
        stamped["run_id"] = validated_run_id(actor, run_id)
    elif "run_id" in prior:
        stamped["run_id"] = prior.get("run_id")
    if require_agent_review and actor.is_agent:
        stamped["needs_review"] = True
        stamped["review_decision"] = "pending"
        stamped["reviewed_by"] = None
        stamped["reviewed_at"] = None
    elif existing is None:
        stamped["needs_review"] = False
    return stamped


async def create_translation_sibling(
    *,
    collection: str,
    slug: str,
    language: str,
    actor: ActorContext,
    frontmatter: Optional[dict[str, Any]] = None,
    body: str = "",
    composite: Optional[bool] = None,
    partials: Optional[dict[str, str]] = None,
    run_id: Optional[str] = None,
) -> PageResponse:
    require_translation_write(actor)
    config = get_site_language_config(actor.site_id)
    target_language = normalize_requested_language(language, config)
    if target_language == config.language:
        raise ContentI18nError(
            "Translation sibling language must differ from the site default. "
            "Fix: use the normal entry endpoint for default-language content."
        )
    reject_spoofed_provenance(frontmatter)
    source = await read_page(
        slug,
        category=collection,
        include_partials=True,
        site_id=actor.site_id,
        language=config.language,
    )
    if source is None:
        raise TranslationNotFoundError(
            f"Default-language source '{slug}' was not found"
        )
    if await resolve_path(
        slug,
        collection,
        site_id=actor.site_id,
        language=target_language,
    ):
        raise TranslationConflictError(
            f"Translation sibling '{slug}' already exists for {target_language}"
        )

    metadata = dict(source.frontmatter)
    incoming = frontmatter or {}
    metadata.update(incoming)
    metadata["slug"] = slug
    metadata["category"] = source.frontmatter.get("category") or collection
    requested_status = incoming.get("status") if "status" in incoming else None
    if requested_status is None:
        metadata["status"] = "draft"
        metadata["published"] = False
        metadata["publish_at"] = None
    elif actor.is_agent:
        enforce_publish_autonomy(
            existing_status="stub",
            new_status=requested_status,
            autonomy=autonomy_for_site(actor.site_id),
        )
    metadata["created_by"] = actor.kind
    metadata["created_by_id"] = actor.actor_id
    metadata["updated_by"] = actor.kind
    metadata["updated_by_id"] = actor.actor_id
    metadata["run_id"] = validated_translation_run(
        actor, run_id, target_language
    )
    live = metadata.get("status") == "published"
    needs_review = False if live else run_requires_review(actor, run_id, target_language)
    metadata["needs_review"] = needs_review
    metadata["reviewed_by"] = None
    metadata["reviewed_at"] = None
    metadata["review_decision"] = "pending" if needs_review else None
    clear_review_if_published(metadata)

    page = Page(
        frontmatter=PageFrontmatter(**metadata),
        content=body or "",
        composite=source.composite if composite is None else composite,
        partials=partials or {},
    )
    return await write_page(
        page,
        page_id=slug,
        composite=bool(page.composite),
        partials=page.partials,
        site_id=actor.site_id,
        language=target_language,
    )


async def update_translation_sibling(
    *,
    collection: str,
    slug: str,
    language: str,
    actor: ActorContext,
    frontmatter: Optional[dict[str, Any]],
    body: str,
    composite: Optional[bool] = None,
    partials: Optional[dict[str, str]] = None,
    run_id: Optional[str] = None,
) -> PageResponse:
    require_translation_write(actor)
    config = get_site_language_config(actor.site_id)
    target_language = normalize_requested_language(language, config)
    if target_language == config.language:
        raise ContentI18nError("Use the normal entry endpoint for default-language writes.")
    reject_spoofed_provenance(frontmatter)
    existing = await read_page(
        slug,
        category=collection,
        include_partials=True,
        site_id=actor.site_id,
        language=target_language,
    )
    if existing is None:
        raise TranslationNotFoundError(
            f"Translation sibling '{slug}' was not found for {target_language}"
        )

    metadata = dict(existing.frontmatter)
    metadata.update(frontmatter or {})
    for key in SERVER_PROVENANCE_FIELDS:
        if key in existing.frontmatter:
            metadata[key] = existing.frontmatter[key]
        else:
            metadata.pop(key, None)
    metadata["language"] = target_language
    metadata["translation_group"] = existing.translation_group
    metadata["updated_by"] = actor.kind
    metadata["updated_by_id"] = actor.actor_id
    validated_run = validated_translation_run(actor, run_id, target_language)
    if validated_run is not None:
        metadata["run_id"] = validated_run
    if actor.is_agent:
        requested_status = metadata.get("status")
        enforce_publish_autonomy(
            existing_status=existing.frontmatter.get("status"),
            new_status=requested_status,
            autonomy=autonomy_for_site(actor.site_id),
        )
        live = requested_status == "published"
        needs_review = (
            False if live else run_requires_review(actor, run_id, target_language)
        )
        metadata["needs_review"] = needs_review
        metadata["review_decision"] = "pending" if needs_review else (
            existing.frontmatter.get("review_decision")
        )
        if live:
            metadata["reviewed_by"] = None
            metadata["reviewed_at"] = None
            metadata["review_decision"] = None
        clear_review_if_published(metadata)
    elif bool(existing.frontmatter.get("needs_review")):
        # Human prose edits do not substitute for the explicit review transition.
        metadata["status"] = existing.frontmatter.get("status", "draft")
        metadata["published"] = bool(existing.frontmatter.get("published", False))
        metadata["publish_at"] = existing.frontmatter.get("publish_at")

    page = Page(
        frontmatter=PageFrontmatter(**metadata),
        content=body or "",
        composite=existing.composite if composite is None else composite,
        partials=existing.partials if partials is None else partials,
    )
    return await write_page(
        page,
        page_id=slug,
        composite=bool(page.composite),
        partials=page.partials,
        site_id=actor.site_id,
        language=target_language,
    )


async def delete_translation_sibling(
    *,
    collection: str,
    slug: str,
    language: str,
    actor: ActorContext,
) -> bool:
    require_translation_write(actor)
    config = get_site_language_config(actor.site_id)
    target_language = normalize_requested_language(language, config)
    if target_language == config.language:
        raise TranslationConflictError(
            "Exact sibling deletion cannot delete the default-language source; "
            "delete non-default siblings first."
        )
    require_policy_target_binding(actor, target_language)
    return await delete_page(
        slug,
        category=collection,
        site_id=actor.site_id,
        language=target_language,
    )


async def review_translation_sibling(
    *,
    slug: str,
    language: str,
    actor: ActorContext,
    decision: str,
    note: Optional[str] = None,
) -> PageResponse:
    require_active_config(actor.site_id)
    if actor.is_agent:
        raise TranslationAuthorizationError(
            "Current publication policy requires a human to review translation siblings."
        )
    config = get_site_language_config(actor.site_id)
    target_language = normalize_requested_language(language, config)
    if target_language == config.language:
        raise ContentI18nError("Review targets must be non-default translation siblings.")
    existing = await read_page(
        slug,
        include_partials=True,
        site_id=actor.site_id,
        language=target_language,
    )
    if existing is None:
        raise TranslationNotFoundError(
            f"Translation sibling '{slug}' was not found for {target_language}"
        )
    metadata = dict(existing.frontmatter)
    if decision == "approve":
        if metadata.get("status") not in ("stub", "draft"):
            raise TranslationConflictError(
                f"Translation sibling has status '{metadata.get('status')}' and does not need approval"
            )
        metadata["status"] = "published"
        metadata["published"] = True
        metadata["needs_review"] = False
        metadata["review_decision"] = "approved"
    elif decision == "reject":
        metadata["status"] = "draft"
        metadata["published"] = False
        metadata["publish_at"] = None
        metadata["needs_review"] = False
        metadata["review_decision"] = "rejected"
    else:
        raise ValueError("decision must be 'approve' or 'reject'")
    metadata["reviewed_by"] = actor.actor_id
    metadata["reviewed_at"] = utc_now_iso()
    metadata["review_note"] = note.strip() if note and note.strip() else None
    metadata["updated_by"] = actor.kind
    metadata["updated_by_id"] = actor.actor_id
    page = Page(
        frontmatter=PageFrontmatter(**metadata),
        content=existing.content,
        composite=existing.composite,
        partials=existing.partials,
    )
    return await write_page(
        page,
        page_id=slug,
        composite=existing.composite,
        partials=existing.partials,
        site_id=actor.site_id,
        language=target_language,
    )


def _coverage_summary(language: str, metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "language": language,
        "status": metadata.get("status"),
        "published": bool(metadata.get("published")),
        "needs_review": bool(metadata.get("needs_review")),
        "review_decision": metadata.get("review_decision"),
        "translation_group": metadata.get("translation_group"),
    }


async def translation_coverage(
    site_id: str,
    *,
    language: Optional[str] = None,
) -> dict[str, Any]:
    config = get_site_language_config(site_id)
    base = {
        "config": translation_config(site_id),
        "totals": {
            "eligible": 0,
            "existing": 0,
            "published": 0,
            "draft": 0,
            "needs_review": 0,
            "rejected": 0,
            "missing": 0,
        },
        "items": [],
    }
    if not config.active:
        if language is not None:
            normalize_requested_language(language, config)
        return base
    targets = [lang for lang in config.languages if lang != config.language]
    if language is not None:
        requested = normalize_requested_language(language, config)
        if requested == config.language:
            raise ContentI18nError("Coverage language must be a non-default target.")
        targets = [requested]

    default_slugs: list[str] = []
    for path in await iter_canonical_files(site_id):
        identity = content_identity_for_path(path, site_id)
        if identity.is_default and identity.slug not in default_slugs:
            default_slugs.append(identity.slug)

    totals = base["totals"]
    for slug in default_slugs:
        records = await list_sibling_records(slug, site_id=site_id)
        by_language = {record["language"]: record for record in records}
        source = by_language.get(config.language)
        if source is None:
            continue
        source_metadata = source["frontmatter"]
        sibling_summaries = [
            _coverage_summary(code, by_language[code]["frontmatter"])
            for code in targets
            if code in by_language
        ]
        gaps: list[str] = []
        for target in targets:
            totals["eligible"] += 1
            record = by_language.get(target)
            if record is None:
                totals["missing"] += 1
                gaps.append(f"{target}:missing")
                continue
            metadata = record["frontmatter"]
            totals["existing"] += 1
            if is_live_translation(source_metadata) and is_live_translation(metadata):
                totals["published"] += 1
            else:
                totals["draft"] += 1
                gaps.append(f"{target}:draft")
            if metadata.get("needs_review"):
                totals["needs_review"] += 1
                gaps.append(f"{target}:needs_review")
            if metadata.get("review_decision") == "rejected":
                totals["rejected"] += 1
                gaps.append(f"{target}:rejected")
        base["items"].append(
            {
                "slug": slug,
                "collection": source_metadata.get("category") or "general",
                "source": _coverage_summary(config.language, source_metadata),
                "siblings": sibling_summaries,
                "gap_codes": gaps,
            }
        )
    return base
