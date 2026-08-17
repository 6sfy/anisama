"""Catalog CRUD, settings, history, and multi-source merge logic.

This module combines all cache functions from both the CLI and API
versions of anisama, including ``merge_source_into_catalog()`` and
``_try_merge_entry()`` from the API.
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx
from bs4 import BeautifulSoup

from .config import (
    CATALOG_FILE,
    CATALOG_REMOTE_URL,
    CACHE_MAX_AGE_HOURS,
    DATA_DIR,
    DEFAULT_HEADERS,
    DOMAIN_CACHE_FILE,
    HISTORY_FILE,
    REQUEST_TIMEOUT,
    SETTINGS_FILE,
    VOIRANIME_HEADERS,
    VOIRANIME_DOMAIN,
)


# ── Cache validity ──

def is_cache_valid() -> bool:
    """Check whether the local catalog file is still fresh."""
    if not CATALOG_FILE.exists():
        return False
    age = (time.time() - CATALOG_FILE.stat().st_mtime) / 3600
    s = load_settings()
    max_age = s.get("cache_hours", CACHE_MAX_AGE_HOURS)
    return age < max_age


# ── Anime-Sama catalog scraping helpers ──

def _get_max_page(soup: BeautifulSoup) -> int:
    """Extract the maximum page number from pagination."""
    pag = soup.find("div", id="list_pagination")
    if not pag:
        return 1
    mp = 1
    for a in pag.find_all("a", href=True):
        m = re.search(r"page=(\d+)", a["href"])
        if m:
            p = int(m.group(1))
            if p > mp:
                mp = p
    return mp


def _parse_card(card: Any, domain: str) -> dict[str, Any] | None:
    """Parse a single catalog card from Anime-Sama."""
    t = card.find("h2", class_="card-title")
    anchor = card.find("a")
    if not t or not anchor:
        return None
    title = t.get_text(strip=True)
    link = anchor.get("href", "")
    slug = link.rstrip("/").split("/")[-1] if link else ""
    if not slug:
        return None
    if link and not link.startswith("http"):
        link = f"https://{domain}{link}"
    alt = card.find("p", class_="alternate-titles")
    alts = [a.strip() for a in alt.get_text(strip=True).split(",") if a.strip()] if alt else []
    genres = [g.get_text(strip=True) for g in card.find_all("span", class_="genre-tag")]
    return {"title": title, "link": link, "slug": slug, "alt_titles": alts, "genres": genres}


def _fetch_soup(client: httpx.Client, url: str, params: dict[str, Any]) -> BeautifulSoup | None:
    """Fetch a URL and return a BeautifulSoup object, or None on failure."""
    try:
        r = client.get(url, params=params, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            return None
        return BeautifulSoup(r.content, "lxml")
    except Exception:
        return None


def _scrape_type(client: httpx.Client, domain: str, type_filter: str) -> list[dict[str, Any]]:
    """Scrape all entries of a given type (Anime/Film) from Anime-Sama."""
    url = f"https://{domain}/catalogue"
    seen: set[str] = set()
    entries: list[dict[str, Any]] = []

    soup = _fetch_soup(client, url, {"type[]": type_filter})
    if not soup:
        return []

    mp = _get_max_page(soup)

    for pn in range(1, mp + 1):
        if pn != 1:
            soup = _fetch_soup(client, url, {"type[]": type_filter, "page": pn})
            if not soup:
                continue

        cards = soup.find_all("div", class_="shrink-0 catalog-card card-base")
        for c in cards:
            parsed = _parse_card(c, domain)
            if parsed and parsed["slug"] not in seen:
                seen.add(parsed["slug"])
                entries.append({"title": parsed["title"], "link": parsed["link"], "alt_titles": parsed["alt_titles"], "genres": parsed.get("genres", [])})

    return entries


def download_catalog(domain: str, skip_slugs: set[str] | None = None) -> list[dict[str, Any]]:
    """Download the full Anime-Sama catalog for a given domain."""
    client = httpx.Client(follow_redirects=True, timeout=REQUEST_TIMEOUT)
    seen: set[str] = set()
    all_e: list[dict[str, Any]] = []

    for f in ("Anime", "Film"):
        for entry in _scrape_type(client, domain, f):
            slug = entry["link"].rstrip("/").split("/")[-1]
            if slug not in seen and (not skip_slugs or slug not in skip_slugs):
                seen.add(slug)
                all_e.append(entry)

    client.close()
    return all_e


# ── Voiranime catalog scraping ──

def _voiranime_get_max_page(soup: BeautifulSoup) -> int:
    """Extract the maximum page number from Voiranime pagination."""
    pag = soup.find("div", class_="pagination")
    if not pag:
        return 1
    pages: set[int] = set()
    for a in pag.find_all("a", href=True):
        m = re.search(r"page=(\d+)", a.get("href", ""))
        if m:
            pages.add(int(m.group(1)))
    return max(pages) if pages else 1


def _parse_voiranime_card(a: Any) -> dict[str, Any] | None:
    """Parse a single catalog card from Voiranime."""
    href = a.get("href", "").strip()
    img = a.find("img", class_="card-image")
    title = img.get("alt", "").strip() if img else ""
    if not title:
        t = a.find("h2", class_="card-title")
        title = t.get_text(strip=True) if t else ""
    if not title or not href:
        return None
    if href.startswith("/"):
        href = f"https://{VOIRANIME_DOMAIN}{href}"
    year_el = a.find("div", class_="year-item")
    year = year_el.get_text(strip=True) if year_el else ""
    genre_el = a.find("div", class_="genre-item")
    genre = genre_el.get_text(strip=True) if genre_el else ""
    return {"title": title, "link": href, "year": year, "genre": genre}


def download_voiranime_catalog(skip_slugs: set[str] | None = None) -> list[dict[str, Any]]:
    """Download the full Voiranime catalog."""
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()

    try:
        r = httpx.get(f"https://{VOIRANIME_DOMAIN}/catalogue/", headers=VOIRANIME_HEADERS, follow_redirects=True, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            return entries
    except Exception:
        return entries

    soup = BeautifulSoup(r.text, "html.parser")
    mp = _voiranime_get_max_page(soup)

    for pn in range(1, mp + 1):
        try:
            if pn == 1:
                page_soup = soup
            else:
                pr = httpx.get(f"https://{VOIRANIME_DOMAIN}/catalogue/?page={pn}", headers=VOIRANIME_HEADERS, follow_redirects=True, timeout=REQUEST_TIMEOUT)
                if pr.status_code != 200:
                    continue
                page_soup = BeautifulSoup(pr.text, "html.parser")

            grid = page_soup.find("div", class_="anime-grid")
            if not grid:
                continue

            for a in grid.find_all("a", href=True):
                parsed = _parse_voiranime_card(a)
                if parsed:
                    slug = parsed["link"].rstrip("/").split("/")[-1]
                    if slug not in seen and (not skip_slugs or slug not in skip_slugs):
                        seen.add(slug)
                        entries.append(parsed)
        except Exception:
            continue

    return entries


SKIP_GENRES: set[str] = {"animes", "top animes", "films", "voirdrama"}


def _scrape_voiranime_details(page_url: str) -> dict[str, Any]:
    """Scrape genre details from a Voiranime anime page."""
    try:
        r = httpx.get(page_url, headers=VOIRANIME_HEADERS, follow_redirects=True, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            return {}
    except Exception:
        return {}

    soup = BeautifulSoup(r.text, "html.parser")
    genres = [x.get_text(strip=True) for x in soup.select(".hero-genres .genre-link")]
    genres = [g for g in genres if g.lower() not in SKIP_GENRES]
    return {"genres": genres}


def enrich_voiranime_entries(entries: list[dict[str, Any]], max_workers: int = 15) -> list[dict[str, Any]]:
    """Enrich Voiranime entries with genre information in parallel."""
    if not entries:
        return entries

    enriched = list(entries)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut_map = {ex.submit(_scrape_voiranime_details, e["link"]): i for i, e in enumerate(entries)}
        for f in as_completed(fut_map):
            i = fut_map[f]
            try:
                details = f.result()
                if details.get("genres"):
                    enriched[i]["genres"] = details["genres"]
            except Exception:
                pass
    return enriched


# ── Title normalization for merge ──

def _norm_title(t: str) -> str:
    """Normalize a title for dedup comparison."""
    t = t.lower().strip()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


# ── Merge functions ──

def _try_merge_entry(merged: list[dict[str, Any]], seen: dict[str, int], new_entry: dict[str, Any], source_name: str) -> bool:
    """Try to merge a single entry into the catalog. Return True if merged."""
    new_slug = new_entry.get("link", "").rstrip("/").split("/")[-1]
    new_title = _norm_title(new_entry.get("title", ""))
    match_key: str | None = None

    if new_slug and new_slug in seen:
        match_key = new_slug
    else:
        for s, i in seen.items():
            e_title = _norm_title(merged[i].get("title", ""))
            if new_title and (new_title == e_title or new_title in e_title or e_title in new_title):
                match_key = s
                break
            for alt in merged[i].get("alt_titles", []):
                a = _norm_title(alt)
                if new_title and (new_title == a or new_title in a or a in new_title):
                    match_key = s
                    break
            if match_key:
                break

    if match_key is not None:
        idx = seen[match_key]
        src = merged[idx].get("alt_source", [])
        if source_name not in src:
            src.append(source_name)
            merged[idx]["alt_source"] = src
        if new_entry.get("genres"):
            existing_g = merged[idx].get("genres", [])
            g_set = set(existing_g)
            for g in new_entry["genres"]:
                if g not in g_set:
                    g_set.add(g)
                    existing_g.append(g)
            merged[idx]["genres"] = existing_g
        return True
    return False


def merge_into_catalog(as_entries: list[dict[str, Any]], vr_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge Anime-Sama and Voiranime entries, deduplicating by slug/title."""
    if not as_entries:
        return [dict(e, source="voiranime") for e in vr_entries]

    seen: dict[str, int] = {}
    merged: list[dict[str, Any]] = []

    for e in as_entries:
        slug = e.get("link", "").rstrip("/").split("/")[-1]
        key = slug or _norm_title(e.get("title", ""))
        seen[key] = len(merged)
        merged.append(dict(e))

    for vr in vr_entries:
        if not _try_merge_entry(merged, seen, vr, "voiranime"):
            entry = dict(vr)
            entry["source"] = "voiranime"
            merged.append(entry)

    return merged


def merge_source_into_catalog(catalog: list[dict[str, Any]], new_entries: list[dict[str, Any]], source_name: str) -> list[dict[str, Any]]:
    """Merge any source into an existing catalog.

    This is the general-purpose merge used for MyFluneo, AnimesUltra,
    FrenchAnime, and AnimoFlix catalogs.
    """
    seen: dict[str, int] = {}
    for i, e in enumerate(catalog):
        slug = e.get("link", "").rstrip("/").split("/")[-1]
        key = slug or _norm_title(e.get("title", ""))
        seen[key] = i

    for entry in new_entries:
        if not _try_merge_entry(catalog, seen, entry, source_name):
            new_entry = dict(entry)
            new_entry["source"] = source_name
            catalog.append(new_entry)
            slug = new_entry.get("link", "").rstrip("/").split("/")[-1]
            key = slug or _norm_title(new_entry.get("title", ""))
            seen[key] = len(catalog) - 1

    return catalog


# ── Catalog persistence ──

def save_catalog(data: list[dict[str, Any]]) -> None:
    """Save catalog data to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_catalog() -> list[dict[str, Any]]:
    """Load catalog data from disk. Returns empty list if file does not exist."""
    if not CATALOG_FILE.exists():
        return []
    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Combined catalog download ──

def download_combined_catalog(domain: str, enrich: bool = True) -> list[dict[str, Any]]:
    """Download a combined catalog from all sources and save to disk."""
    existing = load_catalog()
    existing_slugs: set[str] = set()
    if existing:
        for e in existing:
            slug = e.get("link", "").rstrip("/").split("/")[-1]
            if slug:
                existing_slugs.add(slug)

    as_entries = download_catalog(domain, skip_slugs=existing_slugs if existing else None)
    vr_entries = download_voiranime_catalog(skip_slugs=existing_slugs if existing else None)

    # Try to import and use additional source scrapers
    try:
        from .scraper.animesultra import animesultra_catalog
        au_entries = animesultra_catalog()
    except Exception:
        au_entries = []
    try:
        from .scraper.frenchanime import frenchanime_catalog
        fa_entries = frenchanime_catalog()
    except Exception:
        fa_entries = []
    try:
        from .scraper.animoflix import animoflix_catalog
        af_entries = animoflix_catalog()
    except Exception:
        af_entries = []
    try:
        from .scraper.myfluneo import myfluneo_catalog
        mf_entries = myfluneo_catalog()
    except Exception:
        mf_entries = []

    if not as_entries and not vr_entries and not au_entries and not fa_entries and not af_entries and not mf_entries:
        return existing or []

    if enrich and vr_entries:
        vr_entries = enrich_voiranime_entries(vr_entries)

    if existing:
        merged = merge_into_catalog(existing, vr_entries)
        for e in as_entries:
            merged.append(e)
    else:
        merged = merge_into_catalog(as_entries, vr_entries)

    if au_entries:
        merged = merge_source_into_catalog(merged, au_entries, "animesultra")
    if fa_entries:
        merged = merge_source_into_catalog(merged, fa_entries, "frenchanime")
    if af_entries:
        merged = merge_source_into_catalog(merged, af_entries, "animoflix")
    if mf_entries:
        merged = merge_source_into_catalog(merged, mf_entries, "myfluneo")

    save_catalog(merged)
    return merged


def fetch_github_catalog() -> list[dict[str, Any]] | None:
    """Fetch the catalog from the GitHub remote URL."""
    try:
        r = httpx.get(CATALOG_REMOTE_URL, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 100:
                save_catalog(data)
                return data
    except Exception:
        pass
    return None


def load_combined_catalog(domain: str) -> list[dict[str, Any]]:
    """Load the combined catalog from disk."""
    return load_catalog()


# ── Domain cache ──

def load_domain_cache() -> str | None:
    """Load the cached active domain from disk."""
    if not DOMAIN_CACHE_FILE.exists():
        return None
    try:
        return DOMAIN_CACHE_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return None


def save_domain_cache(domain: str) -> None:
    """Save the active domain to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        DOMAIN_CACHE_FILE.write_text(domain, encoding="utf-8")
    except Exception:
        pass


# ── Settings ──

DEFAULT_SETTINGS: dict[str, Any] = {
    "lang": None,
    "player": None,
    "auto_update": True,
    "auto_fetch_github": True,
    "auto_fetch_new": True,
    "download_dir": "downloads",
    "auto_next": False,
    "default_download": False,
    "max_results": 50,
    "cache_hours": 24,
    "preferred_hosts": "sendvid,vidmoly,smoothpre,vidhide,streamwish,oneupload,sibnet",
    "keep_open": True,
    "proxy": "",
    "prefer_mp4": True,
    "auto_convert_mp4": True,
}


def load_settings() -> dict[str, Any]:
    """Load settings from disk, filling in defaults for missing keys."""
    if not SETTINGS_FILE.exists():
        return dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            s = json.load(f)
            for k in DEFAULT_SETTINGS:
                s.setdefault(k, DEFAULT_SETTINGS[k])
            return s
    except Exception:
        return dict(DEFAULT_SETTINGS)


def save_settings(s: dict[str, Any]) -> None:
    """Save settings to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)


# ── History ──

def load_history() -> list[dict[str, Any]]:
    """Load watch history from disk."""
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def add_history(title: str, link: str, source: str, episode_num: Any, season_url: str | None = None, season_name: str | None = None) -> None:
    """Add an entry to watch history (most recent first)."""
    h = load_history()
    entry = {
        "title": title,
        "link": link,
        "source": source,
        "episode": episode_num,
        "season_url": season_url,
        "season_name": season_name,
        "time": time.time(),
    }
    # Move to top if same episode already exists
    h = [e for e in h if not (e.get("link") == link and e.get("season_url") == season_url and e.get("episode") == episode_num)]
    h.insert(0, entry)
    if len(h) > 200:
        h = h[:200]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)


def get_recent_anime() -> list[dict[str, Any]]:
    """Get recent anime from history, deduplicated."""
    h = load_history()
    seen: dict[str, dict[str, Any]] = {}
    for e in h:
        key = e["link"] + (e.get("season_url") or "")
        if key not in seen:
            seen[key] = e
    return list(seen.values())
