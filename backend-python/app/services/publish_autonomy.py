"""Shared ``ai_publish_autonomy`` checks for agent status writes.

One trust dial for monolingual posts, default-language i18n writes, and
translation siblings. ``review_policy`` is only a ``needs_review`` queue flag.
"""

from __future__ import annotations

from typing import Optional

from services.ai_settings_service import load_ai_settings

RESTRICTED_STATUS_DETAIL = (
    "Permission Denied: AI is prohibited from modifying the status field."
)


class PublishAutonomyError(ValueError):
    """Agent status change blocked by site ``ai_publish_autonomy``."""


def require_approval_status_detail(new_status: str) -> str:
    return (
        f"Permission Denied: AI is not allowed to set status to '{new_status}' "
        "without human approval. Please set status to 'draft' or 'stub'."
    )


def enforce_publish_autonomy(
    *,
    existing_status: Optional[str],
    new_status: Optional[str],
    autonomy: Optional[str],
) -> None:
    """Raise ``PublishAutonomyError`` when the status change is not allowed.

    ``autonomous``: any status. ``require_approval``: stub/draft only (not
    published/unpublished). ``restricted``: no status changes.
    Treat a missing existing status as ``stub`` (create bootstrap).
    """
    if new_status is None:
        return
    previous = existing_status if existing_status is not None else "stub"
    if new_status == previous:
        return
    mode = autonomy or "require_approval"
    if mode == "restricted":
        raise PublishAutonomyError(RESTRICTED_STATUS_DETAIL)
    if mode == "require_approval" and new_status in ("published", "unpublished"):
        raise PublishAutonomyError(require_approval_status_detail(str(new_status)))


def autonomy_for_site(site_id: str) -> str:
    settings = load_ai_settings(site_id)
    return settings.get("ai_publish_autonomy") or "require_approval"


def clear_review_if_published(metadata: dict) -> None:
    """Publishing is the decision; do not leave a review queue flag on live copy."""
    if metadata.get("status") == "published":
        metadata["published"] = True
        metadata["needs_review"] = False
        if not metadata.get("review_decision"):
            metadata["review_decision"] = None
