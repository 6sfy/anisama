"""Anisama — multi-source anime scraping, search, resolution, and CLI.

Usage::

    # Core library
    from anisama import cache, search, resolver
    from anisama.scraper import anime_sama, voiranime
    from anisama.sources import SOURCES
    from anisama.config import KNOWN_DOMAINS, DEFAULT_HEADERS

    # CLI interface
    from anisama.cli.app import main
"""

__version__ = "2.1.0"
__app_name__ = "anisama"

# Convenient top-level re-exports (core)
from . import config
from . import cache
from . import search
from . import resolver
from . import sources
from . import exceptions
from . import http_client

__all__ = [
    "__version__",
    "__app_name__",
    "config",
    "cache",
    "search",
    "resolver",
    "sources",
    "exceptions",
    "http_client",
]
