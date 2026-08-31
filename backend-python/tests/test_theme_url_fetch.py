"""Tests for remote theme URL resolution and download."""

from __future__ import annotations

import io
import json
import socket
import zipfile
from typing import Dict
from unittest.mock import MagicMock, patch

import httpx
import pytest


from services.theme_install_service import ThemeInvalidArchiveError, ThemeTooLargeError
from services.theme_url_fetch import (
    ThemeUrlFetchError,
    ThemeUrlUpstreamError,
    assert_public_https_host,
    download_zip_bytes,
    resolve_download_url,
)


def _build_zip(files: Dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()


def test_resolve_direct_zip_url(monkeypatch):
    monkeypatch.setattr(
        "services.theme_url_fetch.socket.getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
    )
    url = resolve_download_url("https://cdn.example.com/themes/starter.zip")
    assert url == "https://cdn.example.com/themes/starter.zip"


def test_resolve_github_git_url():
    url = resolve_download_url("https://github.com/acme/my-theme.git")
    assert url == "https://codeload.github.com/acme/my-theme/zip/HEAD"


def test_resolve_github_tree_branch():
    url = resolve_download_url("https://github.com/acme/my-theme/tree/develop")
    assert url == "https://codeload.github.com/acme/my-theme/zip/develop"


def test_resolve_github_tree_nested_ref():
    url = resolve_download_url("https://github.com/acme/my-theme/tree/feature/foo")
    assert url == "https://codeload.github.com/acme/my-theme/zip/feature%2Ffoo"


def test_resolve_gitlab_repo():
    url = resolve_download_url("https://gitlab.com/group/sub/repo.git")
    assert (
        url
        == "https://gitlab.com/group/sub/repo/-/archive/main/repo-main.zip"
    )


def test_resolve_gitlab_tree_ref():
    url = resolve_download_url("https://gitlab.com/group/repo/-/tree/develop")
    assert (
        url
        == "https://gitlab.com/group/repo/-/archive/develop/repo-develop.zip"
    )


def test_resolve_rejects_http():
    with pytest.raises(ThemeUrlFetchError, match="HTTPS"):
        resolve_download_url("http://github.com/acme/repo.git")


def test_resolve_rejects_credentials():
    with pytest.raises(ThemeUrlFetchError, match="credentials"):
        resolve_download_url("https://user:pass@github.com/acme/repo.git")


def test_resolve_rejects_unknown_host():
    with pytest.raises(ThemeUrlFetchError, match="GitHub/GitLab"):
        resolve_download_url("https://example.com/not-a-zip")


def test_assert_public_https_host_blocks_loopback():
    with pytest.raises(ThemeUrlFetchError, match="restricted"):
        assert_public_https_host("127.0.0.1")


def test_assert_public_https_host_blocks_private_dns(monkeypatch):
    monkeypatch.setattr(
        "services.theme_url_fetch.socket.getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))],
    )
    with pytest.raises(ThemeUrlFetchError, match="restricted"):
        assert_public_https_host("evil.example.com")


def _mock_stream_response(status_code: int, body: bytes, headers: dict | None = None):
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    response.iter_bytes = lambda: iter([body])
    response.__enter__ = lambda self: self
    response.__exit__ = lambda *args: None
    return response


def test_download_zip_bytes_success(monkeypatch):
    zip_bytes = _build_zip({"theme.json": "{}"})
    monkeypatch.setattr(
        "services.theme_url_fetch.socket.getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
    )

    mock_response = _mock_stream_response(200, zip_bytes)
    mock_client = MagicMock()
    mock_client.stream.return_value = mock_response
    mock_client.__enter__ = lambda self: self
    mock_client.__exit__ = lambda *args: None

    with patch("services.theme_url_fetch.httpx.Client", return_value=mock_client):
        data = download_zip_bytes("https://cdn.example.com/theme.zip")

    assert data == zip_bytes


def test_download_zip_bytes_rejects_html(monkeypatch):
    monkeypatch.setattr(
        "services.theme_url_fetch.socket.getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
    )
    mock_response = _mock_stream_response(200, b"<html>not a zip</html>")
    mock_client = MagicMock()
    mock_client.stream.return_value = mock_response
    mock_client.__enter__ = lambda self: self
    mock_client.__exit__ = lambda *args: None

    with patch("services.theme_url_fetch.httpx.Client", return_value=mock_client):
        with pytest.raises(ThemeInvalidArchiveError, match="not a zip"):
            download_zip_bytes("https://cdn.example.com/theme.zip")


def test_download_zip_bytes_rejects_oversized_content_length(monkeypatch):
    monkeypatch.setattr(
        "services.theme_url_fetch.socket.getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
    )
    mock_response = _mock_stream_response(
        200,
        b"PK",
        headers={"content-length": str(30 * 1024 * 1024)},
    )
    mock_client = MagicMock()
    mock_client.stream.return_value = mock_response
    mock_client.__enter__ = lambda self: self
    mock_client.__exit__ = lambda *args: None

    with patch("services.theme_url_fetch.httpx.Client", return_value=mock_client):
        with pytest.raises(ThemeTooLargeError, match="maximum allowed"):
            download_zip_bytes("https://cdn.example.com/theme.zip")


def test_download_zip_bytes_follows_redirect_with_ssrf_check(monkeypatch):
    zip_bytes = _build_zip({"theme.json": json.dumps({"name": "x", "slug": "x"})})
    public_ip = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
    blocked_ip = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

    def fake_getaddrinfo(host, *args, **kwargs):
        if host == "blocked.example.com":
            return blocked_ip
        return public_ip

    monkeypatch.setattr("services.theme_url_fetch.socket.getaddrinfo", fake_getaddrinfo)

    redirect_response = MagicMock()
    redirect_response.status_code = 302
    redirect_response.headers = {"location": "https://blocked.example.com/theme.zip"}
    redirect_response.iter_bytes = lambda: iter([])
    redirect_response.__enter__ = lambda self: self
    redirect_response.__exit__ = lambda *args: None

    mock_client = MagicMock()
    mock_client.stream.return_value = redirect_response
    mock_client.__enter__ = lambda self: self
    mock_client.__exit__ = lambda *args: None

    with patch("services.theme_url_fetch.httpx.Client", return_value=mock_client):
        with pytest.raises(ThemeUrlFetchError, match="restricted"):
            download_zip_bytes("https://cdn.example.com/theme.zip")


def test_download_zip_bytes_upstream_error(monkeypatch):
    monkeypatch.setattr(
        "services.theme_url_fetch.socket.getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
    )
    mock_response = _mock_stream_response(404, b"")
    mock_client = MagicMock()
    mock_client.stream.return_value = mock_response
    mock_client.__enter__ = lambda self: self
    mock_client.__exit__ = lambda *args: None

    with patch("services.theme_url_fetch.httpx.Client", return_value=mock_client):
        with pytest.raises(ThemeUrlUpstreamError, match="404"):
            download_zip_bytes("https://cdn.example.com/theme.zip")
