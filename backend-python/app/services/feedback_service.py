"""Public feedback ingest and v1 relay poll: contact fb-* stubs and comment files."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

import config as app_config
from models.page import Page, PageFrontmatter
from services.comment_service import (
    CommentIngestError,
    CommentsDisabledError,
    write_comment,
)
from services.file_service import name_to_id, resolve_path, write_page
from services.site_service import (
    get_site,
    mint_feedback_fetch_token,
    mint_feedback_submission_key,
    resolve_feedback_relay_url,
    site_comments_enabled,
    update_site,
)

logger = logging.getLogger("pencms.feedback")

HEADLINE_WORD_COUNT = 6
KIND_CONTACT = "contact"
KIND_COMMENT = "comment"
ALLOWED_KINDS = (KIND_CONTACT, KIND_COMMENT)
SOURCE_TYPE_FORM = "form"
SOURCE_TYPE_RELAY = "relay"
REGISTER_TIMEOUT_SECONDS = 10.0
SYNC_TIMEOUT_SECONDS = 30.0
_relay_registered: set[str] = set()


def _headline_from_message(message: str) -> tuple[str, str]:
    """Return (headline, slug_suffix) from the first words of the message."""
    words = message.split()[:HEADLINE_WORD_COUNT]
    raw = " ".join(words).strip()
    slug_part = name_to_id(raw) if raw else ""
    if not slug_part:
        return "Feedback", "feedback"
    return raw, slug_part


async def _unique_slug(site_id: str, base: str) -> str:
    """Append -2, -3, … when the base slug directory already exists."""
    candidate = base
    n = 2
    while await resolve_path(candidate, site_id=site_id) is not None:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def _optional_item_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _received_at_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def write_ingest_item(
    site_id: str,
    *,
    submitter: str,
    message: str,
    email: Optional[str] = None,
    source_url: Optional[str] = None,
    kind: str = KIND_CONTACT,
    parent_slug: Optional[str] = None,
    source_type: str = SOURCE_TYPE_FORM,
    received_at: Optional[str] = None,
) -> str:
    """Dispatch public/relay ingest: comments beside the post, contact as fb-*."""
    kind_value = kind if kind in ALLOWED_KINDS else KIND_CONTACT
    if kind_value == KIND_COMMENT:
        if not site_comments_enabled(site_id):
            raise CommentsDisabledError("Comments are disabled for this site")
        return await write_comment(
            site_id,
            submitter=submitter,
            message=message,
            parent_slug=parent_slug,
            source_type=source_type,
            received_at=received_at,
        )
    return await write_feedback_item(
        site_id,
        submitter=submitter,
        message=message,
        email=email,
        source_url=source_url,
        source_type=source_type,
        received_at=received_at,
    )


async def write_feedback_item(
    site_id: str,
    *,
    submitter: str,
    message: str,
    email: Optional[str] = None,
    source_url: Optional[str] = None,
    source_type: str = SOURCE_TYPE_FORM,
    received_at: Optional[str] = None,
) -> str:
    """Write a contact stub page and return its slug (``fb-…``)."""
    headline, slug_suffix = _headline_from_message(message)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    slug = await _unique_slug(site_id, f"fb-{stamp}-{slug_suffix}")

    handle = (submitter or "").strip() or "Anonymous"
    stamped = _optional_item_str(received_at) or _received_at_now()

    fm_dict: dict = {
        "name": headline,
        "slug": slug,
        "page": True,
        "status": "stub",
        "published": False,
        "kind": KIND_CONTACT,
        "submitter": handle,
        "source_type": source_type,
        "received_at": stamped,
    }
    if email:
        fm_dict["email"] = email
    if source_url:
        fm_dict["source_url"] = source_url

    tax_token = app_config.set_active_taxonomy(
        app_config.load_taxonomy_for_site(site_id)
    )
    try:
        page_obj = Page(
            frontmatter=PageFrontmatter(**fm_dict),
            content=message,
            composite=False,
            partials={},
        )
        await write_page(
            page_obj, page_id=slug, composite=False, partials={}, site_id=site_id
        )
    finally:
        app_config.reset_active_taxonomy(tax_token)

    logger.info("Wrote feedback stub %s on site %s", slug, site_id)
    return slug


async def _register_with_relay(
    url: str, *, submission_key: str, fetch_token: str
) -> None:
    """POST /register. Log failures; never raise (relay down must not block enable)."""
    register_url = f"{url.rstrip('/')}/register"
    try:
        async with httpx.AsyncClient(timeout=REGISTER_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                register_url,
                json={
                    "submission_key": submission_key,
                    "fetch_token_hash": fetch_token,
                },
            )
            if resp.status_code >= 400:
                logger.warning(
                    "Relay register failed (%s) at %s",
                    resp.status_code,
                    register_url,
                )
    except httpx.HTTPError as exc:
        logger.warning("Relay register unreachable at %s: %s", register_url, exc)


async def ensure_feedback_relay(
    site_id: str,
    *,
    relay_url: Optional[str] = None,
    rotate_fetch_token: bool = False,
    force_register: bool = False,
):
    """Mint missing relay credentials, persist, and POST /register.

    Empty ``feedback_relay_url`` falls back to ``https://feedback.pencms.org``.
    Register HTTP failure is logged; keys still persist.
    """
    site = get_site(site_id)
    if site is None:
        raise ValueError(f"Unknown site_id: {site_id}")

    url = resolve_feedback_relay_url(site, url=relay_url)
    minted = False
    submission_key = site.feedback_submission_key
    if not submission_key:
        submission_key = mint_feedback_submission_key()
        minted = True
    if rotate_fetch_token or not site.feedback_fetch_token:
        fetch_token = mint_feedback_fetch_token()
        minted = True
    else:
        fetch_token = site.feedback_fetch_token

    kwargs: dict[str, Any] = {}
    if minted:
        kwargs["feedback_submission_key"] = submission_key
        kwargs["feedback_fetch_token"] = fetch_token
    if relay_url is not None:
        kwargs["feedback_relay_url"] = url
    if kwargs:
        site = update_site(site_id, **kwargs)

    if minted or rotate_fetch_token or force_register or site_id not in _relay_registered:
        await _register_with_relay(
            url, submission_key=submission_key, fetch_token=fetch_token
        )
        _relay_registered.add(site_id)
    return get_site(site_id) or site


def _sync_failure(reason: str, *, written: int = 0, slugs: Optional[list] = None) -> dict:
    out: dict[str, Any] = {"written": written, "reason": reason}
    if slugs is not None:
        out["slugs"] = slugs
    return out


async def sync_from_relay(site_id: str) -> dict:
    """Pull unacked relay items into fb-* files. Never mints credentials."""
    site = get_site(site_id)
    if site is None or not site.feedback_submission_key or not site.feedback_fetch_token:
        return _sync_failure("no_relay_configured")

    url = resolve_feedback_relay_url(site)
    fetch_url = f"{url}/fetch"
    ack_url = f"{url}/ack"
    cursor = site.feedback_relay_cursor or "0"
    headers = {"Authorization": f"Bearer {site.feedback_fetch_token}"}
    params = {
        "submission_key": site.feedback_submission_key,
        "since": cursor,
    }

    try:
        async with httpx.AsyncClient(timeout=SYNC_TIMEOUT_SECONDS) as client:
            try:
                resp = await client.get(fetch_url, params=params, headers=headers)
            except httpx.HTTPError as exc:
                logger.warning("Relay fetch unreachable at %s: %s", fetch_url, exc)
                return _sync_failure("relay_unreachable")
            if resp.status_code >= 400:
                logger.warning(
                    "Relay fetch failed (%s) at %s", resp.status_code, fetch_url
                )
                return _sync_failure("relay_unreachable")
            try:
                payload = resp.json()
            except ValueError:
                return _sync_failure("relay_unreachable")
            if not isinstance(payload, dict):
                return _sync_failure("relay_unreachable")
            items = payload.get("items")
            if not isinstance(items, list):
                items = []

            slugs: list[str] = []
            acked_ids: list[int] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                message = _optional_item_str(item.get("message"))
                if not message:
                    continue
                slug = None
                try:
                    slug = await write_ingest_item(
                        site_id,
                        submitter=_optional_item_str(item.get("name")) or "Anonymous",
                        message=message,
                        email=_optional_item_str(item.get("email")),
                        source_url=_optional_item_str(item.get("source_url")),
                        kind=_optional_item_str(item.get("kind")) or KIND_CONTACT,
                        parent_slug=_optional_item_str(item.get("parent_slug")),
                        source_type=SOURCE_TYPE_RELAY,
                        received_at=_optional_item_str(item.get("received_at")),
                    )
                except CommentIngestError as exc:
                    logger.warning(
                        "Skipping relay comment on site %s: %s", site_id, exc
                    )
                if slug:
                    slugs.append(slug)
                raw_id = item.get("id")
                if raw_id is not None:
                    try:
                        acked_ids.append(int(raw_id))
                    except (TypeError, ValueError):
                        pass

            if acked_ids:
                try:
                    ack_resp = await client.post(
                        ack_url,
                        json={
                            "submission_key": site.feedback_submission_key,
                            "ids": acked_ids,
                        },
                        headers=headers,
                    )
                except httpx.HTTPError as exc:
                    logger.warning("Relay ack unreachable at %s: %s", ack_url, exc)
                    return _sync_failure(
                        "relay_unreachable", written=len(slugs), slugs=slugs
                    )
                if ack_resp.status_code >= 400:
                    logger.warning(
                        "Relay ack failed (%s) at %s", ack_resp.status_code, ack_url
                    )
                    return _sync_failure(
                        "relay_unreachable", written=len(slugs), slugs=slugs
                    )
                update_site(
                    site_id, feedback_relay_cursor=str(max(acked_ids))
                )

            return {"written": len(slugs), "slugs": slugs}
    except httpx.HTTPError as exc:
        logger.warning("Relay sync unreachable: %s", exc)
        return _sync_failure("relay_unreachable")
