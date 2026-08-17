"""Anime-Sama scraper: seasons, episodes, and online search."""

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..config import DEFAULT_HEADERS, REQUEST_TIMEOUT
from ..http_client import get_client
from ..cache import download_catalog


_SKIP_SEASON_KEYWORDS = {"scan", "manhwa", "webtoon", "manhua", "manga", "novel", "light novel", "ln"}


def _is_anime_season(name: str) -> bool:
    """Return True if the season name refers to anime (not manga/novel)."""
    lower = name.lower()
    return not any(kw in lower for kw in _SKIP_SEASON_KEYWORDS)


def get_anime_seasons(url):
    """Scrape the list of anime seasons from an Anime-Sama anime page."""
    client = get_client()
    r = client.get(url, headers=DEFAULT_HEADERS)
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    seasons = []
    pat = re.compile(r'panneau(?:Anime|Film|Scan|Visual)\s*\(\s*(["\'])(.*?)\1\s*,\s*(["\'])(.*?)\3\s*\)')
    for s in soup.find_all("script"):
        if s.text:
            txt = re.sub(r'/\*.*?\*/', "", s.text, flags=re.DOTALL)
            for _, name, _, path in pat.findall(txt):
                if name.lower() != "nom" and path.lower() != "url":
                    if not _is_anime_season(name):
                        continue
                    full = urljoin(url.rstrip("/") + "/", path).rstrip("/")
                    seasons.append({"name": name, "url": full})
    seen = set()
    uniq = []
    for s in seasons:
        if s["name"] not in seen:
            seen.add(s["name"])
            uniq.append(s)
    return uniq


def get_episodes(url):
    """Scrape the list of episodes (with mirrors) from a season page."""
    client = get_client()
    if not url.endswith("/"):
        url += "/"
    r = client.get(url, headers=DEFAULT_HEADERS)
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    script = soup.find("script", src=lambda s: s and "episodes.js" in s)
    if not script:
        return []
    src = script.get("src", "")
    if src.startswith("/"):
        parsed = urlparse(url)
        js_url = f"{parsed.scheme}://{parsed.netloc}{src}"
    else:
        js_url = urljoin(url, src)
    try:
        js = client.get(js_url, headers=DEFAULT_HEADERS).text
    except Exception:
        return []
    matches = re.findall(r"var\s+(eps\d+)\s*=\s*\[(.*?)\];", js, re.DOTALL)
    if not matches:
        return []
    all_eps = {}
    for name, content in matches:
        urls = re.findall(r"'(https?://[^']+)'", content)
        all_eps[name] = urls
    keys = sorted(all_eps.keys(), key=lambda x: int(x[3:]))
    if not keys:
        return []
    n = len(all_eps[keys[0]])
    eps = []
    for i in range(n):
        mirrors = {}
        for k in keys:
            if i < len(all_eps[k]):
                mirrors[k] = all_eps[k][i]
        eps.append({"number": i + 1, "mirrors": mirrors, "referer": url})
    return eps


def resolve_episode_url(url):
    """Resolve an episode URL using the resolver module."""
    from ..resolver import resolve_url
    return resolve_url(url)


def search_online(domain, query):
    """Search Anime-Sama's built-in search endpoint."""
    url = f"https://{domain}/template-php/defaut/fetch.php"
    client = get_client()
    try:
        r = client.post(url, data={"query": query}, headers=DEFAULT_HEADERS)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    for a in soup.find_all("a", class_="asn-search-result"):
        link = a.get("href", "").strip()
        t = a.find("h3", class_="asn-search-result-title")
        title = t.get_text(strip=True) if t else ""
        if not title or not link:
            continue
        results.append({"title": title, "link": link, "score": 100, "source": "online"})
    return results


def anime_sama_catalog(domain=None, skip_slugs=None):
    """Download the Anime-Sama catalog. Thin wrapper around cache.download_catalog."""
    if domain is None:
        from .base import find_active_domain
        domain = find_active_domain()
    return download_catalog(domain, skip_slugs=skip_slugs)
