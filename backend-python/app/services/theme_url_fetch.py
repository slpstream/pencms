"""Fetch theme .zip archives from HTTPS URLs (direct or GitHub/GitLab repos).

Rewrites public GitHub/GitLab repository URLs to archive zipballs, then
downloads with SSRF protections and size limits before handing bytes to
``install_from_zip``.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple
from urllib.parse import quote, urljoin, urlparse

import httpx

from services.theme_install_service import (
    MAX_UPLOAD_BYTES,
    ThemeInstallError,
    ThemeInvalidArchiveError,
    ThemeTooLargeError,
)
from services.url_safety import UrlSafetyError, assert_public_hostname

logger = logging.getLogger("pencms.theme_url_fetch")

GITHUB_HOSTS = frozenset({"github.com", "www.github.com"})
GITLAB_HOSTS = frozenset({"gitlab.com", "www.gitlab.com"})

MAX_REDIRECTS = 3
CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 60.0
DEFAULT_GITHUB_REF = "HEAD"
DEFAULT_GITLAB_REF = "main"


class ThemeUrlFetchError(ThemeInstallError):
    """Raised when a remote theme URL cannot be fetched."""


class ThemeUrlTimeoutError(ThemeUrlFetchError):
    """Raised when a remote fetch times out."""


class ThemeUrlUpstreamError(ThemeUrlFetchError):
    """Raised when the remote server returns an error response."""


def _redact_url(url: str) -> str:
    """Return a log-safe URL with credentials stripped."""
    parsed = urlparse(url)
    if not parsed.username and not parsed.password:
        return url
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    netloc = host
    return parsed._replace(netloc=netloc).geturl()


def assert_public_https_host(hostname: Optional[str]) -> None:
    """Reject hosts that resolve to private or metadata addresses."""
    try:
        assert_public_hostname(hostname)
    except UrlSafetyError as exc:
        raise ThemeUrlFetchError(str(exc)) from exc


def _parse_github_repo(path: str) -> Optional[Tuple[str, str, str]]:
    """Return (owner, repo, ref) when path is a GitHub repo URL."""
    segments = [segment for segment in path.split("/") if segment]
    if len(segments) < 2:
        return None

    owner, repo = segments[0], segments[1]
    if repo.endswith(".git"):
        repo = repo[:-4]

    ref = DEFAULT_GITHUB_REF
    if len(segments) >= 4 and segments[2] == "tree":
        ref = "/".join(segments[3:]) or DEFAULT_GITHUB_REF

    return owner, repo, ref


def _parse_gitlab_repo(path: str) -> Optional[Tuple[str, str]]:
    """Return (project_path, ref) for a GitLab repo URL."""
    if "/-/" not in path:
        project_path = path.strip("/")
        if not project_path:
            return None
        if project_path.endswith(".git"):
            project_path = project_path[:-4]
        return project_path, DEFAULT_GITLAB_REF

    project_path, remainder = path.split("/-/", 1)
    project_path = project_path.strip("/")
    if not project_path:
        return None
    if project_path.endswith(".git"):
        project_path = project_path[:-4]

    ref = DEFAULT_GITLAB_REF
    remainder = remainder.strip("/")
    if remainder.startswith("tree/"):
        ref = "/".join(remainder.split("/")[1:]) or DEFAULT_GITLAB_REF

    return project_path, ref


def _github_archive_url(host: str, owner: str, repo: str, ref: str) -> str:
    safe_host = "codeload.github.com"
    encoded_ref = quote(ref, safe="")
    return f"https://{safe_host}/{owner}/{repo}/zip/{encoded_ref}"


def _gitlab_archive_url(host: str, project_path: str, ref: str) -> str:
    repo_name = project_path.rstrip("/").split("/")[-1]
    encoded_ref = quote(ref, safe="")
    ref_file = ref.replace("/", "-")
    return (
        f"https://{host}/{project_path}/-/archive/{encoded_ref}/"
        f"{repo_name}-{ref_file}.zip"
    )


def resolve_download_url(url: str) -> str:
    """Normalize a user URL into a direct HTTPS zip download URL."""
    raw = (url or "").strip()
    if not raw:
        raise ThemeUrlFetchError("URL is required")

    parsed = urlparse(raw)
    if parsed.scheme != "https":
        raise ThemeUrlFetchError("Only HTTPS URLs are supported")
    if parsed.username or parsed.password:
        raise ThemeUrlFetchError("URLs with embedded credentials are not supported")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ThemeUrlFetchError("Invalid URL hostname")

    path = parsed.path or ""
    path_lower = path.lower()
    if path_lower.endswith(".zip"):
        assert_public_https_host(hostname)
        return raw

    if hostname in GITHUB_HOSTS:
        repo = _parse_github_repo(path)
        if not repo:
            raise ThemeUrlFetchError(
                "GitHub URL must point to a repository or .zip archive"
            )
        owner, repo_name, ref = repo
        return _github_archive_url(hostname, owner, repo_name, ref)

    if hostname in GITLAB_HOSTS:
        repo = _parse_gitlab_repo(path)
        if not repo:
            raise ThemeUrlFetchError(
                "GitLab URL must point to a repository or .zip archive"
            )
        project_path, ref = repo
        return _gitlab_archive_url(hostname, project_path, ref)

    raise ThemeUrlFetchError(
        "URL must be a direct .zip download or a public GitHub/GitLab HTTPS repository"
    )


def _validate_redirect_target(location: str, base_url: str) -> str:
    target = urljoin(base_url, location)
    parsed = urlparse(target)
    if parsed.scheme != "https":
        raise ThemeUrlFetchError("Redirect target must use HTTPS")
    if parsed.username or parsed.password:
        raise ThemeUrlFetchError("Redirect target must not include credentials")
    assert_public_https_host(parsed.hostname)
    return target


def download_zip_bytes(url: str) -> bytes:
    """Download a zip archive from ``url`` with redirect and size checks."""
    current = url
    timeout = httpx.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT)

    for redirect_count in range(MAX_REDIRECTS + 1):
        assert_public_https_host(urlparse(current).hostname)
        try:
            with httpx.Client(timeout=timeout, follow_redirects=False) as client:
                with client.stream("GET", current) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        if redirect_count >= MAX_REDIRECTS:
                            raise ThemeUrlFetchError("Too many redirects")
                        location = response.headers.get("location")
                        if not location:
                            raise ThemeUrlUpstreamError(
                                "Remote server returned a redirect without a location"
                            )
                        current = _validate_redirect_target(location, current)
                        continue

                    if response.status_code != 200:
                        raise ThemeUrlUpstreamError(
                            f"Remote server returned HTTP {response.status_code}"
                        )

                    content_length = response.headers.get("content-length")
                    if content_length is not None:
                        try:
                            declared = int(content_length)
                        except ValueError:
                            declared = None
                        if declared is not None and declared > MAX_UPLOAD_BYTES:
                            raise ThemeTooLargeError(
                                f"Remote archive is {declared} bytes; "
                                f"maximum allowed is {MAX_UPLOAD_BYTES} bytes"
                            )

                    chunks: list[bytes] = []
                    total = 0
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > MAX_UPLOAD_BYTES:
                            raise ThemeTooLargeError(
                                f"Remote archive exceeds {MAX_UPLOAD_BYTES} bytes"
                            )
                        chunks.append(chunk)

                    data = b"".join(chunks)
                    if len(data) < 2 or data[:2] != b"PK":
                        raise ThemeInvalidArchiveError(
                            "Downloaded file is not a zip archive"
                        )
                    logger.info(
                        "Fetched theme archive (%s bytes) from %s",
                        len(data),
                        _redact_url(current),
                    )
                    return data
        except httpx.TimeoutException as exc:
            raise ThemeUrlTimeoutError("Timed out fetching remote theme archive") from exc
        except httpx.HTTPError as exc:
            raise ThemeUrlUpstreamError(
                f"Failed to fetch remote theme archive: {exc}"
            ) from exc

    raise ThemeUrlFetchError("Too many redirects")
