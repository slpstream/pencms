"""Scheduled publishing: publish_at validation, live listing, approve/publish."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from models.page import PageFrontmatter, normalize_publish_at
from pydantic import ValidationError


def _future_iso(hours: int = 24) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _past_iso(hours: int = 24) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


# ---------------------------------------------------------------------------
# normalize_publish_at / PageFrontmatter
# ---------------------------------------------------------------------------


def test_normalize_publish_at_iso_z():
    assert normalize_publish_at("2026-07-20T15:30:00Z") == "2026-07-20T15:30:00Z"


def test_normalize_publish_at_bare_date_is_utc_midnight():
    assert normalize_publish_at("2026-07-20") == "2026-07-20T00:00:00Z"


def test_normalize_publish_at_empty_is_none():
    assert normalize_publish_at(None) is None
    assert normalize_publish_at("") is None


def test_normalize_publish_at_rejects_garbage():
    with pytest.raises(ValueError):
        normalize_publish_at("not-a-date")


def test_frontmatter_defaults_date_from_publish_at():
    fm = PageFrontmatter(
        category="general",
        name="Scheduled Piece",
        status="draft",
        publish_at="2026-08-01T12:00:00Z",
    )
    assert fm.publish_at == "2026-08-01T12:00:00Z"
    assert fm.date == "2026-08-01"


def test_frontmatter_preserves_explicit_date():
    fm = PageFrontmatter(
        category="general",
        name="Dated Piece",
        status="draft",
        date="2026-01-15",
        publish_at="2026-08-01T12:00:00Z",
    )
    assert fm.date == "2026-01-15"


# ---------------------------------------------------------------------------
# Live listing via API
# ---------------------------------------------------------------------------


def _create_published(authed_client, slug: str, publish_at: str | None = None):
    fm = {
        "name": slug.replace("-", " ").title(),
        "category": "general",
        "status": "published",
        "published": True,
        "domain": "blog",
    }
    if publish_at is not None:
        fm["publish_at"] = publish_at
    resp = authed_client.post(
        "/api/pages/",
        json={"frontmatter": fm, "content": "Body.", "slug": slug},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_live_list_excludes_future_publish_at(client, authed_client):
    """live_only hides future publish_at; unauthenticated defaults to live_only."""
    future_slug = "sched-future-post"
    past_slug = "sched-past-post"
    _create_published(authed_client, future_slug, _future_iso(48))
    _create_published(authed_client, past_slug, _past_iso(1))

    resp = authed_client.get(
        "/api/pages/", params={"status": "published", "live_only": "true"}
    )
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()}
    assert past_slug in ids
    assert future_slug not in ids

    # Drop auth cookie — unauthenticated default is live_only=true
    client.cookies.clear()
    resp = client.get("/api/pages/", params={"status": "published"})
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()}
    assert past_slug in ids
    assert future_slug not in ids


def test_authed_list_includes_scheduled(authed_client):
    """Authenticated admin list sees future publish_at unless live_only=true."""
    slug = "sched-admin-visible"
    _create_published(authed_client, slug, _future_iso(72))

    resp = authed_client.get(
        "/api/pages/", params={"status": "published", "live_only": "false"}
    )
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()}
    assert slug in ids

    resp = authed_client.get(
        "/api/pages/", params={"status": "published", "live_only": "true"}
    )
    ids = {p["id"] for p in resp.json()}
    assert slug not in ids


def test_published_without_publish_at_is_live(authed_client):
    slug = "sched-immediate"
    _create_published(authed_client, slug, publish_at=None)
    resp = authed_client.get("/api/pages/", params={"live_only": "true"})
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()}
    assert slug in ids


def test_live_only_lists_status_published_even_if_boolean_false(authed_client):
    """Editorial go-live is status + publish_at; the boolean published flag is not a gate."""
    live_slug = "legacy-status-published"
    draft_slug = "legacy-status-draft"
    future_slug = "legacy-status-future"

    live_resp = authed_client.post(
        "/api/pages/",
        json={
            "frontmatter": {
                "name": "Legacy Live",
                "category": "general",
                "status": "published",
                "published": False,
                "domain": "blog",
            },
            "content": "Body.",
            "slug": live_slug,
        },
    )
    assert live_resp.status_code == 201, live_resp.text
    assert live_resp.json()["frontmatter"]["status"] == "published"
    assert live_resp.json()["frontmatter"]["published"] is False

    draft_resp = authed_client.post(
        "/api/pages/",
        json={
            "frontmatter": {
                "name": "Legacy Draft",
                "category": "general",
                "status": "draft",
                "published": False,
                "domain": "blog",
            },
            "content": "Body.",
            "slug": draft_slug,
        },
    )
    assert draft_resp.status_code == 201, draft_resp.text

    _create_published(authed_client, future_slug, _future_iso(48))

    resp = authed_client.get("/api/pages/", params={"live_only": "true"})
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()}
    assert live_slug in ids
    assert draft_slug not in ids
    assert future_slug not in ids


def test_due_within_hours(authed_client):
    recent = "sched-due-recent"
    old = "sched-due-old"
    _create_published(authed_client, recent, _past_iso(2))
    _create_published(authed_client, old, _past_iso(48))

    resp = authed_client.get("/api/pages/", params={"due_within_hours": 6})
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()}
    assert recent in ids
    assert old not in ids


# ---------------------------------------------------------------------------
# Approve / publish workflow unchanged
# ---------------------------------------------------------------------------


def test_approve_then_publish_still_works(authed_client):
    slug = "sched-approve-flow"
    resp = authed_client.post(
        "/api/pages/",
        json={
            "frontmatter": {
                "name": "Approve Flow",
                "category": "general",
                "status": "draft",
                "domain": "blog",
            },
            "content": "Draft body.",
            "slug": slug,
        },
    )
    assert resp.status_code == 201, resp.text

    resp = authed_client.patch(f"/api/pages/{slug}/approve")
    assert resp.status_code == 200, resp.text
    fm = resp.json()["frontmatter"]
    assert fm["status"] == "published"
    assert fm.get("published") is True
