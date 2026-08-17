"""HTTP client for the anisama API."""

import json
import os
import re
import time
import urllib.error
from urllib.request import Request, urlopen
from urllib.parse import quote

from anisama import cache as cache_mod

DEFAULT_API_URL = "https://anisama.sexcaller.lol"


def _default_api_base():
    try:
        return (cache_mod.load_settings().get("api_url") or "").strip().rstrip("/")
    except Exception:
        return ""


API_BASE = (os.environ.get("ANISAMA_API") or _default_api_base() or DEFAULT_API_URL).rstrip("/")


def _clean(t):
    if not t:
        return t
    m = re.match(r"^\d+\s+(.+)", t)
    if m and re.search(r"\b(Vf|Vostfr|VO|VF|VOSTFR|VO)\b", m.group(1)):
        t = m.group(1)
    t = re.sub(r"\s+(Vf|Vostfr|VO|VF|VOSTFR|VO)\s*$", "", t)
    return t


def _get(path, _retries=2):
    url = f"{API_BASE}{path}"
    req = Request(url, headers={"User-Agent": "anisama-cli/2.1.3"})
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429 and _retries > 0:
            retry_after = 1
            try:
                retry_after = int(e.headers.get("Retry-After", "1"))
            except (TypeError, ValueError):
                pass
            time.sleep(min(retry_after, 5))
            return _get(path, _retries - 1)
        raise Exception(f"API error ({url}): {e}")
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


def submit_resolution(source, slug, num, url, rtype, referer=""):
    """POST a locally-resolved URL to the API so it can serve it instantly later."""
    body = json.dumps({
        "source": source,
        "slug": slug,
        "num": num,
        "url": url,
        "type": rtype,
        "referer": referer,
    }).encode()
    req = Request(
        f"{API_BASE}/api/v2/resolve-episode",
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "anisama-cli/2.1.3",
        },
        method="POST",
    )
    with urlopen(req, timeout=5) as resp:
        return resp.status


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
        r = urlopen(Request(f"{base}/api/v2/sources", headers={"User-Agent": "anisama-cli/2.1.3"}), timeout=5)
        data = json.loads(r.read().decode())
        return data.get("total", 0)
    except Exception:
        return 0
