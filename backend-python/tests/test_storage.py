import os
import shutil
import pytest
from pathlib import Path


def test_upload_site_hero_success(client, temp_data_root):
    site_images = temp_data_root / "content" / "sites" / "default" / "assets" / "images"
    if site_images.exists():
        shutil.rmtree(site_images)

    # 1. Upload a PNG hero image → active site (default) assets
    files = {"file": ("test_hero.png", b"fake png content", "image/png")}
    response = client.post("/api/storage/hero", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Hero image uploaded successfully"
    assert body["path"] == "images/hero.png"
    assert body["site_id"] == "default"
    assert body["url"] == "/api/assets/raw/sites/default/assets/images/hero.png"

    target_file = site_images / "hero.png"
    assert target_file.exists()
    assert target_file.read_bytes() == b"fake png content"

    # 2. Upload a JPEG hero image, should clean up PNG
    files = {"file": ("test_hero.jpeg", b"fake jpeg content", "image/jpeg")}
    response = client.post("/api/storage/hero", files=files)

    assert response.status_code == 200
    assert response.json()["url"] == "/api/assets/raw/sites/default/assets/images/hero.jpg"

    assert not target_file.exists()
    target_jpg = site_images / "hero.jpg"
    assert target_jpg.exists()
    assert target_jpg.read_bytes() == b"fake jpeg content"


def test_upload_site_hero_invalid_extension(client):
    files = {"file": ("test_hero.txt", b"plain text", "text/plain")}
    response = client.post("/api/storage/hero", files=files)

    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_upload_site_hero_file_too_large(client):
    from config import MAX_UPLOAD_SIZE
    large_data = b"x" * (MAX_UPLOAD_SIZE + 100)
    files = {"file": ("large_hero.png", large_data, "image/png")}
    response = client.post("/api/storage/hero", files=files)

    assert response.status_code == 413
    assert "File too large" in response.json()["detail"]


def test_upload_site_favicon_success(client, temp_data_root):
    site_images = temp_data_root / "content" / "sites" / "default" / "assets" / "images"
    if site_images.exists():
        shutil.rmtree(site_images)

    files = {"file": ("test_fav.svg", b"<svg>fake favicon</svg>", "image/svg+xml")}
    response = client.post("/api/storage/favicon", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Favicon uploaded successfully"
    assert body["path"] == "images/favicon.svg"
    assert body["url"] == "/api/assets/raw/sites/default/assets/images/favicon.svg"

    target_file = site_images / "favicon.svg"
    assert target_file.exists()
    assert target_file.read_bytes() == b"<svg>fake favicon</svg>"

    files = {"file": ("test_fav.ico", b"fake ico content", "image/x-icon")}
    response = client.post("/api/storage/favicon", files=files)

    assert response.status_code == 200
    assert response.json()["url"] == "/api/assets/raw/sites/default/assets/images/favicon.ico"

    assert not target_file.exists()
    target_ico = site_images / "favicon.ico"
    assert target_ico.exists()
    assert target_ico.read_bytes() == b"fake ico content"


def test_upload_site_favicon_invalid_extension(client):
    files = {"file": ("test_fav.txt", b"plain text", "text/plain")}
    response = client.post("/api/storage/favicon", files=files)

    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_upload_logo_respects_site_header(client, temp_data_root):
    """Logo for a non-default site lands under that site's assets tree."""
    from services.site_service import create_site, get_site

    sid = "logo-wiki"
    if get_site(sid) is None:
        create_site(sid, "Logo Wiki")
    files = {"file": ("logo.png", b"wiki-logo", "image/png")}
    response = client.post(
        "/api/storage/logo",
        files=files,
        headers={"X-Pen-Site-Id": sid},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["site_id"] == sid
    assert body["path"] == "images/logo.png"
    target = temp_data_root / "content" / "sites" / sid / "assets" / "images" / "logo.png"
    assert target.exists()
    assert target.read_bytes() == b"wiki-logo"
    # default site must not receive the file
    assert not (temp_data_root / "content" / "sites" / "default" / "assets" / "images" / "logo.png").exists()


def test_get_site_branding_lists_logo_and_favicon(client, temp_data_root):
    """GET /storage/branding resolves extensions via one list_dir, not HEAD probes."""
    from services.site_service import create_site, get_site

    # Session-scoped temp root may retain favicon from earlier upload tests
    default_images = temp_data_root / "content" / "sites" / "default" / "assets" / "images"
    if default_images.exists():
        shutil.rmtree(default_images)

    sid = "brand-wiki"
    if get_site(sid) is None:
        create_site(sid, "Brand Wiki")

    site_images = temp_data_root / "content" / "sites" / sid / "assets" / "images"
    site_images.mkdir(parents=True, exist_ok=True)
    (site_images / "logo.svg").write_bytes(b"<svg></svg>")
    (site_images / "favicon.ico").write_bytes(b"ico")
    (site_images / "readme.txt").write_text("ignore")

    empty = client.get("/api/storage/branding", headers={"X-Pen-Site-Id": "default"})
    assert empty.status_code == 200
    assert empty.json()["site_id"] == "default"
    assert empty.json()["logo"] is None
    assert empty.json()["favicon"] is None

    res = client.get("/api/storage/branding", headers={"X-Pen-Site-Id": sid})
    assert res.status_code == 200
    body = res.json()
    assert body["site_id"] == sid
    assert body["logo"] == f"/api/assets/raw/sites/{sid}/assets/images/logo.svg"
    assert body["favicon"] == f"/api/assets/raw/sites/{sid}/assets/images/favicon.ico"