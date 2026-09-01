"""SSRF guards for public HTTPS URL fetches."""

from __future__ import annotations

import ipaddress
import socket

import pytest

from services.url_safety import (
    UrlSafetyError,
    assert_public_hostname,
    canonicalize_public_https_url,
    hostname_is,
    is_blocked_ip,
)


PUBLIC_ADDRINFO = [
    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
]


def test_hostname_is_exact_and_subdomain():
    assert hostname_is("api.anthropic.com", "api.anthropic.com")
    assert hostname_is("API.Anthropic.COM.", "api.anthropic.com")
    assert hostname_is("cdn.nano-gpt.com", "nano-gpt.com")
    assert not hostname_is("evil-nano-gpt.com", "nano-gpt.com")
    assert not hostname_is("api.anthropic.com.evil.example", "api.anthropic.com")
    assert not hostname_is(None, "nano-gpt.com")
    assert not hostname_is("", "nano-gpt.com")


def test_is_blocked_ip_loopback_and_mapped():
    assert is_blocked_ip(ipaddress.ip_address("127.0.0.1"))
    assert is_blocked_ip(ipaddress.ip_address("::1"))
    assert is_blocked_ip(ipaddress.ip_address("::ffff:127.0.0.1"))
    assert is_blocked_ip(ipaddress.ip_address("169.254.169.254"))
    assert is_blocked_ip(ipaddress.ip_address("10.0.0.1"))
    assert not is_blocked_ip(ipaddress.ip_address("93.184.216.34"))


def test_assert_public_hostname_blocks_literals():
    with pytest.raises(UrlSafetyError, match="restricted"):
        assert_public_hostname("127.0.0.1")
    with pytest.raises(UrlSafetyError, match="restricted"):
        assert_public_hostname("localhost")
    with pytest.raises(UrlSafetyError, match="restricted"):
        assert_public_hostname("metadata.google.internal")
    with pytest.raises(UrlSafetyError, match="restricted"):
        assert_public_hostname("foo.internal")


def test_assert_public_hostname_blocks_private_dns(monkeypatch):
    monkeypatch.setattr(
        "services.url_safety.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))
        ],
    )
    with pytest.raises(UrlSafetyError, match="restricted"):
        assert_public_hostname("evil.example.com")


def test_canonicalize_public_https_strips_fragment_and_default_port(monkeypatch):
    monkeypatch.setattr(
        "services.url_safety.socket.getaddrinfo",
        lambda *args, **kwargs: PUBLIC_ADDRINFO,
    )
    out = canonicalize_public_https_url(
        "https://CIMD.example:443/client.json?x=1#frag",
        require_port_443=True,
    )
    assert out == "https://cimd.example/client.json?x=1"


@pytest.mark.parametrize(
    "url",
    [
        "http://cimd.example/client.json",
        "https://127.0.0.1/client.json",
        "https://localhost/client.json",
        "https://[::ffff:127.0.0.1]/client.json",
        "https://169.254.169.254/client.json",
        "https://192.168.1.1/client.json",
        "https://10.0.0.1/client.json",
        "https://metadata.google.internal/client.json",
        "https://cimd.example:8443/client.json",
        "https://user:pass@cimd.example/client.json",
        "https://foo.internal/client.json",
        "https://127.1/client.json",
    ],
)
def test_canonicalize_cimd_rejects_ssrf_targets(url, monkeypatch):
    monkeypatch.setattr(
        "services.url_safety.socket.getaddrinfo",
        lambda *args, **kwargs: PUBLIC_ADDRINFO,
    )
    with pytest.raises(UrlSafetyError):
        canonicalize_public_https_url(url, require_port_443=True)


def test_canonicalize_allows_public_ip_literal():
    out = canonicalize_public_https_url(
        "https://93.184.216.34/client.json", require_port_443=True
    )
    assert out == "https://93.184.216.34/client.json"
