"""Unified source registry for all anime sources.

Provides a ``Source`` dataclass and a ``SOURCES`` dict that maps
source names to their catalog, search, episodes, and resolve
functions.  Downstream packages (anisama-cli, anisama-api) can
iterate over ``SOURCES`` to treat all scrapers uniformly.

Usage::

    from anisama.sources import SOURCES

    src = SOURCES["anime-sama"]
    catalog = src.catalog(domain="anime-sama.to")
    seasons = src.episodes(anime_url)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any, Optional


@dataclass
class Source:
    """A single anime source with its associated functions."""

    name: str
    catalog: Callable[..., list[dict[str, Any]]]
    search: Callable[..., list[dict[str, Any]]]
    episodes: Callable[..., list[dict[str, Any]]]
    resolve: Callable[..., Optional[dict[str, Any]]]
    needs_playwright: bool = False
    description: str = ""


# Lazy imports to avoid circular deps at import time

def _anime_sama_catalog(**kwargs):
    from .scraper.anime_sama import anime_sama_catalog
    return anime_sama_catalog(**kwargs)


def _anime_sama_search(query, **kwargs):
    from .scraper.anime_sama import search_online
    from .scraper.base import find_active_domain
    domain = kwargs.get("domain") or find_active_domain()
    return search_online(domain, query)


def _anime_sama_episodes(url, **kwargs):
    from .scraper.anime_sama import get_episodes
    return get_episodes(url)


def _anime_sama_resolve(url, **kwargs):
    from .resolver import resolve_url
    return resolve_url(url)


def _voiranime_catalog(**kwargs):
    from .scraper.voiranime import voiranime_catalog
    return voiranime_catalog(skip_slugs=kwargs.get("skip_slugs"))


def _voiranime_search(query, **kwargs):
    from .search import search_voiranime
    return search_voiranime(query)


def _voiranime_episodes(season_url, **kwargs):
    from .scraper.voiranime import voiranime_get_episodes
    return voiranime_get_episodes(season_url, lang=kwargs.get("lang"))


def _voiranime_resolve(episode_url, **kwargs):
    from .resolver import resolve_voiranime_episode
    return resolve_voiranime_episode(episode_url, kwargs.get("lang", "vostfr"))


def _myfluneo_catalog(**kwargs):
    from .scraper.myfluneo import myfluneo_catalog
    return myfluneo_catalog()


def _myfluneo_search(query, **kwargs):
    from .scraper.myfluneo import myfluneo_search
    return myfluneo_search(query)


def _myfluneo_episodes(url, **kwargs):
    from .scraper.myfluneo import myfluneo_episodes
    return myfluneo_episodes(url)


def _myfluneo_resolve(url, **kwargs):
    from .scraper.myfluneo import myfluneo_resolve
    return myfluneo_resolve(url)


def _animesultra_catalog(**kwargs):
    from .scraper.animesultra import animesultra_catalog
    return animesultra_catalog()


def _animesultra_search(query, **kwargs):
    from .scraper.animesultra import animesultra_search
    return animesultra_search(query)


def _animesultra_episodes(url, **kwargs):
    from .scraper.animesultra import animesultra_episodes
    return animesultra_episodes(url)


def _animesultra_resolve(url, **kwargs):
    from .scraper.animesultra import animesultra_resolve
    return animesultra_resolve(url)


def _frenchanime_catalog(**kwargs):
    from .scraper.frenchanime import frenchanime_catalog
    return frenchanime_catalog()


def _frenchanime_search(query, **kwargs):
    from .scraper.frenchanime import frenchanime_search
    return frenchanime_search(query)


def _frenchanime_episodes(url, **kwargs):
    from .scraper.frenchanime import frenchanime_episodes
    return frenchanime_episodes(url)


def _frenchanime_resolve(url, **kwargs):
    from .scraper.frenchanime import frenchanime_resolve
    return frenchanime_resolve(url)


def _animoflix_catalog(**kwargs):
    from .scraper.animoflix import animoflix_catalog
    return animoflix_catalog()


def _animoflix_search(query, **kwargs):
    from .scraper.animoflix import animoflix_search
    return animoflix_search(query)


def _animoflix_episodes(url, **kwargs):
    from .scraper.animoflix import animoflix_episodes
    return animoflix_episodes(url)


def _animoflix_resolve(url, **kwargs):
    from .scraper.animoflix import animoflix_resolve
    return animoflix_resolve(url)


SOURCES: dict[str, Source] = {
    "anime-sama": Source(
        name="anime-sama",
        catalog=_anime_sama_catalog,
        search=_anime_sama_search,
        episodes=_anime_sama_episodes,
        resolve=_anime_sama_resolve,
        needs_playwright=False,
        description="Anime-Sama — primary VOSTFR/VF source",
    ),
    "voiranime": Source(
        name="voiranime",
        catalog=_voiranime_catalog,
        search=_voiranime_search,
        episodes=_voiranime_episodes,
        resolve=_voiranime_resolve,
        needs_playwright=False,
        description="Voiranime — secondary VOSTFR/VF source",
    ),
    "myfluneo": Source(
        name="myfluneo",
        catalog=_myfluneo_catalog,
        search=_myfluneo_search,
        episodes=_myfluneo_episodes,
        resolve=_myfluneo_resolve,
        needs_playwright=True,
        description="MyFluneo — VOSTFR source requiring Playwright",
    ),
    "animesultra": Source(
        name="animesultra",
        catalog=_animesultra_catalog,
        search=_animesultra_search,
        episodes=_animesultra_episodes,
        resolve=_animesultra_resolve,
        needs_playwright=False,
        description="AnimesUltra — VOSTFR/VF sitemap-based source",
    ),
    "frenchanime": Source(
        name="frenchanime",
        catalog=_frenchanime_catalog,
        search=_frenchanime_search,
        episodes=_frenchanime_episodes,
        resolve=_frenchanime_resolve,
        needs_playwright=False,
        description="FrenchAnime — VOSTFR/VF HTML scraping source",
    ),
    "animoflix": Source(
        name="animoflix",
        catalog=_animoflix_catalog,
        search=_animoflix_search,
        episodes=_animoflix_episodes,
        resolve=_animoflix_resolve,
        needs_playwright=True,
        description="AnimoFlix — VOSTFR source with Playwright fallback",
    ),
}


def get_sources(needs_playwright: bool | None = None) -> list[Source]:
    """Return sources, optionally filtered by Playwright requirement.

    Args:
        needs_playwright: If None, return all. If True, only Playwright
            sources. If False, only non-Playwright sources.
    """
    if needs_playwright is None:
        return list(SOURCES.values())
    return [s for s in SOURCES.values() if s.needs_playwright == needs_playwright]
