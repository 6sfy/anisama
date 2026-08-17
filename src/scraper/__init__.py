"""Scraper subpackage — imports and re-exports all scrapers for convenience.

Usage::

    from anisama.scraper import anime_sama, voiranime
    from anisama.scraper import myfluneo, animesultra, frenchanime, animoflix
    from anisama.scraper.base import find_active_domain, get_client
"""

from . import base
from . import anime_sama
from . import voiranime
from . import myfluneo
from . import animesultra
from . import frenchanime
from . import animoflix

# Re-export key functions for backward compatibility
from .base import find_active_domain

__all__ = [
    "base",
    "anime_sama",
    "voiranime",
    "myfluneo",
    "animesultra",
    "frenchanime",
    "animoflix",
    "find_active_domain",
]
