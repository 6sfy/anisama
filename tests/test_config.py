"""Tests for anisama.config module."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest


class TestConstants:
    """Test that all config constants are defined and have expected types."""

    def test_known_domains_defined(self):
        from anisama.config import KNOWN_DOMAINS
        assert isinstance(KNOWN_DOMAINS, list)
        assert len(KNOWN_DOMAINS) > 0
        for d in KNOWN_DOMAINS:
            assert isinstance(d, str)
            assert "." in d  # all domains contain a dot

    def test_known_domains_contents(self):
        from anisama.config import KNOWN_DOMAINS
        assert "anime-sama.to" in KNOWN_DOMAINS
        assert "anime-sama.pw" in KNOWN_DOMAINS

    def test_default_headers_defined(self):
        from anisama.config import DEFAULT_HEADERS
        assert isinstance(DEFAULT_HEADERS, dict)
        assert "User-Agent" in DEFAULT_HEADERS
        assert "Accept" in DEFAULT_HEADERS
        assert "Accept-Language" in DEFAULT_HEADERS

    def test_voiranime_headers_defined(self):
        from anisama.config import VOIRANIME_HEADERS
        assert isinstance(VOIRANIME_HEADERS, dict)
        assert "Referer" in VOIRANIME_HEADERS

    def test_resolver_headers_defined(self):
        from anisama.config import RESOLVER_HEADERS
        assert isinstance(RESOLVER_HEADERS, dict)
        assert "User-Agent" in RESOLVER_HEADERS

    def test_provider_url_defined(self):
        from anisama.config import PROVIDER_URL
        assert isinstance(PROVIDER_URL, str)
        assert PROVIDER_URL.startswith("https://")

    def test_voiranime_domain_defined(self):
        from anisama.config import VOIRANIME_DOMAIN
        assert isinstance(VOIRANIME_DOMAIN, str)
        assert "." in VOIRANIME_DOMAIN

    def test_cache_max_age_hours(self):
        from anisama.config import CACHE_MAX_AGE_HOURS
        assert isinstance(CACHE_MAX_AGE_HOURS, int)
        assert CACHE_MAX_AGE_HOURS > 0

    def test_request_timeout(self):
        from anisama.config import REQUEST_TIMEOUT
        assert isinstance(REQUEST_TIMEOUT, int)
        assert REQUEST_TIMEOUT > 0

    def test_catalog_remote_url(self):
        from anisama.config import CATALOG_REMOTE_URL
        assert isinstance(CATALOG_REMOTE_URL, str)
        assert CATALOG_REMOTE_URL.startswith("https://")

    def test_package_dir(self):
        from anisama.config import PACKAGE_DIR
        assert isinstance(PACKAGE_DIR, Path)
        assert PACKAGE_DIR.exists()

    def test_project_dir(self):
        from anisama.config import PROJECT_DIR
        assert isinstance(PROJECT_DIR, Path)

    def test_path_constants_are_paths(self):
        from anisama.config import CATALOG_FILE, SETTINGS_FILE, HISTORY_FILE, DOMAIN_CACHE_FILE
        assert isinstance(CATALOG_FILE, Path)
        assert isinstance(SETTINGS_FILE, Path)
        assert isinstance(HISTORY_FILE, Path)
        assert isinstance(DOMAIN_CACHE_FILE, Path)


class TestDataDirConfigurable:
    """Test DATA_DIR is configurable via ANISAMA_DATA_DIR env var."""

    def test_data_dir_from_env(self, tmp_data_dir):
        import anisama.config
        assert anisama.config.DATA_DIR == tmp_data_dir

    def test_data_dir_fallback_default(self, monkeypatch):
        """When ANISAMA_DATA_DIR is not set, DATA_DIR falls back to default."""
        monkeypatch.delenv("ANISAMA_DATA_DIR", raising=False)
        import anisama.config
        importlib.reload(anisama.config)
        expected = anisama.config.PROJECT_DIR / "data"
        assert anisama.config.DATA_DIR == expected

    def test_data_dir_paths_use_env(self, tmp_data_dir):
        """Path constants should be under the configured DATA_DIR."""
        import anisama.config
        assert anisama.config.CATALOG_FILE == tmp_data_dir / "catalog.json"
        assert anisama.config.SETTINGS_FILE == tmp_data_dir / "settings.json"
        assert anisama.config.HISTORY_FILE == tmp_data_dir / "history.json"
        assert anisama.config.DOMAIN_CACHE_FILE == tmp_data_dir / "active_domain.txt"
