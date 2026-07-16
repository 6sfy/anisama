> [!IMPORTANT]
> ## Project Status
>
> **This project is actively maintained and developed by 6sfy.**

> [!CAUTION]
> **The use of this module under a different name on PyPI (or another source besides this GitHub) is not associated with this library.**
> **anisama only streams from Anime-Sama and Voiranime. We are not responsible for any misuse.**

## About

<strong>Welcome to <code>anisama</code>, a Python CLI to browse, watch, and download anime from Anime-Sama and Voiranime (VOSTFR/VF).</strong>

- anisama is directly inspired by [ani-cli](https://github.com/pystardust/ani-cli), the original shell-based anime streaming tool. While ani-cli focuses on a lightweight shell experience, anisama brings the same idea to Python with a richer interactive TUI and broader Windows support.
- It scrapes Anime-Sama and Voiranime to search, stream, and download anime episodes directly from your terminal.
- The interactive TUI is built with [Rich](https://github.com/Textualize/rich) and [Questionary](https://github.com/tmbo/questionary): clean headers and native arrow-key navigation.

<div align="center">
  <p>
    <a href="https://pypi.org/project/anisama/"><img src="https://img.shields.io/pypi/v/anisama" alt="PyPI version" /></a>
    <a href="https://pypi.org/project/anisama/"><img src="https://img.shields.io/pypi/dm/anisama" alt="PyPI downloads" /></a>
    <a href="https://github.com/6sfy/anisama/actions"><img src="https://github.com/6sfy/anisama/actions/workflows/test.yml/badge.svg" alt="Tests status" /></a>
    <a href="https://python.org"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python version" /></a>
  </p>
</div>

> [!WARNING]
> **anisama scrapes Anime-Sama and Voiranime. The availability of content depends on the source websites. Use responsibly.**

> [!CAUTION]
> **Streaming/downloading copyrighted content may be illegal in your country. Check your local laws before using this tool.**

### <strong>[GitHub](https://github.com/6sfy/anisama)</strong>

### <strong>[Report Issue](https://github.com/6sfy/anisama/issues)</strong>

## Features

- [x] Search anime by title with fuzzy matching across alt titles
- [x] Browse seasons (VOSTFR / VF)
- [x] Stream episodes in your preferred video player
- [x] Download episodes directly
- [x] Episode range support
- [x] Multiple video mirrors with automatic fallback
- [x] Player support: mpv, VLC, IINA, MoonPlayer, ImPlay
- [x] Smart catalog: auto-updates
- [x] Dual-source catalog merging (Anime-Sama + Voiranime)
- [x] "Continue watching" history menu
- [x] Clean interactive TUI with keyboard navigation
- [x] AniList-powered info panel (score, status, episodes, studios, tags, synopsis)
- [x] Prefer MP4 sources over HLS/m3u8 for faster playback
- [x] Automatic m3u8 → mp4 conversion for downloads (via ffmpeg or yt-dlp)
- [ ] More sources / languages

## Installation

> [!NOTE]
> **Python 3.10 or newer is required**

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

Just run `anisama` without arguments to use the interactive TUI:

```sh-session
anisama
```

Use the arrow keys to navigate menus, Enter to confirm, and Esc to go back.

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

### Settings

Run `anisama` and choose **Settings**, or edit `data/settings.json`:

| Setting | Description |
|---------|-------------|
| `lang` | Default language: `vostfr`, `vf`, or `None` |
| `player` | Default player: `mpv`, `vlc`, `iina`, `moonplayer`, `implay`, or `Auto` |
| `auto_update` | Automatically refresh the catalog when stale |
| `auto_fetch_github` | Download the remote GitHub catalog first |
| `auto_fetch_new` | Scrape new Anime-Sama/Voiranime entries locally |
| `download_dir` | Directory for downloaded episodes |
| `auto_next` | Automatically play the next episode |
| `default_download` | Default to download mode instead of streaming |
| `max_results` | Maximum number of search results returned |
| `cache_hours` | Catalog cache lifetime in hours |
| `preferred_hosts` | Comma-separated mirror priority list |
| `keep_open` | Keep the player open after the video ends |
| `prefer_mp4` | Prefer MP4 files over HLS/m3u8 streams |
| `auto_convert_mp4` | Convert HLS downloads to MP4 automatically |
| `proxy` | HTTP/HTTPS proxy (e.g. `http://127.0.0.1:8080`) |

## Example

```python
# anisama is a CLI tool — run it from your terminal
# anisama "death note"
# anisama "fullmetal alchemist" -e 1-10
```

## Video sources

anisama resolves multiple video mirrors per episode and automatically prefers MP4 files when possible, because MP4 starts faster than HLS/m3u8 streams.

When downloading an episode that only resolves to an m3u8 stream, anisama attempts to convert it to MP4 in the background using `ffmpeg` (preferred) or `yt-dlp` (fallback). If neither is installed, the raw stream is downloaded as-is.\n\nEnable **Auto-convert downloads to MP4** in Settings for fully automatic conversion. The first time you enable it, anisama will offer to install `ffmpeg` for you, or show platform-specific install instructions. The conversion uses `-c copy`, so it is as fast as your internet connection and does not re-encode the video.

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| ↑ / ↓ | Navigate choices |
| Enter | Confirm selection |
| Esc | Go back / cancel |
| Ctrl+C | Quit |

## Contributing

- Before creating an issue, please ensure that it hasn't already been reported/suggested.
- See [the contribution guide](https://github.com/6sfy/anisama/blob/main/CONTRIBUTING.md) if you'd like to submit a PR.

## Need help?

GitHub Issues: [Here](https://github.com/6sfy/anisama/issues)

## Credits

- [pystardust/ani-cli](https://github.com/pystardust/ani-cli) for the original idea and workflow
- [Anime-Sama](https://anime-sama.to) for the primary content
- [Voiranime](https://voiranime.rip) for the secondary source

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=6sfy/anisama&type=Date)](https://star-history.com/#6sfy/anisama&Date)
