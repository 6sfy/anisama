"""Configuration constants and configurable paths for anisama.

DATA_DIR is configurable via the ``ANISAMA_DATA_DIR`` environment
variable.  If not set, it defaults to ``<package_dir>/data``.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Known Anime-Sama domains ──

KNOWN_DOMAINS: list[str] = [
    "anime-sama.to",
    "anime-sama.si",
    "anime-sama.org",
    "anime-sama.tv",
    "anime-sama.eu",
    "anime-sama.pw",
    "anime-sama.fr",
]

PROVIDER_URL: str = "https://anime-sama.pw/"

# ── HTTP headers ──

DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

VOIRANIME_DOMAIN: str = "voiranime.rip"

VOIRANIME_HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.6",
    "Referer": "https://voiranime.rip/catalogue/",
}

RESOLVER_HEADERS: dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

# ── Paths (configurable via environment) ──

PACKAGE_DIR: Path = Path(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR: Path = PACKAGE_DIR.parent

# Allow overriding the data directory via environment variable
_ENV_DATA_DIR = os.environ.get("ANISAMA_DATA_DIR")
if _ENV_DATA_DIR:
    DATA_DIR: Path = Path(_ENV_DATA_DIR)
else:
    DATA_DIR = PROJECT_DIR / "data"

CATALOG_FILE: Path = DATA_DIR / "catalog.json"
SETTINGS_FILE: Path = DATA_DIR / "settings.json"
HISTORY_FILE: Path = DATA_DIR / "history.json"
DOMAIN_CACHE_FILE: Path = DATA_DIR / "active_domain.txt"

# ── Cache / network settings ──

CACHE_MAX_AGE_HOURS: int = 24
REQUEST_TIMEOUT: int = 15
CATALOG_REMOTE_URL: str = "https://raw.githubusercontent.com/6sfy/anisama/main/data/catalog.json"

# ── Playwright (optional dependency) ──

PLAYWRIGHT_EXECUTABLE_PATH: str = os.environ.get(
    "ANISAMA_PLAYWRIGHT_EXECUTABLE_PATH", ""
)
