> [!IMPORTANT]
> ## Project Status
>
> **This project is actively maintained and developed by 6sfy.**

> [!CAUTION]
> **The use of this module under a different name on PyPI (or another source besides this GitHub) is not associated with this library.**
> **anisama scrapes from Anime-Sama, Voiranime, MyFluneo, AnimesUltra, French-Anime, AnimoFlix. We are not responsible for any misuse.**

## About

<strong>Welcome to <code>anisama</code>, a Python library + CLI for multi-source anime scraping, search, and video resolution.</strong>

- Scrapes 6 sources: Anime-Sama, Voiranime, MyFluneo, AnimesUltra, French-Anime, AnimoFlix.
- Fuzzy search with rapidfuzz across all sources with intelligent dedup.
- Video URL resolution for 10+ hosting providers.
- Unified source registry for use by CLI and API frontends.
- Built-in interactive CLI (click + questionary + rich) — `anisama "demon slayer"`

<div align="center">
  <p>
    <a href="https://pypi.org/project/anisama/"><img src="https://img.shields.io/pypi/v/anisama" alt="PyPI version" /></a>
    <a href="https://pypi.org/project/anisama/"><img src="https://img.shields.io/pypi/dm/anisama" alt="PyPI downloads" /></a>
    <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python version" /></a>
  </p>
</div>

## Project Structure

```
anisama/
├── src/
│   ├── __init__.py               # Version and top-level exports
│   ├── config.py                 # Constants, headers, domains, paths
│   ├── cache.py                  # Catalog CRUD, multi-source merge
│   ├── search.py                 # Fuzzy search (rapidfuzz)
│   ├── http_client.py            # Shared httpx.Client singleton (HTTP/2)
│   ├── resolver.py               # Video URL resolution per host
│   ├── sources.py                # Source registry + unified API
│   ├── exceptions.py             # Custom exceptions
│   ├── scraper/
│   │   ├── __init__.py           # Re-exports all scrapers
│   │   ├── base.py               # Shared helpers, domain discovery
│   │   ├── anime_sama.py         # Anime-Sama scraper
│   │   ├── voiranime.py          # Voiranime scraper
│   │   ├── myfluneo.py           # MyFluneo scraper (Playwright)
│   │   ├── animesultra.py        # AnimesUltra scraper
│   │   ├── frenchanime.py        # FrenchAnime scraper
│   │   └── animoflix.py          # AnimoFlix scraper (Playwright)
│   └── cli/
│       ├── __init__.py
│       ├── app.py                # Click entry point & main menu
│       ├── display.py            # Rich console, banners, panels
│       ├── workflow.py           # Search → pick → play workflow
│       ├── picker.py             # Episode & mirror selection
│       ├── player.py             # Video player launcher (mpv/vlc/…)
│       ├── settings.py           # Settings menu (lang, player, proxy)
│       ├── config.py             # CLI-specific config helpers
│       ├── install.py            # Dependency installer
│       ├── mirror.py             # Mirror selection logic
│       └── api_client.py         # Optional API backend client
├── data/                       # Local catalog/settings storage
├── tests/                      # Pytest suite (125+ tests)
└── pyproject.toml
```

## Installation

### From PyPI (recommended)

```sh-session
pip install anisama
```

### With Playwright support

```sh-session
pip install anisama[playwright]
playwright install chromium
```

### From source

```sh-session
git clone https://github.com/6sfy/anisama.git
cd anisama
pip install -e .
```

## Usage

### As a CLI tool

```sh-session
# Interactive mode (launches menu)
anisama

# Search and play
anisama "demon slayer"
anisama --lang vf "attack on titan"
anisama --download "one piece"
anisama -e 1-5 "naruto"

# Settings
anisama --settings
```

### As a library

```python
from anisama import cache, search, resolver
from anisama.scraper import anime_sama, voiranime
from anisama.scraper.base import find_active_domain
from anisama.sources import SOURCES
from anisama.config import KNOWN_DOMAINS, DEFAULT_HEADERS

# Find active domain
domain = find_active_domain()

# Download catalog
catalog = cache.download_combined_catalog(domain)

# Search
results = search.search_combined("demon slayer", catalog, domain)

# Get episodes
seasons = anime_sama.get_anime_seasons(results[0]["link"])
episodes = anime_sama.get_episodes(seasons[0]["url"])

# Resolve video URL
video = resolver.resolve_url(episodes[0]["mirrors"]["eps1"])

# Use the unified source registry
for name, source in SOURCES.items():
    print(f"{name}: {source.description}")
```

### Configuration

- `ANISAMA_DATA_DIR` — Override the data directory (default: `<project_root>/data`)
- `ANISAMA_PLAYWRIGHT_EXECUTABLE_PATH` — Path to Playwright Chromium executable

## Sources

| Source | Language | Method |
|--------|----------|--------|
| [Anime-Sama](https://anime-sama.to) | VOSTFR/VF | HTML scraping |
| [Voiranime](https://voiranime.rip) | VOSTFR/VF | HTML scraping |
| [MyFluneo](https://myfluneo.eu) | VOSTFR | Playwright |
| [AnimesUltra](https://ww.animesultra.org) | VOSTFR/VF | Sitemap/HTML |
| [French-Anime](https://french-anime.com) | VOSTFR/VF | HTML scraping |
| [AnimoFlix](https://animoflix.to) | VOSTFR | HTML + Playwright |

## Contributing

- Before creating an issue, please ensure that it hasn't already been reported/suggested.
- See [the contribution guide](https://github.com/6sfy/anisama/blob/main/CONTRIBUTING.md) if you'd like to submit a PR.

## Credits

- [pystardust/ani-cli](https://github.com/pystardust/ani-cli) for the original idea and workflow
- Content sources: Anime-Sama, Voiranime, MyFluneo, AnimesUltra, French-Anime, AnimoFlix
