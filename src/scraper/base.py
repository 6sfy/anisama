"""Base scraper utilities: shared HTTP client, domain discovery, and common helpers."""

import re

from ..config import DEFAULT_HEADERS, KNOWN_DOMAINS, PROVIDER_URL, REQUEST_TIMEOUT
from ..http_client import get_client
from ..cache import load_domain_cache, save_domain_cache
from ..exceptions import DomainNotFoundError

_active_domain = None


def find_active_domain():
    """Find the currently active Anime-Sama domain.

    Tries, in order:
    1. Cached domain (with a quick verification request)
    2. Provider URL redirect
    3. Brute-force scan of known domains

    Returns the domain string, or raises ``DomainNotFoundError``.
    """
    global _active_domain
    if _active_domain is not None:
        return _active_domain

    client = get_client()

    # 1. Try cached domain
    cached = load_domain_cache()
    if cached:
        try:
            r = client.get(f"https://{cached}", headers=DEFAULT_HEADERS)
            if r.status_code == 200 and "anime-sama" in r.text.lower()[:500]:
                final = str(r.url).replace("https://", "").replace("http://", "").split("/")[0].split("?")[0]
                if final:
                    _active_domain = final
                    if final != cached:
                        save_domain_cache(final)
                    return final
        except Exception:
            pass

    # 2. Try provider URL redirect
    try:
        r = client.get(PROVIDER_URL, headers=DEFAULT_HEADERS)
        m = re.search(r'href="(.+?)">Acceder a Anime-Sama', r.text, re.IGNORECASE)
        if m:
            r2 = client.get(m.group(1), headers=DEFAULT_HEADERS)
            u = str(r2.url)
            dm = re.search(r"https?://([^/]+)", u)
            if dm:
                _active_domain = dm.group(1)
                save_domain_cache(_active_domain)
                return _active_domain
    except Exception:
        pass

    # 3. Brute-force known domains
    for d in KNOWN_DOMAINS:
        try:
            r = client.get(f"https://{d}/", headers=DEFAULT_HEADERS)
            if r.status_code == 200 and "anime-sama" in r.text.lower()[:500]:
                final = str(r.url).replace("https://", "").replace("http://", "").split("/")[0].split("?")[0]
                if not final:
                    final = d
                _active_domain = final
                save_domain_cache(final)
                return final
        except Exception:
            continue

    raise DomainNotFoundError("Could not find an active Anime-Sama domain")


def reset_active_domain():
    """Reset the cached active domain, forcing rediscovery on next call."""
    global _active_domain
    _active_domain = None
