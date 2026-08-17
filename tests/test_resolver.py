"""Tests for anisama.resolver module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestResolverMap:
    """Test RESOLVER_MAP has expected hosts."""

    def test_resolver_map_has_expected_hosts(self):
        from anisama.resolver import RESOLVER_MAP
        expected_hosts = [
            "vidmoly.to",
            "vidmoly.net",
            "smoothpre.com",
            "vidhide.com",
            "streamwish.com",
            "sendvid.com",
            "oneupload.to",
            "video.sibnet.ru",
            "minochinos.com",
            "embed4me.com",
            "lpayer.embed4me.com",
        ]
        for host in expected_hosts:
            assert host in RESOLVER_MAP, f"Missing host: {host}"

    def test_resolver_map_values_are_callable(self):
        from anisama.resolver import RESOLVER_MAP
        for host, func in RESOLVER_MAP.items():
            assert callable(func), f"Resolver for {host} is not callable"


class TestResolveUrl:
    """Test resolve_url() dispatch."""

    def test_returns_raw_for_unknown_host(self):
        from anisama.resolver import resolve_url
        # Mock the generic resolver and yt-dlp to also return None
        with patch("anisama.resolver.resolve_generic", return_value=None):
            result = resolve_url("https://unknown-host.example.com/embed/123")
            assert result["type"] == "raw"
            assert "unknown-host.example.com" in result["url"]

    def test_returns_raw_url_preserved(self):
        from anisama.resolver import resolve_url
        url = "https://unknown-host.example.com/embed/123"
        with patch("anisama.resolver.resolve_generic", return_value=None):
            result = resolve_url(url)
            assert result["url"] == url


class TestToBaseN:
    """Test _to_base_n() conversion."""

    def test_zero(self):
        from anisama.resolver import _to_base_n
        assert _to_base_n(0, 10) == "0"

    def test_base_10_values(self):
        """In base 10, digits are 0-9, so 10 is '10' (two digits)."""
        from anisama.resolver import _to_base_n
        assert _to_base_n(0, 10) == "0"
        assert _to_base_n(5, 10) == "5"
        assert _to_base_n(9, 10) == "9"
        assert _to_base_n(10, 10) == "10"  # 10 in base-10 is "10"

    def test_base_36(self):
        from anisama.resolver import _to_base_n
        assert _to_base_n(0, 36) == "0"
        assert _to_base_n(1, 36) == "1"
        assert _to_base_n(35, 36) == "z"

    def test_base_62(self):
        from anisama.resolver import _to_base_n
        assert _to_base_n(10, 62) == "a"
        assert _to_base_n(36, 62) == "A"

    def test_roundtrip_small(self):
        from anisama.resolver import _to_base_n
        # Verify base-10-like for small numbers
        assert _to_base_n(5, 10) == "5"
        assert _to_base_n(9, 10) == "9"

    def test_base_10_uses_digits_only(self):
        """Base 10 should only use 0-9 chars."""
        from anisama.resolver import _to_base_n
        result = _to_base_n(15, 10)
        assert result == "15"


class TestDecodePack:
    """Test _decode_pack() unpacking."""

    def test_simple_decode(self):
        from anisama.resolver import _decode_pack
        # p="hello 0 world", a=10, c=1, k="test"
        # In base 10, index 0 = "0", so "0" gets replaced by "test"
        result = _decode_pack("hello 0 world", 10, 1, "test")
        assert result == "hello test world"

    def test_no_replacement_when_empty_key(self):
        from anisama.resolver import _decode_pack
        # When k_str has empty entry, no replacement happens
        result = _decode_pack("hello world", 10, 1, "")
        assert result == "hello world"

    def test_multiple_replacements(self):
        from anisama.resolver import _decode_pack
        # a=10: base-10 digits 0-9. c=3 means 3 keys.
        # index 0 -> "0", index 1 -> "1", index 2 -> "2"
        # Replace in reverse: 2->"two", 1->"one", 0->"zero"
        result = _decode_pack("0 and 1 and 2", 10, 3, "zero|one|two")
        assert result == "zero and one and two"
