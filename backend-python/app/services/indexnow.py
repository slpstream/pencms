"""Optional IndexNow ping after a successful public HTTPS publish.

Bing / Yandex / Seznam / Naver via api.indexnow.org. Not Google.
Never raises into the publish pipeline.
"""

from __future__ import annotations

import ipaddress
import logging
import re
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence
from urllib.parse import urlparse

import httpx

from services.site_service import INDEXNOW_KEY_RE, get_site

logger = logging.getLogger("pencms.indexnow")

INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
SKIP_HOST_SUFFIXES = (
    ".localhost",
    ".local",
    ".lan",
    ".internal",
    ".test",
    ".example",
    ".invalid",
)


def is_skipped_host(host: Optional[str]) -> bool:
    if not host:
        return True
    raw = host.strip().lower().strip("[]")
    if raw in {"localhost", "::1"}:
        return True
    try:
        addr = ipaddress.ip_address(raw)
        return bool(addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved)
    except ValueError:
        pass
    for suffix in SKIP_HOST_SUFFIXES:
        bare = suffix.lstrip(".")
        if raw == bare or raw.endswith(suffix):
            return True
    return False


def is_public_https_url(url: Optional[str]) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    if (parsed.scheme or "").lower() != "https":
        return False
    return not is_skipped_host(parsed.hostname)


def html_relpaths_to_urls(origin: str, rels: Iterable[str]) -> List[str]:
    """Map dist relative paths of HTML files to public URLs. Skip md/txt mirrors."""
    origin = origin.rstrip("/")
    urls: List[str] = []
    for rel in rels:
        path = str(rel).replace("\\", "/").lstrip("/")
        if not path.lower().endswith(".html"):
            continue
        if path.lower() == "index.html":
            urls.append(origin + "/")
            continue
        if path.lower().endswith("/index.html"):
            urls.append(origin + "/" + path[: -len("index.html")])
            continue
        urls.append(origin + "/" + path)
    # stable unique
    seen = set()
    out: List[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def sitemap_html_locs(xml: str) -> List[str]:
    locs = re.findall(r"<loc>\s*([^<]+)\s*</loc>", xml, flags=re.I)
    out: List[str] = []
    seen = set()
    for raw in locs:
        url = raw.strip()
        if not url:
            continue
        path = urlparse(url).path or ""
        if re.search(r"\.(md|txt|xml|jsonl|json)$", path, flags=re.I):
            continue
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def ping_indexnow(
    host: str,
    key: str,
    key_location: str,
    url_list: Sequence[str],
    *,
    client: Optional[httpx.Client] = None,
) -> bool:
    """POST IndexNow. Returns True on HTTP 2xx. Does not raise."""
    urls = [u for u in url_list if isinstance(u, str) and u.strip()]
    if not urls or not INDEXNOW_KEY_RE.fullmatch(key):
        return False
    body = {
        "host": host,
        "key": key,
        "keyLocation": key_location,
        "urlList": urls[:10000],
    }
    close = False
    http = client
    if http is None:
        http = httpx.Client(timeout=8.0)
        close = True
    try:
        resp = http.post(INDEXNOW_ENDPOINT, json=body)
        return 200 <= resp.status_code < 300
    except Exception as exc:  # noqa: BLE001 — ping must never break publish
        logger.warning("IndexNow ping failed: %s", exc)
        return False
    finally:
        if close:
            http.close()


def maybe_ping_indexnow(
    site_id: str,
    public_url: Optional[str],
    dist_dir: Path,
    changed_rels: Optional[Sequence[str]] = None,
    *,
    log_line: Optional[Callable[[str], None]] = None,
    client: Optional[httpx.Client] = None,
) -> str:
    """Ping after deploy when IndexNow is enabled for a public https host.

    Returns a short status string. Never raises.
    """
    def _log(msg: str) -> None:
        if log_line:
            log_line(msg)
        logger.info(msg)

    try:
        record = get_site(site_id)
        if record is None or not record.indexnow_enabled:
            return "skipped:disabled"
        key = (record.indexnow_key or "").strip()
        if not INDEXNOW_KEY_RE.fullmatch(key):
            _log("IndexNow skipped: missing or invalid key.")
            return "skipped:key"
        if not is_public_https_url(public_url):
            _log("IndexNow skipped: host is not public https.")
            return "skipped:host"
        parsed = urlparse(public_url)
        host = parsed.hostname or ""
        origin = f"https://{host}"
        if parsed.port and parsed.port != 443:
            origin += f":{parsed.port}"
        urls: List[str] = []
        if changed_rels:
            urls = html_relpaths_to_urls(origin, changed_rels)
        if not urls:
            sitemap = dist_dir / "sitemap.xml"
            if sitemap.is_file():
                urls = sitemap_html_locs(sitemap.read_text(encoding="utf-8", errors="replace"))
        if not urls:
            _log("IndexNow skipped: no HTML URLs to submit.")
            return "skipped:urls"
        key_location = f"{origin}/{key}.txt"
        _log(f"IndexNow ping ({len(urls)} URL(s))…")
        ok = ping_indexnow(host, key, key_location, urls, client=client)
        if ok:
            _log("IndexNow ping accepted.")
            return "ok"
        _log("IndexNow ping failed (publish continues).")
        return "failed"
    except Exception as exc:  # noqa: BLE001
        _log(f"IndexNow ping failed (publish continues): {exc}")
        return "failed"
