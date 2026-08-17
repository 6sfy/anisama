"""MyFluneo scraper (myfluneo.eu) — requires Playwright for episodes and resolution."""

import base64
import hashlib
import json
import re
import time
from pathlib import Path

from ..config import DATA_DIR, PLAYWRIGHT_EXECUTABLE_PATH, REQUEST_TIMEOUT
from ..http_client import get_client
from ..exceptions import ScraperError

MYFLUNEO_DOMAIN = "myfluneo.eu"
MYFLUNEO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _check_playwright():
    """Import and return the playwright module, or raise ScraperError."""
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        raise ScraperError(
            "Playwright is required for MyFluneo scraping. "
            "Install with: pip install anisama[playwright] && playwright install chromium"
        )


def _get_chromium_executable():
    """Return the Playwright chromium executable path if configured."""
    if PLAYWRIGHT_EXECUTABLE_PATH:
        return PLAYWRIGHT_EXECUTABLE_PATH
    return None


def _base_slug(slug):
    """Normalize a slug by removing -vf/-vostfr/-vo and trailing numbers."""
    s = re.sub(r"-(vf|vostfr|vo)$", "", slug)
    s = re.sub(r"-\d+$", "", s)
    return s


def myfluneo_catalog():
    """Download the MyFluneo catalog by scraping sitemaps."""
    entries = []
    seen = set()
    client = get_client()

    for i in range(1, 18):
        url = f"https://{MYFLUNEO_DOMAIN}/sitemap_{i}.xml"
        try:
            r = client.get(url, headers=MYFLUNEO_HEADERS)
        except Exception:
            continue
        if r.status_code != 200:
            continue

        for loc in re.findall(r"<loc>([^<]+)</loc>", r.text):
            loc = loc.strip()
            if "/anime/" not in loc:
                continue
            slug = loc.rstrip("/").split("/")[-1]
            if slug in seen:
                continue
            seen.add(slug)

            base = _base_slug(slug)
            title = base.replace("-", " ").title()
            title = re.sub(r"\s+Saison\s+\d+.*$", "", title, flags=re.IGNORECASE)
            title = re.sub(r"\s+Movie\s+\d+.*$", "", title, flags=re.IGNORECASE)
            title = re.sub(r"\s+Film\s+\d+.*$", "", title, flags=re.IGNORECASE)
            title = title.strip()

            entries.append({
                "title": title,
                "link": loc,
                "slug": slug,
                "source": "myfluneo",
            })

    return entries


def myfluneo_search(query, entries=None):
    """Search MyFluneo entries by query string."""
    if entries is None:
        entries = myfluneo_catalog()
    q = query.lower().strip()
    results = []
    seen = set()
    for e in entries:
        if q in e["title"].lower() or q in e["slug"].lower():
            if e["link"] not in seen:
                seen.add(e["link"])
                results.append({"title": e["title"], "link": e["link"], "slug": e["slug"], "score": 90, "source": "myfluneo"})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:50]


def myfluneo_resolve(episode_url):
    """Resolve a MyFluneo episode URL to a direct video URL using Playwright."""
    try:
        sync_playwright = _check_playwright()
        pw = sync_playwright().start()
        launch_kwargs = {"headless": True}
        exec_path = _get_chromium_executable()
        if exec_path:
            launch_kwargs["executable_path"] = exec_path
        browser = pw.chromium.launch(**launch_kwargs)
        page = browser.new_page()

        video_url = None

        def on_response(response):
            nonlocal video_url
            if "/embed-player?" in response.url:
                try:
                    data = response.json()
                    if data.get("redirectUrl"):
                        video_url = data["redirectUrl"]
                except Exception:
                    pass

        page.on("response", on_response)
        page.goto(episode_url, wait_until="networkidle", timeout=15000)

        if not video_url:
            iframes = page.locator("iframe").all()
            for f in iframes:
                src = f.get_attribute("src")
                if src and "/embed-player" in src:
                    v_match = re.search(r"v=([A-Za-z0-9+/=]+)", src)
                    if v_match:
                        try:
                            decoded = base64.b64decode(v_match.group(1)).decode()
                            video_url = decoded
                        except Exception:
                            pass

        browser.close()
        pw.stop()

        if video_url:
            return {"url": video_url, "type": "mp4", "referer": episode_url}
        return {"url": episode_url, "type": "raw", "referer": episode_url}

    except ScraperError:
        raise
    except Exception:
        return {"url": episode_url, "type": "raw", "referer": episode_url}


def myfluneo_episodes(anime_url):
    """Scrape the list of episodes from a MyFluneo anime page using Playwright."""
    # Simple file-based cache
    cache_key = hashlib.md5(anime_url.encode()).hexdigest()
    cache_file = DATA_DIR / "api_cache" / f"mf_eps_{cache_key}.json"
    if cache_file.exists():
        try:
            age = time.time() - cache_file.stat().st_mtime
            if age < 86400:
                return json.loads(cache_file.read_text())
        except Exception:
            pass

    try:
        sync_playwright = _check_playwright()
        pw = sync_playwright().start()
        launch_kwargs = {"headless": True}
        exec_path = _get_chromium_executable()
        if exec_path:
            launch_kwargs["executable_path"] = exec_path
        browser = pw.chromium.launch(**launch_kwargs)
        page = browser.new_page()

        episodes = {}
        page.goto(anime_url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        links = page.locator('a[href*="/episode-"]').all()
        for link in links:
            href = link.get_attribute("href") or ""
            m = re.search(r"/saison-(\d+)/episode-(\d+)", href)
            if m:
                ep_num = int(m.group(2))
                if ep_num not in episodes:
                    ep_url = href.split("?_rsc=")[0].split("?")[0]
                    if not ep_url.startswith("http"):
                        ep_url = f"https://{MYFLUNEO_DOMAIN}{ep_url}"
                    episodes[ep_num] = {"url": ep_url, "season": m.group(1)}

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)
        more = page.locator('a[href*="/episode-"]').all()
        for link in more:
            href = link.get_attribute("href") or ""
            m = re.search(r"/saison-(\d+)/episode-(\d+)", href)
            if m:
                ep_num = int(m.group(2))
                if ep_num not in episodes:
                    ep_url = href.split("?_rsc=")[0].split("?")[0]
                    if not ep_url.startswith("http"):
                        ep_url = f"https://{MYFLUNEO_DOMAIN}{ep_url}"
                    episodes[ep_num] = {"url": ep_url, "season": m.group(1)}

        browser.close()
        pw.stop()

        eps = [
            {"number": n, "url": e["url"], "lang": "vostfr", "season": e.get("season", "1")}
            for n, e in sorted(episodes.items())
        ]

        if eps:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(eps, ensure_ascii=False))

        return eps

    except ScraperError:
        raise
    except Exception:
        return []
