import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .config import DEFAULT_HEADERS, KNOWN_DOMAINS, PROVIDER_URL, REQUEST_TIMEOUT, VOIRANIME_HEADERS
from .cache import load_domain_cache, save_domain_cache

_client = None
_active_domain = None

def get_client():
    global _client
    if _client is None:
        _client = httpx.Client(follow_redirects=True, timeout=REQUEST_TIMEOUT)
    return _client

def find_active_domain():
    global _active_domain
    if _active_domain is not None:
        return _active_domain

    cached = load_domain_cache()
    if cached:
        try:
            r = get_client().get(f"https://{cached}", headers=DEFAULT_HEADERS)
            if r.status_code == 200 and "anime-sama" in r.text.lower()[:500]:
                final = str(r.url).replace("https://", "").replace("http://", "").split("/")[0].split("?")[0]
                if final:
                    _active_domain = final
                    if final != cached:
                        save_domain_cache(final)
                    return final
        except Exception:
            pass

    try:
        r = get_client().get(PROVIDER_URL, headers=DEFAULT_HEADERS)
        m = re.search(r'href="(.+?)">Acceder a Anime-Sama', r.text, re.IGNORECASE)
        if m:
            r2 = get_client().get(m.group(1), headers=DEFAULT_HEADERS)
            u = str(r2.url)
            dm = re.search(r"https?://([^/]+)", u)
            if dm:
                _active_domain = dm.group(1)
                save_domain_cache(_active_domain)
                return _active_domain
    except Exception:
        pass

    for d in KNOWN_DOMAINS:
        try:
            r = get_client().get(f"https://{d}/", headers=DEFAULT_HEADERS)
            if r.status_code == 200 and "anime-sama" in r.text.lower()[:500]:
                final = str(r.url).replace("https://", "").replace("http://", "").split("/")[0].split("?")[0]
                if not final:
                    final = d
                _active_domain = final
                save_domain_cache(final)
                return final
        except Exception:
            continue

    return None

_SKIP_SEASON_KEYWORDS = {"scan", "manhwa", "webtoon", "manhua", "manga", "novel", "light novel", "ln"}


def _is_anime_season(name: str) -> bool:
    lower = name.lower()
    return not any(kw in lower for kw in _SKIP_SEASON_KEYWORDS)


def get_anime_seasons(url):
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
    from .resolver import resolve_url as _resolve
    return _resolve(url)

def search_online(domain, query):
    url = f"https://{domain}/template-php/defaut/fetch.php"
    try:
        r = get_client().post(url, data={"query": query}, headers=DEFAULT_HEADERS)
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

def voiranime_get_seasons(url):
    r = get_client().get(url, headers=VOIRANIME_HEADERS)
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    seasons = []
    section = soup.find("section", id="seasons")
    if not section:
        return seasons
    for card in section.find_all("a", class_="season-card"):
        href = card.get("href", "")
        title_el = card.find("h3", class_="season-title")
        meta = card.find("div", class_="season-meta")
        langs = set()
        if meta:
            for badge in meta.find_all("span", class_="lang-badge"):
                langs.add(badge.get_text(strip=True).lower())
        name = title_el.get_text(strip=True) if title_el else ""
        if not name or not href:
            continue
        if not href.startswith("http"):
            href = urljoin(url, href)
        seasons.append({"name": name, "url": href, "langs": langs})
    return seasons

def voiranime_get_episodes(season_url, lang=None):
    r = get_client().get(season_url, headers=VOIRANIME_HEADERS)
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    eps = []
    grid = soup.find("div", class_="episodes-grid")
    if not grid:
        return eps
    for card in grid.find_all("a", class_="episode-card"):
        href = card.get("href", "")
        num_el = card.find("div", class_="episode-number")
        num = num_el.get_text(strip=True) if num_el else ""
        m = re.search(r"(\d+)", num)
        ep_num = int(m.group(1)) if m else 0
        langs_raw = card.get("data-langs", "")
        ep_langs = set(langs_raw.split()) if langs_raw else set()

        if lang and lang not in ep_langs:
            continue

        if not href.startswith("http"):
            href = urljoin(season_url, href)

        eps.append({"number": ep_num, "url": href, "langs": ep_langs})
    return eps
