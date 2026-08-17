"""Custom exceptions for the anisama library."""

from __future__ import annotations


class AnisamaError(Exception):
    """Base exception for all anisama errors."""
    pass


class ScraperError(AnisamaError):
    """Error raised by scrapers."""
    pass


class ResolverError(AnisamaError):
    """Error raised by video URL resolvers."""
    pass


class CacheError(AnisamaError):
    """Error raised by cache/catalog operations."""
    pass


class DomainNotFoundError(ScraperError):
    """Error raised when no active domain can be found."""
    pass
