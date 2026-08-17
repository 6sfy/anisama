"""AnimoFlix scraper (animoflix.to) — HTML scraping with Playwright fallback."""

import re

from bs4 import BeautifulSoup

from ..config import REQUEST_TIMEOUT
from ..http_client import get_client
from ..exceptions import ScraperError

_ALT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

_AF_DOMAIN = "animoflix.to"


def animoflix_catalog():
    """Download the AnimoFlix catalog by scraping the catalogue page."""
    entries = []
    seen = set()
    client = get_client()
    try:
        r = client.get(f"https://{_AF_DOMAIN}/catalogue/", headers=_ALT_HEADERS)
        if r.status_code != 200:
            return entries
    except Exception:
        return entries
    soup = BeautifulSoup(r.text, "lxml")
    for a in soup.find_all("a", href=re.compile(r"/anime/")):
        href = a.get("href", "")
        title = a.get_text(strip=True) or a.get("title", "")
        if not title or not href:
            continue
        if not href.startswith("http"):
            href = f"https://{_AF_DOMAIN}{href}"
        slug = href.rstrip("/").split("/")[-2] if href.endswith("/") else href.rstrip("/").split("/")[-1]
        if slug and slug not in seen:
            seen.add(slug)
            entries.append({"title": title, "link": href, "slug": slug, "source": "animoflix"})
    return entries


def animoflix_search(query, entries=None):
    """Search AnimoFlix entries by query string."""
    if entries is None:
        entries = animoflix_catalog()
    q = query.lower().strip()
    results = []
    seen = set()
    for e in entries:
        if q in e["title"].lower() or q in e["slug"].lower():
            if e["link"] not in seen:
                seen.add(e["link"])
                results.append({"title": e["title"], "link": e["link"], "slug": e["slug"], "score": 90, "source": "animoflix"})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:50]


def _check_playwright():
    """Import and return the playwright module, or return None if not installed."""
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        return None


def animoflix_episodes(url):
    """Scrape the list of episodes from an AnimoFlix anime page.

    Falls back to Playwright if HTML scraping finds no episodes.
    """
    eps = []
    client = get_client()

    # Try HTML scraping first
    try:
        r = client.get(url, headers=_ALT_HEADERS)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                m = re.search(r"episode[-/]?(\d+)", href)
                if m:
                    ep_num = int(m.group(1))
                    if not href.startswith("http"):
                        href = f"https://{_AF_DOMAIN}{href}"
                    if not any(e["number"] == ep_num for e in eps):
                        eps.append({"number": ep_num, "url": href, "lang": "vostfr"})
    except Exception:
        pass

    if eps:
        return sorted(eps, key=lambda x: x["number"])

    # Fall back to Playwright
    sync_pw = _check_playwright()
    if sync_pw is None:
        return []

    try:
        pw = sync_pw().start()
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        for link in page.locator('a[href*="episode-"]').all():
            href = link.get_attribute("href") or ""
            m = re.search(r"episode[-/]?(\d+)", href)
            if m:
                ep_num = int(m.group(1))
                if not href.startswith("http"):
                    href = f"https://{_AF_DOMAIN}{href}"
                if not any(e["number"] == ep_num for e in eps):
                    eps.append({"number": ep_num, "url": href, "lang": "vostfr"})

        browser.close()
        pw.stop()
    except Exception:
        pass

    return sorted(eps, key=lambda x: x["number"])


def animoflix_resolve(url):
    """Resolve an AnimoFlix episode URL to an embed/video URL.

    Falls back to Playwright if HTML scraping finds no iframe.
    """
    client = get_client()

    # Try HTML scraping first
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
            known = ["sendvid", "sibnet", "vidmoly"]
            if any(h in src for h in known):
                return {"url": src, "type": "embed", "referer": url}

    # Fall back to Playwright
    sync_pw = _check_playwright()
    if sync_pw is None:
        return {"url": url, "type": "raw", "referer": url}

    try:
        pw = sync_pw().start()
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        for btn in page.locator("[data-server], .server-item, .btn-server").all():
            try:
                btn.click()
                page.wait_for_timeout(1500)
            except Exception:
                continue
            for iframe in page.locator("iframe").all():
                src = iframe.get_attribute("src") or ""
                if src and "javascript" not in src:
                    if src.startswith("//"):
                        src = "https:" + src
                    browser.close()
                    pw.stop()
                    return {"url": src, "type": "embed", "referer": url}

        browser.close()
        pw.stop()
    except Exception:
        pass

    return {"url": url, "type": "raw", "referer": url}
