"""Franime scraper (franime.fr) — API-based source for search, episodes, resolution.

Uses the public FRAnime API: https://api.franime.fr/api/
  - GET /animes                               -> Full catalog
  - GET /anime-seasons/{id}/{season}          -> Episode details with _id
  - GET /anime/{id}/{s}/{ep}/{lang}/{lecteur} -> Video URL (embed/player URL)

Supported lecteurs: filemoon, sibnet, sendvid, vidmoly, vk
Supported languages: vo (VOSTFR), vf (VF)

Usage:
    from anisama.scraper import franime

    scraper = franime.FRAnimeScraper()

    # Search
    results = scraper.search("dragon ball")
    # -> [{"id": 199, "title": "Dragon Ball", "score": 150, ...}, ...]

    # Get episode details
    episodes = scraper.get_episodes(4394, season=1)
    # -> [{"number": 1, "title": "...", "thumbnail": "...", "_id": "..."}, ...]

    # Get available players for an episode
    lecteurs = scraper.get_available_lecteurs(4394, season=1, episode=1)
    # -> {"vo": ["vk", "filemoon", "vidmoly"], "vf": [...]}

    # Resolve a specific video URL
    url = scraper.get_video_url(4394, 1, 1, "vo", "filemoon")
    # -> "https://video.sibnet.ru/shell.php?videoid=956101"

    # Auto-resolve: try all lecteurs until one works
    result = scraper.resolve_episode(4394, season=1, episode=1, lang="vo")
    # -> {"url": "https://video.sibnet.ru/...", "lecteur": "filemoon", ...}

Project-style functions (catalog / search / episodes / resolve) are also
provided to integrate with the unified source registry:
    entries = franime.franime_catalog()
    results = franime.franime_search("dragon ball")
    eps = franime.franime_episodes("franime://4394/1/1")
    video = franime.franime_resolve(eps[0]["url"])
"""

import json
import re
import time

from ..config import REQUEST_TIMEOUT
from ..http_client import get_client

API_BASE = "https://api.franime.fr/api/"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://franime.fr",
    "Referer": "https://franime.fr/",
}

# Preferred lecteur order (most reliable first)
LECTEUR_PRIORITY = ["filemoon", "vk", "vidmoly", "sibnet", "sendvid"]


class FRAnimeScraper:
    """Scraper for FRAnime (franime.fr) using their public API."""

    API_BASE = API_BASE

    def __init__(self, timeout: int = REQUEST_TIMEOUT):
        self.client = get_client()
        self.timeout = timeout
        self._catalog = None

    # ── Internal ──────────────────────────────────────────────

    def _get(self, endpoint: str, **kwargs):
        """GET request with automatic retry on rate-limit (429)."""
        url = f"{self.API_BASE}{endpoint}"
        for attempt in range(3):
            r = self.client.get(url, headers=DEFAULT_HEADERS, timeout=self.timeout, **kwargs)
            if r.status_code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            return r
        return r

    # ── Catalog ───────────────────────────────────────────────

    def get_catalog(self, force_refresh: bool = False) -> list:
        """Get the full anime catalog (cached in memory).

        Each anime object contains: id, title, titleO, titles, description,
        themes, format, startDate, endDate, status, nsfw, saisons, ...
        """
        if self._catalog is not None and not force_refresh:
            return self._catalog

        r = self._get("animes")
        if r.status_code == 200:
            self._catalog = r.json()
        else:
            raise RuntimeError(f"Failed to get catalog: HTTP {r.status_code}")

        return self._catalog

    # ── Search ────────────────────────────────────────────────

    def search(self, query: str, limit: int = 20) -> list:
        """Search anime by title (substring match, scored)."""
        catalog = self.get_catalog()
        q = query.lower().strip()
        results = []

        for anime in catalog:
            title = (anime.get("title") or anime.get("titleO") or "").lower()
            title_en = (anime.get("titles", {}).get("en_jp") or "").lower()

            score = 0
            if q in title:
                score = 100 - abs(len(title) - len(q))
                if title.startswith(q):
                    score += 50
            elif q in title_en:
                score = 80 - abs(len(title_en) - len(q))

            if score > 0:
                results.append({
                    "id": anime["id"],
                    "title": anime.get("title") or anime.get("titleO"),
                    "title_original": anime.get("titleO"),
                    "description": anime.get("description", "")[:200],
                    "themes": anime.get("themes", []),
                    "status": anime.get("status", ""),
                    "nsfw": anime.get("nsfw", False),
                    "saisons": anime.get("saisons", []),
                    "score": score,
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    # ── Episodes ──────────────────────────────────────────────

    def get_episodes(self, anime_id: int, season: int = 1) -> list:
        """Get episode details from the anime-seasons endpoint."""
        r = self._get(f"anime-seasons/{anime_id}/{season}")
        if r.status_code == 200:
            return r.json().get("episodes", [])
        raise RuntimeError(
            f"Failed to get episodes for anime {anime_id} season {season}: "
            f"HTTP {r.status_code}"
        )

    def get_available_lecteurs(self, anime_id: int, season: int = 1, episode: int = 1) -> dict:
        """Get available players (lecteurs) for a specific episode."""
        catalog = self.get_catalog()
        anime = next((a for a in catalog if a["id"] == anime_id), None)
        if not anime:
            raise ValueError(f"Anime {anime_id} not found")

        saisons = anime.get("saisons", [])
        if season - 1 >= len(saisons):
            raise ValueError(f"Season {season} out of range")

        episodes = saisons[season - 1].get("episodes", [])
        if episode - 1 >= len(episodes):
            raise ValueError(f"Episode {episode} out of range in season {season}")

        ep = episodes[episode - 1]
        result = {}
        for lang_key, lang_val in ep.get("lang", {}).items():
            lecteurs = lang_val.get("lecteurs", [])
            result[lang_key] = [
                l for l in lecteurs if l not in ("TELECHARGEMENT UNIQUE", "TELECHARGEMENT")
            ]
        return result

    # ── Video URL resolution ──────────────────────────────────

    def get_video_url(self, anime_id: int, season: int, episode: int,
                      lang: str = "vo", lecteur: str = "filemoon"):
        """Resolve a video URL for a specific episode/player.

        Args:
            anime_id: Kitsu/FRAnime anime ID
            season: Season number (1-based)
            episode: Episode number (1-based)
            lang: "vo" (VOSTFR) or "vf" (VF)
            lecteur: Player name (filemoon, sibnet, sendvid, vidmoly, vk)

        Returns the video/embed URL, or None if unavailable.
        """
        r = self._get(f"anime/{anime_id}/{season}/{episode}/{lang}/{lecteur}")

        if r.status_code == 200:
            try:
                data = r.json()
                if isinstance(data, str):
                    return data
                if isinstance(data, dict):
                    return data.get("url") or data.get("iframe") or json.dumps(data)
                return json.dumps(data)
            except (json.JSONDecodeError, ValueError):
                return r.text.strip().strip('"')
        return None

    def resolve_episode(self, anime_id: int, season: int = 1, episode: int = 1,
                        lang: str = "vo") -> dict:
        """Auto-resolve: try all available lecteurs in priority order."""
        try:
            available = self.get_available_lecteurs(anime_id, season, episode)
        except Exception as e:
            return {"anime_id": anime_id, "season": season, "episode": episode,
                    "lang": lang, "error": str(e)}

        # Try requested language first, then fallback to other
        lang_order = [lang] + [l for l in available if l != lang]

        for try_lang in lang_order:
            lecteurs = available.get(try_lang, [])
            lecteurs_sorted = sorted(
                lecteurs,
                key=lambda l: LECTEUR_PRIORITY.index(l)
                if l in LECTEUR_PRIORITY else 999,
            )
            for lecteur in lecteurs_sorted:
                time.sleep(0.3)
                url = self.get_video_url(anime_id, season, episode, try_lang, lecteur)
                if url:
                    return {
                        "anime_id": anime_id,
                        "season": season,
                        "episode": episode,
                        "lang": try_lang,
                        "lecteur": lecteur,
                        "url": url,
                    }

        return {
            "anime_id": anime_id,
            "season": season,
            "episode": episode,
            "lang": lang,
            "error": "No working lecteur found for this episode",
        }


# ── Project-style functions (unified source registry) ─────────

_scraper = FRAnimeScraper()


def _parse_anime_id(url):
    """Extract the Franime anime ID from a franime:// or site URL."""
    if not url:
        return None
    m = re.match(r"franime://(\d+)", url)
    if m:
        return int(m.group(1))
    m = re.search(r"/anime/(\d+)", url)
    return int(m.group(1)) if m else None


def franime_catalog():
    """Download the Franime catalog as project-style entries."""
    try:
        data = _scraper.get_catalog()
    except Exception:
        return []
    entries = []
    for a in data:
        title = a.get("title") or a.get("titleO")
        if not title:
            continue
        aid = a.get("id")
        entries.append({
            "title": title,
            "link": f"https://franime.fr/anime/{aid}",
            "slug": str(aid),
            "anime_id": aid,
            "source": "franime",
        })
    return entries


def franime_search(query, entries=None):
    """Search Franime entries by query string."""
    try:
        data = _scraper.search(query, limit=50)
    except Exception:
        return []
    results = []
    for r in data:
        aid = r.get("id")
        results.append({
            "title": r.get("title"),
            "link": f"https://franime.fr/anime/{aid}",
            "slug": str(aid),
            "anime_id": aid,
            "score": r.get("score", 90),
            "source": "franime",
        })
    return results


def franime_episodes(url, season=1):
    """Get the episode list for a Franime anime (franime:// or site URL)."""
    aid = _parse_anime_id(url)
    if aid is None:
        return []
    try:
        data = _scraper.get_episodes(aid, season)
    except Exception:
        return []
    eps = []
    for i, ep in enumerate(data, start=1):
        eps.append({
            "number": i,
            "url": f"franime://{aid}/{season}/{i}",
            "lang": "vostfr",
            "title": ep.get("title", ""),
            "season": season,
        })
    return eps


def franime_resolve(url, lang="vo"):
    """Resolve a Franime episode URL (franime://id/season/ep) to a video URL."""
    m = re.match(r"franime://(\d+)/(\d+)/(\d+)", url or "")
    if not m:
        return None
    aid, season, ep = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        result = _scraper.resolve_episode(aid, season=season, episode=ep, lang=lang)
    except Exception:
        return None
    if "url" not in result:
        return None
    return {
        "url": result["url"],
        "type": "embed",
        "referer": "https://franime.fr/",
        "lecteur": result.get("lecteur"),
        "lang": result.get("lang"),
    }