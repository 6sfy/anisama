"""Tests for anisama.scraper.base module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestGetClient:
    """Test get_client() singleton."""

    def test_get_client_returns_same_instance(self):
        from anisama.http_client import get_client, close_client
        # Reset the singleton first
        close_client()
        c1 = get_client()
        c2 = get_client()
        assert c1 is c2
        # Clean up
        close_client()

    def test_get_client_returns_httpx_client(self):
        from anisama.http_client import get_client, close_client
        close_client()
        import httpx
        c = get_client()
        assert isinstance(c, httpx.Client)
        close_client()


class TestFindActiveDomain:
    """Test find_active_domain() with mocked HTTP."""

    def test_returns_none_when_all_fail(self):
        """When all HTTP requests fail, should raise DomainNotFoundError."""
        from anisama.scraper.base import find_active_domain, reset_active_domain
        from anisama.exceptions import DomainNotFoundError

        # Reset the cached domain
        reset_active_domain()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = ""
        mock_response.url = "https://example.com"
        mock_client.get.return_value = mock_response

        with patch("anisama.scraper.base.get_client", return_value=mock_client), \
             patch("anisama.scraper.base.load_domain_cache", return_value=None):
            with pytest.raises(DomainNotFoundError):
                find_active_domain()

    def test_returns_cached_domain_when_valid(self):
        """When cached domain is valid, should return it."""
        from anisama.scraper.base import find_active_domain, reset_active_domain

        reset_active_domain()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html>anime-sama catalog</html>'
        mock_response.url = "https://anime-sama.pw/"
        mock_client.get.return_value = mock_response

        with patch("anisama.scraper.base.get_client", return_value=mock_client), \
             patch("anisama.scraper.base.load_domain_cache", return_value="anime-sama.pw"), \
             patch("anisama.scraper.base.save_domain_cache"):
            result = find_active_domain()
            assert result == "anime-sama.pw"

    def test_reset_active_domain(self):
        """reset_active_domain() should clear the cached domain."""
        from anisama.scraper.base import _active_domain, reset_active_domain
        reset_active_domain()
        # After reset, the global should be None
        from anisama.scraper import base
        assert base._active_domain is None
