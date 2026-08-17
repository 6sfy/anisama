"""Tests for anisama.exceptions module."""

from __future__ import annotations

import pytest


class TestExceptionHierarchy:
    """Test exception class hierarchy."""

    def test_anisama_error_is_exception(self):
        from anisama.exceptions import AnisamaError
        assert issubclass(AnisamaError, Exception)

    def test_scraper_error_inherits(self):
        from anisama.exceptions import AnisamaError, ScraperError
        assert issubclass(ScraperError, AnisamaError)

    def test_resolver_error_inherits(self):
        from anisama.exceptions import AnisamaError, ResolverError
        assert issubclass(ResolverError, AnisamaError)

    def test_cache_error_inherits(self):
        from anisama.exceptions import AnisamaError, CacheError
        assert issubclass(CacheError, AnisamaError)

    def test_domain_not_found_inherits_scraper(self):
        from anisama.exceptions import ScraperError, DomainNotFoundError
        assert issubclass(DomainNotFoundError, ScraperError)

    def test_domain_not_found_inherits_anisama(self):
        from anisama.exceptions import AnisamaError, DomainNotFoundError
        assert issubclass(DomainNotFoundError, AnisamaError)


class TestExceptionRaising:
    """Test each exception type can be raised and caught."""

    def test_raise_anisama_error(self):
        from anisama.exceptions import AnisamaError
        with pytest.raises(AnisamaError, match="test error"):
            raise AnisamaError("test error")

    def test_raise_scraper_error(self):
        from anisama.exceptions import ScraperError
        with pytest.raises(ScraperError, match="scrape fail"):
            raise ScraperError("scrape fail")

    def test_raise_resolver_error(self):
        from anisama.exceptions import ResolverError
        with pytest.raises(ResolverError, match="resolve fail"):
            raise ResolverError("resolve fail")

    def test_raise_cache_error(self):
        from anisama.exceptions import CacheError
        with pytest.raises(CacheError, match="cache fail"):
            raise CacheError("cache fail")

    def test_raise_domain_not_found(self):
        from anisama.exceptions import DomainNotFoundError
        with pytest.raises(DomainNotFoundError, match="no domain"):
            raise DomainNotFoundError("no domain")

    def test_catch_scraper_as_anisama(self):
        """ScraperError can be caught as AnisamaError."""
        from anisama.exceptions import AnisamaError, ScraperError
        with pytest.raises(AnisamaError):
            raise ScraperError("caught by base")

    def test_catch_domain_not_found_as_scraper(self):
        """DomainNotFoundError can be caught as ScraperError."""
        from anisama.exceptions import ScraperError, DomainNotFoundError
        with pytest.raises(ScraperError):
            raise DomainNotFoundError("caught by parent")

    def test_exception_message(self):
        from anisama.exceptions import AnisamaError
        e = AnisamaError("hello")
        assert str(e) == "hello"
