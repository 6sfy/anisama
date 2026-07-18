import re
import unicodedata

import httpx
from bs4 import BeautifulSoup
from rapidfuzz import fuzz

from . import scraper
from .config import VOIRANIME_DOMAIN, VOIRANIME_HEADERS, REQUEST_TIMEOUT


def norm(title):
    if not title:
        return ""
    t = unicodedata.normalize("NFKD", title)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("\u2018", "'").replace("\u2019", "'")
    t = re.sub(r'[\\/:*?"<>|]', " ", t)
    t = re.sub(r"[^\w\s\-&#']", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def clean(txt):
    t = txt.lower()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def terms(txt):
    return set(clean(txt).split())


def _norm_title(t):
    return re.sub(r"[^a-z0-9]", "", clean(t))


def strip_id_prefix(t):
    if not t:
        return t
    m = re.match(r"^\d+\s+(.+)", t)
    if m and re.search(r"\b(Vf|Vostfr|VO|VF|VOSTFR|VO)\b", m.group(1)):
        t = m.group(1)
    t = re.sub(r"\s+(Vf|Vostfr|VO|VF|VOSTFR|VO)\s*$", "", t)
    return t


def _base_key(t):
    t = t.lower().strip()
    t = re.sub(r"\s+(vf|vostfr|vo)\s*$", "", t)
    t = re.sub(r"\s+(saison|season)\s+\d+.*$", "", t)
    t = re.sub(r"\s+(movie|film)\s+\d+.*$", "", t)
    t = re.sub(r"\s+\d+\s*$", "", t)
    t = re.sub(r"\s+dll\s*$", "", t)
    t = re.sub(r"[^a-z0-9]", "", t)
    return t


def _calc_score(query: str, title: str, alt_titles=None):
    """
    Compute a realistic 0-100 similarity score.
    Same logic as the API so results are consistent.
    """
    if not query or not title:
        return 0

    q = query.lower().strip()
    t = title.lower().strip()
    qn = norm(query)
    tn = norm(title)

    if q == t or qn == tn:
        return 100

    pr = fuzz.partial_ratio(q, t)
    tsr = fuzz.token_set_ratio(q, t)
    score = max(pr, tsr)

    q_tokens = set(q.split())
    t_tokens = set(t.split())
    extra = len(t_tokens - q_tokens)
    if extra > 0:
        score -= extra * 12

    if t.startswith(q + " "):
        score += 20

    if alt_titles:
        for alt in alt_titles:
            a = alt.lower().strip()
            alt_score = max(fuzz.partial_ratio(q, a), fuzz.token_set_ratio(q, a))
            a_tokens = set(a.split())
            alt_extra = len(a_tokens - q_tokens)
            if alt_extra > 0:
                alt_score -= alt_extra * 12
            if alt_score > score:
                score = alt_score
            if norm(alt) == qn:
                score = 100
                break

    return max(0, min(100, int(score)))


def search_anime(query, catalog, domain=None, limit=10):
    """Legacy search — used by places expecting the old signature."""
    return search_combined(query, catalog, domain=domain, limit=limit)


def search_voiranime(query):
    url = f"https://{VOIRANIME_DOMAIN}/template-php/defaut/fetch.php"
    try:
        r = httpx.post(url, data={"query": query}, headers=VOIRANIME_HEADERS, follow_redirects=True, timeout=REQUEST_TIMEOUT)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    for a in soup.find_all("a", class_="va-search-result"):
        link = a.get("href", "").strip()
        title_el = a.find("span", class_="va-search-result-title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title or not link:
            continue
        if not link.startswith("http"):
            link = f"https://{VOIRANIME_DOMAIN}{link}"
        results.append({"title": strip_id_prefix(title), "link": link, "score": 100, "source": "voiranime"})
    return results


def search_combined(query, catalog, domain, limit=10):
    """
    Intelligent search across all sources.
    - Deduplicates by normalized title
    - Uses real fuzzy matching (rapidfuzz)
    - Prioritizes: catalog > online
    """
    q = clean(query)
    if not q:
        return []

    seen_titles = {}
    results = []

    def _add(r):
        if r.get("title"):
            r["title"] = strip_id_prefix(r["title"])
        key = _base_key(r.get("title", ""))
        if not key:
            return
        if key in seen_titles:
            idx = seen_titles[key]
            existing = results[idx]
            src_rank = {"catalog": 0, "online": 1, "voiranime": 2}
            cur_rank = src_rank.get(existing.get("source", ""), 3)
            new_rank = src_rank.get(r.get("source", ""), 3)
            if r.get("score", 0) > existing.get("score", 0) or new_rank < cur_rank:
                results[idx] = r
            alt = existing.get("alt_source", [])
            if r.get("source") and r["source"] not in alt:
                alt.append(r["source"])
            results[idx]["alt_source"] = alt
            if r.get("anime_id") and not existing.get("anime_id"):
                results[idx]["anime_id"] = r["anime_id"]
            if r.get("link") and not existing.get("link"):
                results[idx]["link"] = r["link"]
        else:
            seen_titles[key] = len(results)
            results.append(r)

    # 1. Catalog search
    if catalog:
        scored = []
        for anime in catalog:
            title = anime.get("title", "")
            link = anime.get("link", "")
            score = _calc_score(query, title, anime.get("alt_titles", []))
            if score < 50:
                continue
            scored.append({
                "title": anime["title"],
                "link": link,
                "score": score,
                "source": "catalog",
                "anime_id": anime.get("anime_id", ""),
                "alt_source": anime.get("alt_source", []),
                "genres": anime.get("genres", []),
            })

        scored.sort(key=lambda x: (-x["score"], x["title"]))
        for r in scored[:limit * 2]:
            _add(r)

    # 2. Anime-Sama online search (live fallback)
    if domain:
        try:
            for r in scraper.search_online(domain, query):
                _add({
                    "title": r.get("title", ""),
                    "link": r.get("link", ""),
                    "score": r.get("score", 85),
                    "source": "online",
                    "anime_id": "",
                })
        except Exception:
            pass

    # 3. Voiranime search (final fallback)
    try:
        for r in search_voiranime(query):
            _add({
                "title": r.get("title", ""),
                "link": r.get("link", ""),
                "score": r.get("score", 80),
                "source": "voiranime",
                "anime_id": "",
            })
    except Exception:
        pass

    results.sort(key=lambda x: (-x["score"], x["title"]))
    return results[:limit]
