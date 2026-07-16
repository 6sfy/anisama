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
    t = re.sub(r"[^\w\s\-&'#]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def clean(txt):
    t = txt.lower()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def terms(txt):
    return set(clean(txt).split())

def search_anime(query, catalog, domain=None, limit=10):
    q = clean(query)
    if not q:
        return []

    seen = set()
    results = []

    if domain:
        for r in scraper.search_online(domain, query):
            if r["link"] not in seen:
                seen.add(r["link"])
                results.append(r)

    if catalog:
        min_score = 60 if results else 40
        qt = terms(query)
        scored = []

        for anime in catalog:
            title = anime.get("title", "")
            link = anime.get("link", "")
            c = clean(title)
            if not c or link in seen:
                continue

            s = fuzz.token_set_ratio(q, c)
            bonus = 0

            tt = terms(title)
            common = qt & tt
            bonus = len(common) * 8

            for qw in qt:
                for tw in tt:
                    if len(qw) >= 3 and (qw in tw or tw in qw):
                        bonus = max(bonus, 6)

            ll = link.lower()
            for qw in qt:
                if qw in ll and len(qw) >= 3:
                    bonus = max(bonus, 10)

            for alt in anime.get("alt_titles", []):
                ac = clean(alt)
                if not ac:
                    continue
                ascore = fuzz.token_set_ratio(q, ac)
                if ascore > s:
                    s = ascore
                if ac == q:
                    s = 100
                    bonus = 40
                    break
                at = terms(alt)
                extra = qt & at
                if extra:
                    bonus = max(bonus, len(extra) * 5)
            else:
                bonus = min(bonus, 40)

            final = min(100, s + bonus)
            if final >= min_score:
                scored.append({"title": anime["title"], "link": link, "score": final, "source": "catalog"})

        scored.sort(key=lambda x: x["score"], reverse=True)
        for r in scored:
            if r["link"] not in seen:
                seen.add(r["link"])
                results.append(r)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]

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
        results.append({
            "title": title,
            "link": link,
            "score": 100,
            "source": "voiranime",
        })
    return results

def search_combined(query, catalog, domain, limit=10):
    q = clean(query)
    if not q:
        return []

    seen = set()
    results = []

    if domain:
        for r in scraper.search_online(domain, query):
            if r["link"] not in seen:
                seen.add(r["link"])
                results.append(r)

    if catalog:
        min_score = 60 if results else 40
        qt = terms(query)
        scored = []

        for anime in catalog:
            title = anime.get("title", "")
            link = anime.get("link", "")
            source = anime.get("source", "catalog")
            c = clean(title)
            if not c or link in seen:
                continue

            s = fuzz.token_set_ratio(q, c)
            bonus = 0

            tt = terms(title)
            common = qt & tt
            bonus = len(common) * 8

            for qw in qt:
                for tw in tt:
                    if len(qw) >= 3 and (qw in tw or tw in qw):
                        bonus = max(bonus, 6)

            ll = link.lower()
            for qw in qt:
                if qw in ll and len(qw) >= 3:
                    bonus = max(bonus, 10)

            for alt in anime.get("alt_titles", []):
                ac = clean(alt)
                if not ac:
                    continue
                ascore = fuzz.token_set_ratio(q, ac)
                if ascore > s:
                    s = ascore
                if ac == q:
                    s = 100
                    bonus = 40
                    break
                at = terms(alt)
                extra = qt & at
                if extra:
                    bonus = max(bonus, len(extra) * 5)
            else:
                bonus = min(bonus, 40)

            final = min(100, s + bonus)
            if final >= min_score:
                scored.append({"title": anime["title"], "link": link, "score": final, "source": source})

        scored.sort(key=lambda x: x["score"], reverse=True)
        for r in scored:
            if r["link"] not in seen:
                seen.add(r["link"])
                results.append(r)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]
