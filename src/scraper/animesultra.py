"""AnimesUltra scraper (ww.animesultra.org) — sitemap-based catalog."""

import re

from bs4 import BeautifulSoup

from ..config import REQUEST_TIMEOUT
from ..http_client import get_client

_ALT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

_AN_DOMAIN = "ww.animesultra.org"


def animesultra_catalog():
    """Download the AnimesUltra catalog by parsing the sitemap."""
    entries = []
    seen = set()
    client = get_client()
    try:
        r = client.get(f"https://{_AN_DOMAIN}/sitemap.xml", headers=_ALT_HEADERS)
        if r.status_code != 200:
            return entries
    except Exception:
        return entries

    for loc in re.findall(r"<loc>([^<]+)</loc>", r.text):
        loc = loc.strip()
        if "/anime-vostfr/" not in loc and "/anime-vf/" not in loc:
            continue
        slug = loc.rstrip("/").split("/")[-1].replace(".html", "")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        title = slug.replace("-", " ").title()
        title = re.sub(r"\s+Au\s*$", "", title, flags=re.IGNORECASE).strip()
        entries.append({"title": title, "link": loc, "slug": slug, "source": "animesultra"})
    return entries


def animesultra_search(query, entries=None):
    """Search AnimesUltra entries by query string."""
    if entries is None:
        entries = animesultra_catalog()
    q = query.lower().strip()
    results = []
    seen = set()
    for e in entries:
        if q in e["title"].lower() or q in e["slug"].lower():
            if e["link"] not in seen:
                seen.add(e["link"])
                results.append({"title": e["title"], "link": e["link"], "slug": e["slug"], "score": 90, "source": "animesultra"})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:50]


def animesultra_episodes(url):
    """Scrape the list of episodes from an AnimesUltra anime page."""
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
                href = f"https://{_AN_DOMAIN}{href}"
            eps.append({"number": ep_num, "url": href, "lang": "vostfr"})
    for ep_div in soup.find_all("div", class_=re.compile(r"epi|episode|eps", re.I)):
        a = ep_div.find("a", href=True)
        if a:
            href = a.get("href", "")
            m = re.search(r"(\d+)", a.get_text(strip=True) or "")
            if m:
                ep_num = int(m.group(1))
                if not href.startswith("http"):
                    href = f"https://{_AN_DOMAIN}{href}"
                if not any(e["number"] == ep_num for e in eps):
                    eps.append({"number": ep_num, "url": href, "lang": "vostfr"})
    return sorted(eps, key=lambda x: x["number"])


def animesultra_resolve(url):
    """Resolve an AnimesUltra episode URL to an embed/video URL."""
    client = get_client()
    try:
        r = client.get(url, headers=_ALT_HEADERS)
        if r.status_code != 200:
            return None
    except Exception:
        return None
    soup = BeautifulSoup(r.text, "lxml")
    for div in soup.find_all(attrs={"data-embed": True}):
        embed = div.get("data-embed", "")
        if embed:
            if embed.startswith("//"):
                embed = "https:" + embed
            return {"url": embed, "type": "embed", "referer": url}
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src", "")
        if src:
            if src.startswith("//"):
                src = "https:" + src
            known = ["vidmoly", "sendvid", "sibnet", "streamtape", "vidstream"]
            if any(h in src for h in known):
                return {"url": src, "type": "embed", "referer": url}
    return {"url": url, "type": "raw", "referer": url}
