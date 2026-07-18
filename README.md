> [!IMPORTANT]
> ## Project Status
>
> **This project is actively maintained and developed by 6sfy.**

> [!CAUTION]
> **The use of this module under a different name on PyPI (or another source besides this GitHub) is not associated with this library.**
> **anisama streams from Anime-Sama, Voiranime, MyFluneo, AnimesUltra, French-Anime, AnimoFlix. We are not responsible for any misuse.**

## About

<strong>Welcome to <code>anisama</code>, a Python CLI to browse, watch, and download anime from multiple sources (VOSTFR/VF).</strong>

- Inspired by [ani-cli](https://github.com/pystardust/ani-cli), the original shell-based anime streaming tool.
- Scrapes 6 sources: Anime-Sama, Voiranime, MyFluneo, AnimesUltra, French-Anime, AnimoFlix.
- Interactive TUI built with [Rich](https://github.com/Textualize/rich) and [Questionary](https://github.com/tmbo/questionary).
- Connects to the [anisama API](https://github.com/6sfy/anisama-api) for fast search and video resolution.

<div align="center">
  <p>
    <a href="https://pypi.org/project/anisama/"><img src="https://img.shields.io/pypi/v/anisama" alt="PyPI version" /></a>
    <a href="https://pypi.org/project/anisama/"><img src="https://img.shields.io/pypi/dm/anisama" alt="PyPI downloads" /></a>
    <a href="https://github.com/6sfy/anisama/actions"><img src="https://github.com/6sfy/anisama/actions/workflows/test.yml/badge.svg" alt="Tests status" /></a>
    <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python version" /></a>
  </p>
</div>

## Project Structure

```
anisama/
├── src/                    # CLI application
│   ├── __init__.py
│   ├── __main__.py
│   ├── core/               # Backend logic
│   │   ├── config.py       # Constants, headers, domains
│   │   ├── cache.py        # Catalog, settings, history
│   │   ├── scraper.py      # Anime-Sama + Voiranime scraping
│   │   ├── resolver.py     # Video URL extraction per host
│   │   └── search.py       # Fuzzy search, scoring, dedup
│   ├── cli/                # CLI-specific code
│   │   ├── app.py          # Entry point, click command
│   │   ├── display.py      # Banner, colors, info panels
│   │   ├── player.py       # Player detection, play/download
│   │   ├── picker.py       # Selection menus
│   │   ├── mirror.py       # Speed tests, mirror resolution
│   │   ├── install.py      # yt-dlp/ffmpeg install guides
│   │   ├── settings.py     # Settings menu
│   │   └── workflow.py     # Main workflow (search, play, download)
│   └── api/                # Remote API client
│       └── client.py       # Wrapper for anisama API
└── data/                   # Local catalog/settings storage
```

## Features

- [x] Search anime by title with fuzzy matching (rapidfuzz) across 6 sources
- [x] Multi-source merge: Anime-Sama, Voiranime, MyFluneo, AnimesUltra, French-Anime, AnimoFlix
- [x] Intelligent dedup: season/lang variants grouped under one result
- [x] Smart search: exact match shows only relevant results, broad queries show variants
- [x] Browse seasons (VOSTFR / VF)
- [x] Stream episodes in your preferred video player
- [x] Download episodes directly
- [x] Episode range support (1-5 or 1,3,5)
- [x] Multiple video mirrors with automatic speed-tested fallback
- [x] Player support: mpv, VLC, IINA, MoonPlayer, ImPlay
- [x] API-first resolve with local fallback
- [x] "Continue watching" history menu
- [x] AniList-powered info panel (score, status, episodes, studios, tags, synopsis)
- [x] Prefer MP4 sources over HLS/m3u8 for faster playback
- [x] Automatic m3u8 → mp4 conversion for downloads
- [ ] More sources / languages

## Installation

### From PyPI (recommended)

```sh-session
pip install anisama
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
| `-p, --player` | Player: `mpv`, `vlc`, `iina`, `moonplayer`, `implay` |
| `-U, --update` | Force refresh the anime catalog |
| `-q, --quiet` | Reduce output verbosity |
| `--version` | Show version |
| `-h, --help` | Show help |

## API

anisama uses a centralized API for fast search and video resolution. The API server source is available at [github.com/6sfy/anisama-api](https://github.com/6sfy/anisama-api).

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
