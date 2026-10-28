# Changelog

All notable changes to `anisama` are documented here.

## [2.1.7] - 2026-10-28

### Fixed

- **Episode playback** — embed URLs returned by the API (often `uqload`,
  which is domain-restricted) are no longer handed to mpv/VLC. They are
  resolved to a direct stream (m3u8/mp4) first. When no direct stream exists
  (e.g. FRAnime `watch2`), the episode opens in the browser instead of
  silently failing.
- **First playable mirror wins** — mirrors are resolved in parallel with a
  12-second cap, so slow or restricted hosts no longer block playback while a
  working mirror is already available.
- **No more false success** — the CLI no longer prints
  `Episode launched, enjoy!` when the resolved URL cannot be played.
- **API cache hygiene** — embeds and `watch2` pages are no longer written back
  to the API as resolved streams; only direct URLs are reported.
- **Dead URLs** — cached API URLs are validated before playback, with
  `fresh=1` re-resolution and an embed-referer fallback when the token expired.
- **HLS segment validation** — an m3u8 is considered alive only if a real
  segment is fetchable. Tokens bound to another IP/ASN (segments 403) are
  rejected and the local resolver takes over.
- **Search scores** — bounded to 0-100 in the CLI picker, so a remote API can
  no longer display values such as `143%`.

### Added

- **Local fast engine** (`anisama.engine`) — direct API extraction for
  Anime-Sama (`episodes.js`) and FRAnime (JSON, 0-based indexes), with
  automatic fallback to the historical scrapers.
- **Parallel API/local resolution race** — the first valid answer wins and the
  result is written back to the API cache.
- **Configurable API URL** in the settings menu (`ANISAMA_API` still takes
  precedence).

### Changed

- Anime-Sama seasons/episodes use the fast engine first (`_get_seasons_fast` /
  `_get_episodes_fast`).
- Test suite: 150 tests, including embed resolution and browser-fallback
  coverage.

## [2.1.6] - 2026-10-23

### Fixed

- Re-resolve the embed referer when the API serves a dead cached URL.
- Reject dead URLs during resolution — liveness checks inside race workers.
- Validate the resolved URL before playback and retry with `fresh=1` on
  expired tokens.

### Added

- Race API and local episode resolution; the first response wins and is
  written back to the API cache.
- Configurable API URL in the settings menu.
