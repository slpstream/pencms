"""Site-scoped authors CRUD + avatar upload isolation."""

from __future__ import annotations

import base64

import pytest
import yaml
from models.author import AuthorCreate, AuthorUpdate
from services import author_service


@pytest.fixture(autouse=True)
def clean_default_authors(temp_data_root):
    """Remove default authors.yaml between tests when present."""
    path = temp_data_root / "content" / "sites" / "default" / "authors.yaml"
    if path.exists():
        path.unlink()
    yield
    if path.exists():
        path.unlink()


@pytest.fixture
def two_sites(authed_client, temp_data_root):
    from services.site_service import create_site, ensure_sites_initialized

    ensure_sites_initialized()
    try:
        create_site("other", "Other Site")
    except ValueError:
        pass
    return temp_data_root / "content"


@pytest.mark.asyncio
async def test_service_crud_and_slug_uniqueness(temp_data_root):
    authors = await author_service.list_authors("default")
    assert authors == []

    a1 = await author_service.create_author(
        AuthorCreate(name="Jane Doe", bio="Plain bio", website="https://example.com")
    )
    assert a1.slug == "jane-doe"
    assert a1.bio == "Plain bio"
    assert a1.avatar is None

    with pytest.raises(ValueError, match="already exists"):
        await author_service.create_author(AuthorCreate(name="Other", slug="jane-doe"))

    a2 = await author_service.create_author(
        AuthorCreate(name="Bob Smith", slug="bob", role="Editor", sort_order=5)
    )
    assert a2.slug == "bob"
    assert a2.sort_order == 5

    updated = await author_service.update_author(
        "jane-doe", AuthorUpdate(bio="Updated bio", role="Writer")
    )
    assert updated.bio == "Updated bio"
    assert updated.role == "Writer"
    assert updated.slug == "jane-doe"

    yaml_path = temp_data_root / "content" / "sites" / "default" / "authors.yaml"
    assert yaml_path.is_file()
    data = yaml.safe_load(yaml_path.read_text())
    assert len(data["authors"]) == 2

    await author_service.delete_author("bob")
    remaining = await author_service.list_authors("default")
    assert len(remaining) == 1
    assert remaining[0].slug == "jane-doe"


def test_authors_rest_site_isolation(authed_client, two_sites):
    headers_other = {"X-Pen-Site-Id": "other"}
    headers_default = {"X-Pen-Site-Id": "default"}

    resp = authed_client.post(
        "/api/authors/",
        json={"name": "Wiki Author", "bio": "Only on other"},
        headers=headers_other,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["slug"] == "wiki-author"

    other_yaml = two_sites / "sites" / "other" / "authors.yaml"
    assert other_yaml.is_file()
    data = yaml.safe_load(other_yaml.read_text())
    assert any(a.get("slug") == "wiki-author" for a in data.get("authors", []))

    resp = authed_client.get("/api/authors/", headers=headers_default)
    assert resp.status_code == 200
    assert resp.json()["site_id"] == "default"
    assert not any(a["slug"] == "wiki-author" for a in resp.json()["authors"])

    resp = authed_client.get("/api/authors/", headers=headers_other)
    assert resp.status_code == 200
    assert resp.json()["site_id"] == "other"
    assert any(a["slug"] == "wiki-author" for a in resp.json()["authors"])


def test_authors_unknown_site_400(authed_client, two_sites):
    resp = authed_client.get("/api/authors/", headers={"X-Pen-Site-Id": "nope"})
    assert resp.status_code == 400


def test_authors_crud_http(authed_client, two_sites):
    headers = {"X-Pen-Site-Id": "default"}

    resp = authed_client.post(
        "/api/authors/",
        json={"name": "Ada Lovelace", "bio": "Math", "email": "ada@example.com"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    slug = resp.json()["slug"]
    assert slug == "ada-lovelace"
    assert resp.json()["avatar"] is None

    resp = authed_client.get(f"/api/authors/{slug}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Ada Lovelace"

    resp = authed_client.put(
        f"/api/authors/{slug}",
        json={"bio": "Updated", "role": "Mathematician"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["bio"] == "Updated"
    assert resp.json()["role"] == "Mathematician"

    resp = authed_client.delete(f"/api/authors/{slug}", headers=headers)
    assert resp.status_code == 204

    resp = authed_client.get(f"/api/authors/{slug}", headers=headers)
    assert resp.status_code == 404


def test_author_avatar_upload_site_scoped(authed_client, two_sites):
    png_1x1 = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    headers_other = {"X-Pen-Site-Id": "other"}

    resp = authed_client.post(
        "/api/authors/",
        json={"name": "Avatar Person"},
        headers=headers_other,
    )
    assert resp.status_code == 201, resp.text
    slug = resp.json()["slug"]

    files = {"file": ("pic.png", png_1x1, "image/png")}
    resp = authed_client.post(
        f"/api/authors/{slug}/avatar",
        files=files,
        headers=headers_other,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["site_id"] == "other"
    assert data["path"] == f"images/authors/{slug}.png"
    assert f"sites/other/assets" in data["url"]

    dest = (
        two_sites
        / "sites"
        / "other"
        / "assets"
        / "images"
        / "authors"
        / f"{slug}.png"
    )
    assert dest.is_file()

    # Default site must not see this author or file
    resp = authed_client.get("/api/authors/", headers={"X-Pen-Site-Id": "default"})
    assert not any(a["slug"] == slug for a in resp.json()["authors"])
    default_avatar = (
        two_sites
        / "sites"
        / "default"
        / "assets"
        / "images"
        / "authors"
        / f"{slug}.png"
    )
    assert not default_avatar.exists()


def test_seed_authors_yaml_on_new_site(authed_client, temp_data_root):
    from services.site_service import create_site, ensure_sites_initialized

    ensure_sites_initialized()
    try:
        create_site("authorseed", "Author Seed Site")
    except ValueError:
        pass

    path = temp_data_root / "content" / "sites" / "authorseed" / "authors.yaml"
    assert path.is_file()
    data = yaml.safe_load(path.read_text())
    assert data == {"authors": []}
