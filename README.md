> [!IMPORTANT]
> ## Project Status
>
> **This project is actively maintained and developed by 6sfy.**

> [!CAUTION]
> **The use of this module under a different name on PyPI (or another source besides this GitHub) is not associated with this library.**
> **anisama streams from Anime-Sama, Voiranime, MyFluneo, AnimesUltra, French-Anime, AnimoFlix, Franime. We are not responsible for any misuse.**

## About

<strong>Welcome to <code>anisama</code>, a Python CLI to browse, watch, and download anime from multiple sources (VOSTFR/VF).</strong>

- Inspired by [ani-cli](https://github.com/pystardust/ani-cli), the original shell-based anime streaming tool.
- Scrapes 7 sources: Anime-Sama, Voiranime, MyFluneo, AnimesUltra, French-Anime, AnimoFlix, Franime.
- Interactive TUI built with Rich and Questionary.
- Connects to the anisama API for fast search and video resolution.

<div align="center">
  <p>
    <a href="https://pypi.org/project/anisama/"><img src="https://img.shields.io/pypi/v/anisama" alt="PyPI version" /></a>
    <a href="https://pypi.org/project/anisama/"><img src="https://img.shields.io/pypi/dm/anisama" alt="PyPI downloads" /></a>
    <a href="https://github.com/6sfy/anisama/actions/workflows/test.yml"><img src="https://img.shields.io/github/actions/workflow/status/6sfy/anisama/test.yml?branch=master" alt="Tests status" /></a>
    <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python version" /></a>
  </p>
</div>

## Project Structure

```
anisama/
├── src/                       # Library package (installed as `anisama`)
│   ├── __init__.py            # Version and top-level exports
│   ├── config.py              # Constants, headers, domains, paths
│   ├── cache.py               # Catalog CRUD, multi-source merge
│   ├── search.py              # Fuzzy search (rapidfuzz)
│   ├── http_client.py         # Shared httpx.Client singleton (HTTP/2)
│   ├── resolver.py            # Video URL resolution per host
│   ├── sources.py             # Source registry + unified API
│   ├── exceptions.py          # Custom exceptions
│   ├── scraper/               # Per-source scrapers
│   │   ├── base.py            # Shared helpers, domain discovery
│   │   ├── anime_sama.py      # Anime-Sama scraper
│   │   ├── voiranime.py       # Voiranime scraper
│   │   ├── myfluneo.py        # MyFluneo scraper (Playwright)
│   │   ├── animesultra.py     # AnimesUltra scraper
│   │   ├── frenchanime.py     # FrenchAnime scraper
│   │   ├── animoflix.py       # AnimoFlix scraper (Playwright)
│   │   └── franime.py         # Franime scraper (API-based)
│   └── cli/                   # CLI-specific code
│       ├── app.py             # Entry point, click command
│       ├── display.py         # Banner, colors, info panels
│       ├── workflow.py        # Main workflow (search, play, download)
│       ├── picker.py          # Selection menus
│       ├── player.py          # Player detection, play/download
│       ├── mirror.py          # Speed tests, mirror resolution
│       ├── install.py         # yt-dlp/ffmpeg install guides
│       ├── settings.py        # Settings menu
│       └── api_client.py      # Remote anisama API client
├── data/                      # Local catalog/settings storage
├── tests/                     # Pytest suite
└── pyproject.toml
```

## Features

- Search anime by title with fuzzy matching (rapidfuzz) across 7 sources
- Multi-source merge: Anime-Sama, Voiranime, MyFluneo, AnimesUltra, French-Anime, AnimoFlix, Franime
- Intelligent dedup: season/lang variants grouped under one result
- Smart search: exact match shows only relevant results, broad queries show variants
- Browse seasons (VOSTFR / VF)
- Stream episodes in your preferred video player
- Download episodes directly
- Episode range support (1-5 or 1,3,5)
- Multiple video mirrors with automatic speed-tested fallback
- Player support: mpv, VLC, IINA, MoonPlayer, ImPlay
- API-first resolve with local fallback
- "Continue watching" history menu
- AniList-powered info panel (score, status, episodes, studios, tags, synopsis)
- Prefer MP4 sources over HLS/m3u8 for faster playback
- Automatic m3u8 → mp4 conversion for downloads

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

### Interactive mode

```sh-session
anisama
```

### CLI mode

```sh-session
anisama "demon slayer"
anisama "one piece" -e 1-5
anisama "attack on titan" -e 1,3,5 --lang vf
anisama "jujutsu kaisen" -d -e 1
anisama -p vlc "berserk"
```

### Options

| Flag | Description |
|------|-------------|
| `--lang vostfr/vf` | Language filter |
| `--dub` | Shorthand for VF |
| `-d, --download` | Download instead of streaming |
| `-e, --episodes` | Episode range: `5`, `1-5`, or `1,3,5` |
| `-p, --player` | Player: mpv, vlc, iina, moonplayer, implay |
| `-U, --update` | Force refresh the anime catalog |
| `-s, --settings` | Open settings menu |
| `-q, --quiet` | Reduce output verbosity |
| `--version` | Show version |
| `-h, --help` | Show help |

## API

anisama uses a centralized API for fast search and video resolution. The API server source is available at [github.com/6sfy/anisama-api](https://github.com/6sfy/anisama-api).

The API base URL defaults to `https://anisama.sexcaller.lol` and can be overridden with the `ANISAMA_API` environment variable.

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

- `ANISAMA_API` — Override the API base URL (default: `https://anisama.sexcaller.lol`)
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
| [Franime](https://franime.fr) | VOSTFR/VF | API |

## Contributing

- Before creating an issue, please ensure that it hasn't already been reported/suggested.
- See [the contribution guide](https://github.com/6sfy/anisama/blob/master/CONTRIBUTING.md) if you'd like to submit a PR.

## Credits

- [pystardust/ani-cli](https://github.com/pystardust/ani-cli) for the original idea and workflow
- Content sources: Anime-Sama, Voiranime, MyFluneo, AnimesUltra, French-Anime, AnimoFlix, Franime