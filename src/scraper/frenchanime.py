"""FrenchAnime scraper (french-anime.com) — link scraping."""

import re

from bs4 import BeautifulSoup

from ..config import REQUEST_TIMEOUT
from ..http_client import get_client

_ALT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

_FA_DOMAIN = "french-anime.com"


def frenchanime_catalog():
    """Download the FrenchAnime catalog by scraping the homepage links."""
    entries = []
    seen = set()
    client = get_client()
    try:
        r = client.get(f"https://{_FA_DOMAIN}/", headers=_ALT_HEADERS)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            for a in soup.find_all("a", href=re.compile(r"/animes-(?:vostfr|vf)/")):
                href = a.get("href", "")
                title = a.get_text(strip=True) or a.get("title", "")
                if not title or not href:
                    continue
                if not href.startswith("http"):
                    href = f"https://{_FA_DOMAIN}{href}"
                slug = href.rstrip("/").split("/")[-1].replace(".html", "")
                if slug and slug not in seen:
                    seen.add(slug)
                    entries.append({"title": title, "link": href, "slug": slug, "source": "frenchanime"})
    except Exception:
        pass
    return entries


def frenchanime_search(query, entries=None):
    """Search FrenchAnime entries by query string."""
    if entries is None:
        entries = frenchanime_catalog()
    q = query.lower().strip()
    results = []
    seen = set()
    for e in entries:
        if q in e["title"].lower() or q in e["slug"].lower():
            if e["link"] not in seen:
                seen.add(e["link"])
                results.append({"title": e["title"], "link": e["link"], "slug": e["slug"], "score": 90, "source": "frenchanime"})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:50]


def frenchanime_episodes(url):
    """Scrape the list of episodes from a FrenchAnime anime page."""
    eps = []
    client = get_client()
    try:
        r = client.get(url, headers=_ALT_HEADERS)
        if r.status_code != 200:
            return eps
    except Exception:
        return eps
    soup = BeautifulSoup(r.text, "lxml")
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        m = re.search(r"episode[-/]?(\d+)", href)
        if m:
            ep_num = int(m.group(1))
            if not href.startswith("http"):
                href = f"https://{_FA_DOMAIN}{href}"
            eps.append({"number": ep_num, "url": href, "lang": "vostfr"})
    return sorted(eps, key=lambda x: x["number"])


def frenchanime_resolve(url):
    """Resolve a FrenchAnime episode URL to an embed/video URL."""
    client = get_client()
    try:
        r = client.get(url, headers=_ALT_HEADERS)
        if r.status_code != 200:
            return None
    except Exception:
        return None
    soup = BeautifulSoup(r.text, "lxml")
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "")
        if src:
            if src.startswith("//"):
                src = "https:" + src
            known = ["luluvdo", "vidmoly", "vidara", "sendvid", "sibnet"]
            if any(h in src for h in known):
                return {"url": src, "type": "embed", "referer": url}
    return {"url": url, "type": "raw", "referer": url}
