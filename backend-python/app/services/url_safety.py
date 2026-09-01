"""Shared guards against fetching non-public HTTP(S) URLs (SSRF)."""

from __future__ import annotations

import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse, urlunparse

BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
    }
)
BLOCKED_HOST_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".lan",
)


class UrlSafetyError(ValueError):
    """Raised when a URL or hostname is not safe to fetch."""


def _core_ip_blocked(ip: ipaddress._BaseAddress) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    """True if *ip* (or its IPv4-mapped form) is not a public unicast address."""
    if _core_ip_blocked(ip):
        return True
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None and _core_ip_blocked(mapped):
        return True
    return False


def _parse_literal_ip(host: str) -> Optional[ipaddress._BaseAddress]:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    if ":" in host:
        return None
    try:
        packed = socket.inet_aton(host)
    except OSError:
        return None
    return ipaddress.IPv4Address(packed)


def is_blocked_hostname(hostname: Optional[str]) -> bool:
    if not hostname:
        return True
    host = hostname.lower().rstrip(".")
    if host in BLOCKED_HOSTNAMES:
        return True
    return any(host == suffix.lstrip(".") or host.endswith(suffix) for suffix in BLOCKED_HOST_SUFFIXES)


def assert_public_hostname(hostname: Optional[str]) -> None:
    """Reject hosts that are metadata, private, or resolve to a blocked address."""
    if not hostname:
        raise UrlSafetyError("Invalid URL hostname")

    host = hostname.lower().rstrip(".")
    if is_blocked_hostname(host):
        raise UrlSafetyError("URL host is restricted")

    literal = _parse_literal_ip(host)
    if literal is not None:
        if is_blocked_ip(literal):
            raise UrlSafetyError("URL host is restricted")
        return

    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UrlSafetyError(f"Could not resolve host: {host}") from exc

    if not infos:
        raise UrlSafetyError(f"Could not resolve host: {host}")

    found = False
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        found = True
        if is_blocked_ip(ip):
            raise UrlSafetyError("URL host resolves to a restricted address")
    if not found:
        raise UrlSafetyError(f"Could not resolve host: {host}")


def canonicalize_public_https_url(url: str, *, require_port_443: bool = False) -> str:
    """Parse *url* and return a canonical public HTTPS URL.

    Rejects non-HTTPS schemes, embedded credentials, blocked hosts, and
    (when ``require_port_443``) any port other than 443.
    """
    raw = (url or "").strip()
    try:
        parsed = urlparse(raw)
    except Exception as exc:
        raise UrlSafetyError("Invalid URL") from exc

    if parsed.scheme.lower() != "https":
        raise UrlSafetyError("Only HTTPS URLs are supported")
    if parsed.username or parsed.password:
        raise UrlSafetyError("URLs with embedded credentials are not supported")

    hostname = parsed.hostname
    if not hostname:
        raise UrlSafetyError("Invalid URL hostname")

    port = parsed.port
    if require_port_443 and port not in (None, 443):
        raise UrlSafetyError("URL port is not allowed")

    assert_public_hostname(hostname)

    host = hostname.lower().rstrip(".")
    try:
        ipaddress.IPv6Address(host)
        netloc = f"[{host}]"
    except ValueError:
        netloc = host
    if port not in (None, 443) and not require_port_443:
        netloc = f"{netloc}:{port}"

    return urlunparse(
        ("https", netloc, parsed.path or "", parsed.params, parsed.query, "")
    )
