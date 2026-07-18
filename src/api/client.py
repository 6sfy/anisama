import json
import os
import re
from urllib.request import Request, urlopen
from urllib.parse import quote

API_BASE = os.environ.get("ANISAMA_API", "https://anisama.sexcaller.lol").rstrip("/")


def _clean(t):
    if not t:
        return t
    m = re.match(r"^\d+\s+(.+)", t)
    if m and re.search(r"\b(Vf|Vostfr|VO|VF|VOSTFR|VO)\b", m.group(1)):
        t = m.group(1)
    t = re.sub(r"\s+(Vf|Vostfr|VO|VF|VOSTFR|VO)\s*$", "", t)
    return t


def _get(path):
    url = f"{API_BASE}{path}"
    req = Request(url, headers={"User-Agent": "anisama-cli/1.1.0"})
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        raise Exception(f"API error ({url}): {e}")


def search(q):
    data = _get(f"/api/v2/search?q={quote(q)}")
    results = data.get("results", [])
    for r in results:
        if r.get("title"):
            r["title"] = _clean(r["title"])
    return results


def get_episodes(source, slug, url=""):
    params = f"source={quote(source)}&slug={quote(slug)}"
    if url:
        params += f"&url={quote(url)}"
    data = _get(f"/api/v2/episodes?{params}")
    return data.get("episodes", []), data.get("total", 0)


def resolve_episode(source, slug, num):
    data = _get(f"/api/v2/resolve-episode?source={quote(source)}&slug={quote(slug)}&num={num}")
    return data.get("url"), data.get("type", "mp4"), data.get("referer", "")


def get_sources():
    data = _get("/api/v2/sources")
    return data.get("sources", [])


def get_anime_info(title):
    try:
        data = _get(f"/api/v2/info?title={quote(title)}")
        return data
    except Exception:
        return None


def fetch_catalog_count(api_base=None):
    base = api_base or API_BASE
    try:
        r = urlopen(Request(f"{base}/api/v2/sources", headers={"User-Agent": "anisama-cli/1.1.0"}), timeout=5)
        data = json.loads(r.read().decode())
        return data.get("total", 0)
    except Exception:
        return 0
