"""IndexNow eligibility, URL mapping, and never-fail ping."""

from __future__ import annotations

from pathlib import Path

import httpx

from services.indexnow import (
    html_relpaths_to_urls,
    is_public_https_url,
    is_skipped_host,
    maybe_ping_indexnow,
    ping_indexnow,
    sitemap_html_locs,
)


def test_skip_localhost_rfc1918_and_special_use():
    assert is_skipped_host("localhost")
    assert is_skipped_host("127.0.0.1")
    assert is_skipped_host("10.0.0.4")
    assert is_skipped_host("192.168.1.9")
    assert is_skipped_host("example.test")
    assert is_skipped_host("preview.local")
    assert not is_skipped_host("example.com")
    assert not is_public_https_url("http://example.com/")
    assert not is_public_https_url("https://localhost/")
    assert is_public_https_url("https://example.com/")


def test_html_relpaths_to_urls_skips_markdown():
    origin = "https://example.com"
    urls = html_relpaths_to_urls(
        origin,
        [
            "index.html",
            "about/index.html",
            "about.md",
            "llms.txt",
            "about/index.md",
        ],
    )
    assert urls == ["https://example.com/", "https://example.com/about/"]


def test_sitemap_html_locs_skip_mirrors():
    xml = """
    <urlset>
      <url><loc>https://example.com/post/</loc></url>
      <url><loc>https://example.com/post.md</loc></url>
      <url><loc>https://example.com/llms.txt</loc></url>
    </urlset>
    """
    assert sitemap_html_locs(xml) == ["https://example.com/post/"]


def test_ping_indexnow_posts_payload():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = request.read()
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        ok = ping_indexnow(
            "example.com",
            "a" * 32,
            "https://example.com/" + "a" * 32 + ".txt",
            ["https://example.com/"],
            client=client,
        )
    assert ok is True
    assert "api.indexnow.org" in captured["url"]


def test_ping_indexnow_failure_does_not_raise():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        assert ping_indexnow(
            "example.com",
            "a" * 32,
            "https://example.com/key.txt",
            ["https://example.com/"],
            client=client,
        ) is False


def test_maybe_ping_skips_private_and_survives_errors(authed_client, tmp_path):
    from services.site_service import ensure_sites_initialized, update_site

    ensure_sites_initialized()
    update_site("default", indexnow_enabled=True)
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "sitemap.xml").write_text(
        "<urlset><url><loc>https://example.com/</loc></url></urlset>"
    )
    assert maybe_ping_indexnow(
        "default",
        "https://127.0.0.1/",
        dist,
    ) == "skipped:host"

    def boom(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("boom")

    transport = httpx.MockTransport(boom)
    with httpx.Client(transport=transport) as client:
        status = maybe_ping_indexnow(
            "default",
            "https://example.com/",
            dist,
            ["about/index.html"],
            client=client,
        )
    assert status == "failed"


def test_maybe_ping_prefers_changed_html(authed_client, tmp_path):
    from services.site_service import ensure_sites_initialized, update_site

    ensure_sites_initialized()
    update_site("default", indexnow_enabled=True, indexnow_key="b" * 32)
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "sitemap.xml").write_text(
        "<urlset><url><loc>https://example.com/from-sitemap/</loc></url></urlset>"
    )
    posted = {}

    def handler(request: httpx.Request) -> httpx.Response:
        posted["body"] = request.read().decode()
        return httpx.Response(200, text="ok")

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        status = maybe_ping_indexnow(
            "default",
            "https://example.com/",
            dist,
            ["about/index.html", "about.md"],
            client=client,
        )
    assert status == "ok"
    assert "https://example.com/about/" in posted["body"]
    assert "from-sitemap" not in posted["body"]
    assert ".md" not in posted["body"]
