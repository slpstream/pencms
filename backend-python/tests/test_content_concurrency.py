"""Optimistic concurrency across MCP, v1 entries, and /api/pages."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from fastapi import HTTPException

from services.concurrency import (
    SOFT_VERSION_WARNING,
    STRICT_ENV,
    check_expected_version,
)


def _slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _page_body(name: str, slug: str, content: str = "body") -> dict:
    return {
        "frontmatter": {
            "name": name,
            "status": "draft",
            "domain": "blog",
            "published": False,
            "category": "summer",
        },
        "content": content,
        "slug": slug,
    }


def _v1_body(name: str, body: str = "body") -> dict:
    return {
        "frontmatter": {
            "name": name,
            "status": "draft",
            "domain": "blog",
            "category": "summer",
        },
        "body": body,
    }


def _bump_content_mtime(authed_client, temp_data_root: Path, slug: str) -> None:
    """Advance mtime by 2s so the opaque token changes on coarse filesystems."""
    got = authed_client.get(f"/api/pages/{slug}")
    assert got.status_code == 200, got.text
    rel = got.json().get("file_path")
    assert rel, f"no file_path on GET /api/pages/{slug}"
    path = temp_data_root / "content" / rel
    if not path.is_file():
        matches = [
            p
            for p in (temp_data_root / "content").rglob("*.md")
            if p.name == f"{slug}.md" or (p.name == "index.md" and slug in p.parts)
        ]
        assert matches, f"no markdown file for slug {slug} (looked for {path})"
        path = matches[0]
    stat = path.stat()
    os.utime(path, (stat.st_atime, stat.st_mtime + 2.0))


@pytest.fixture
def strict_on(monkeypatch):
    monkeypatch.setenv(STRICT_ENV, "1")


@pytest.fixture
def strict_off(monkeypatch):
    monkeypatch.setenv(STRICT_ENV, "0")


def test_check_expected_version_skip_and_force(strict_on):
    assert check_expected_version(None, "1.0", force=False) is None
    assert check_expected_version("1.0", None, force=False) is None
    assert check_expected_version("1.0", "1.0", force=False) is None
    assert check_expected_version("old", "new", force=True) is None
    try:
        check_expected_version("old", "new", force=False)
        raise AssertionError("expected 409")
    except HTTPException as exc:
        assert exc.status_code == 409
        assert exc.detail["error"] == "version_conflict"


def test_check_expected_version_soft_warn(strict_off):
    warning = check_expected_version("old", "new", force=False)
    assert warning == SOFT_VERSION_WARNING


def test_pages_get_returns_version(authed_client):
    slug = _slug("conc-pages-get")
    created = authed_client.post("/api/pages/", json=_page_body("Get Version", slug))
    assert created.status_code == 201, created.text
    assert created.json().get("version")

    got = authed_client.get(f"/api/pages/{slug}")
    assert got.status_code == 200, got.text
    assert got.json().get("version")
    assert got.json()["version"] == created.json()["version"]


def test_v1_get_returns_version(authed_client):
    slug = _slug("conc-v1-get")
    created = authed_client.put(
        f"/api/v1/content/collections/summer/entries/{slug}",
        json=_v1_body("V1 Get Version"),
    )
    assert created.status_code == 200, created.text
    assert created.json().get("version")

    got = authed_client.get(f"/api/v1/content/collections/summer/entries/{slug}")
    assert got.status_code == 200, got.text
    assert got.json().get("version")
    assert got.json()["version"] == created.json()["version"]


def test_pages_matching_token_succeeds(authed_client, strict_on):
    slug = _slug("conc-pages-match")
    created = authed_client.post("/api/pages/", json=_page_body("Match", slug, "v1"))
    token = created.json()["version"]
    updated = authed_client.put(
        f"/api/pages/{slug}",
        json={**_page_body("Match", slug, "v2"), "expected_version": token},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json().get("version")
    assert "version_warning" not in updated.json()
    assert authed_client.get(f"/api/pages/{slug}").json()["content"].strip() == "v2"


def test_v1_matching_token_succeeds(authed_client, strict_on):
    slug = _slug("conc-v1-match")
    created = authed_client.put(
        f"/api/v1/content/collections/summer/entries/{slug}",
        json=_v1_body("Match", "v1"),
    )
    token = created.json()["version"]
    updated = authed_client.put(
        f"/api/v1/content/collections/summer/entries/{slug}",
        json={**_v1_body("Match", "v2"), "expected_version": token},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json().get("version")
    assert "version_warning" not in updated.json()


def test_pages_stale_token_409_leaves_disk(authed_client, temp_data_root, strict_on):
    slug = _slug("conc-pages-stale")
    created = authed_client.post("/api/pages/", json=_page_body("Stale", slug, "original"))
    stale = created.json()["version"]
    _bump_content_mtime(authed_client, temp_data_root, slug)

    conflicted = authed_client.put(
        f"/api/pages/{slug}",
        json={**_page_body("Stale", slug, "clobber"), "expected_version": stale},
    )
    assert conflicted.status_code == 409, conflicted.text
    detail = conflicted.json()["detail"]
    assert detail["error"] == "version_conflict"
    assert detail["expected_version"] == stale
    assert detail["current_version"] != stale
    assert authed_client.get(f"/api/pages/{slug}").json()["content"].strip() == "original"


def test_v1_stale_token_409_leaves_disk(authed_client, temp_data_root, strict_on):
    slug = _slug("conc-v1-stale")
    created = authed_client.put(
        f"/api/v1/content/collections/summer/entries/{slug}",
        json=_v1_body("Stale", "original"),
    )
    stale = created.json()["version"]
    _bump_content_mtime(authed_client, temp_data_root, slug)

    conflicted = authed_client.put(
        f"/api/v1/content/collections/summer/entries/{slug}",
        json={**_v1_body("Stale", "clobber"), "expected_version": stale},
    )
    assert conflicted.status_code == 409, conflicted.text
    detail = conflicted.json()["detail"]
    assert detail["error"] == "version_conflict"
    got = authed_client.get(f"/api/v1/content/collections/summer/entries/{slug}")
    assert got.json()["body"].strip() == "original"


def test_omitted_expected_version_is_unconditional(authed_client, temp_data_root, strict_on):
    slug = _slug("conc-omit")
    authed_client.post("/api/pages/", json=_page_body("Omit", slug, "v1"))
    _bump_content_mtime(authed_client, temp_data_root, slug)
    updated = authed_client.put(
        f"/api/pages/{slug}",
        json=_page_body("Omit", slug, "v2"),
    )
    assert updated.status_code == 200, updated.text
    assert authed_client.get(f"/api/pages/{slug}").json()["content"].strip() == "v2"


def test_force_true_overwrites_stale_token(authed_client, temp_data_root, strict_on):
    slug = _slug("conc-force")
    created = authed_client.put(
        f"/api/v1/content/collections/summer/entries/{slug}",
        json=_v1_body("Force", "original"),
    )
    stale = created.json()["version"]
    _bump_content_mtime(authed_client, temp_data_root, slug)
    updated = authed_client.put(
        f"/api/v1/content/collections/summer/entries/{slug}",
        json={
            **_v1_body("Force", "forced"),
            "expected_version": stale,
            "force": True,
        },
    )
    assert updated.status_code == 200, updated.text
    assert "version_warning" not in updated.json()
    got = authed_client.get(f"/api/v1/content/collections/summer/entries/{slug}")
    assert got.json()["body"].strip() == "forced"


def test_soft_warn_when_strict_disabled(authed_client, temp_data_root, strict_off):
    slug = _slug("conc-soft")
    created = authed_client.put(
        f"/api/v1/content/collections/summer/entries/{slug}",
        json=_v1_body("Soft", "v1"),
    )
    stale = created.json()["version"]
    _bump_content_mtime(authed_client, temp_data_root, slug)
    updated = authed_client.put(
        f"/api/v1/content/collections/summer/entries/{slug}",
        json={**_v1_body("Soft", "v2"), "expected_version": stale},
    )
    assert updated.status_code == 200, updated.text
    assert "version_warning" in updated.json()
    assert "not yet enforced" in updated.json()["version_warning"]
    got = authed_client.get(f"/api/v1/content/collections/summer/entries/{slug}")
    assert got.json()["body"].strip() == "v2"
