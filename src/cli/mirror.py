"""Mirror resolution, speed test, m3u8→mp4 conversion."""

import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import httpx
import questionary

from anisama import cache
from anisama.config import RESOLVER_HEADERS
from anisama.scraper.anime_sama import resolve_episode_url
from anisama.resolver import resolve_generic

from .display import console, ST, QS, note, ok, err

PREF_HOSTS = ["sendvid", "vidmoly", "smoothpre", "vidhide", "streamwish", "oneupload", "sibnet"]
MP4_HOSTS = ["sendvid", "oneupload", "sibnet"]
BACK = "<  Back"


def test_url_speed(url, referer=None, sample_bytes=256000):
    headers = dict(RESOLVER_HEADERS)
    if referer:
        headers["Referer"] = referer
    try:
        start = time.perf_counter()
        with httpx.stream("GET", url, headers=headers, timeout=10, follow_redirects=True) as r:
            if r.status_code >= 400:
                return 0
            downloaded = 0
            for chunk in r.iter_bytes(chunk_size=8192):
                downloaded += len(chunk)
                if downloaded >= sample_bytes:
                    break
            elapsed = time.perf_counter() - start
            if elapsed <= 0:
                return 0
            return int(downloaded / elapsed)
    except Exception:
        return 0


def format_speed(bps):
    if bps >= 1_000_000:
        return f"{bps/1_000_000:.1f} MB/s"
    if bps >= 1_000:
        return f"{bps/1_000:.1f} KB/s"
    return f"{bps} B/s"


def _stream_is_alive(url, rtype="mp4", referer=None, timeout=8):
    """Lightweight liveness check for a resolved video URL."""
    from . import player as player_mod
    return player_mod.stream_is_alive(url, rtype, referer, timeout=timeout)


def pick_fastest_mirror(ep, prefer_mp4=True, test_speed=True, quiet=False):
    """Resolve all mirrors in parallel, optionally speed-test the best ones,
    and return the fastest playable source."""
    candidates = resolve_all_mirrors(ep)
    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    type_rank = {"mp4": 0, "webm": 1, "m3u8": 2, "raw": 3}
    candidates.sort(key=lambda c: type_rank.get(c.get("type", "raw"), 3))

    if test_speed:
        ranked = sorted(enumerate(candidates), key=lambda x: type_rank.get(x[1].get("type", "raw"), 3))
        speeds = {}
        has_mp4 = any(c.get("type") in ("mp4", "webm") for c in candidates)
        for i, c in ranked:
            t = c.get("type", "raw")
            if t not in ("mp4", "webm"):
                speeds[i] = 0 if has_mp4 else 1_000_000
                continue
            speeds[i] = 0
            try:
                speeds[i] = test_url_speed(c["url"], c.get("referer"))
            except Exception:
                pass

        def sort_key(item):
            i, c = item
            t = c.get("type", "raw")
            rank = type_rank.get(t, 3)
            speed = speeds.get(i, 0)
            if prefer_mp4 and t in ("mp4", "webm"):
                speed = speed * 2 + 1_000_000
            return (rank, -speed)

        ranked = sorted(enumerate(candidates), key=sort_key)
        best_idx, best = ranked[0]
        if not quiet:
            for i, c in ranked:
                spd = speeds.get(i, 0)
                t = c.get("type", "raw")
                if t in ("mp4", "webm"):
                    spd_str = format_speed(spd) if spd > 0 else "unreachable"
                else:
                    spd_str = "skipped (m3u8)"
                note(f"  {c.get('type','raw').upper():6} {spd_str:<14} {urlparse(c['url']).netloc}")
        return best

    return candidates[0]


def resolve_best_mirror(ep, prefer_mp4=True):
    """Resolve ALL mirrors in parallel, check liveness, and return the
    best ALIVE source. No hard priority — all sources are tried equally.

    Preference is only a SOFT tiebreaker among alive URLs:
      mp4/webm > m3u8 > raw
    """
    candidates = resolve_all_mirrors(ep)
    if not candidates:
        return None

    if len(candidates) == 1:
        c = candidates[0]
        # Even a single candidate should be checked for liveness
        if c.get("type") not in ("embed", "raw") and not _stream_is_alive(
            c["url"], c.get("type", "mp4"), c.get("referer")
        ):
            return None
        return c

    type_rank = {"mp4": 0, "webm": 1, "m3u8": 2, "raw": 3}

    # Sort by soft preference (mp4 > m3u8 > raw)
    candidates.sort(key=lambda c: type_rank.get(c.get("type", "raw"), 3))

    # Check liveness in parallel and return first alive one
    # We check in preference order so the first alive = the best alive
    alive_results = {}
    dead_urls = set()

    def _check_one(idx, c):
        if c.get("type") in ("embed", "raw"):
            alive_results[idx] = True
            return
        alive_results[idx] = _stream_is_alive(
            c["url"], c.get("type", "mp4"), c.get("referer")
        )
        if not alive_results[idx]:
            dead_urls.add(c["url"])

    with ThreadPoolExecutor(max_workers=min(len(candidates), 4)) as ex:
        futures = {ex.submit(_check_one, i, c): i for i, c in enumerate(candidates)}
        for f in as_completed(futures):
            try:
                f.result(timeout=12)
            except Exception:
                idx = futures[f]
                alive_results[idx] = False

    # Return first alive candidate (already sorted by preference)
    for i, c in enumerate(candidates):
        if alive_results.get(i, False):
            return c

    # All dead — return None instead of a dead URL
    return None


def resolve_all_mirrors(ep, max_workers=4, single_timeout=8):
    """Resolve every mirror for an episode in parallel and return list of {url,type,referer}."""
    found = []
    mirrors = ep.get("mirrors", {})
    if not mirrors:
        return found

    ordered_keys = sorted(mirrors.keys(), key=lambda x: int(x[3:]))

    def resolve_one(k):
        u = mirrors[k]
        try:
            r = resolve_episode_url(u)
            if r and r.get("url"):
                r.setdefault("referer", u)
                return r
        except Exception:
            pass
        return None

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut_map = {ex.submit(resolve_one, k): k for k in ordered_keys}
        for f in as_completed(fut_map):
            try:
                r = f.result(timeout=single_timeout)
                if r:
                    results.append(r)
            except Exception:
                pass

    seen = set()
    raw_items = []
    for r in results:
        if r["url"] not in seen:
            seen.add(r["url"])
            if r.get("type") == "raw":
                raw_items.append(r)
            else:
                found.append(r)

    if raw_items:
        deeper_found = []
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            fut_map = {ex.submit(resolve_generic, r["url"]): r for r in raw_items}
            for f in as_completed(fut_map):
                r = fut_map[f]
                try:
                    deeper = f.result(timeout=single_timeout)
                    if deeper and deeper.get("url") and deeper["url"] not in seen and deeper.get("type") != "raw":
                        deeper.setdefault("referer", r.get("referer", r["url"]))
                        seen.add(deeper["url"])
                        deeper_found.append(deeper)
                    else:
                        deeper_found.append(r)
                except Exception:
                    deeper_found.append(r)
        found.extend(deeper_found)

    return found


def pick_mirror(ep):
    """Let user pick a mirror if multiple resolutions/types exist."""
    all_resolved = resolve_all_mirrors(ep)
    if not all_resolved:
        return None
    if len(all_resolved) == 1:
        return all_resolved[0]

    def sort_key(r):
        t = r.get("type", "raw")
        return {"mp4": 0, "webm": 1, "m3u8": 2, "raw": 3}.get(t, 3)

    all_resolved.sort(key=sort_key)

    choices = []
    for i, r in enumerate(all_resolved, 1):
        t = r.get("type", "raw").upper()
        u = r["url"]
        host = urlparse(u).netloc
        choices.append(f"{i}. [{t}] {host}")
    choices.append("Auto (best)")
    choices.append(BACK)

    sel = questionary.select(
        "Select a video source",
        style=QS,
        choices=choices,
        instruction="↑/↓ select · Enter confirm · Esc back"
    ).ask()
    if not sel or sel == BACK:
        return None
    if sel == "Auto (best)":
        return resolve_best_mirror(ep)
    idx = int(sel.split(".")[0]) - 1
    return all_resolved[idx]


def convert_m3u8_to_mp4(m3u8_url, out_path, referer=None):
    """Fast m3u8 → mp4 remux using ffmpeg with -c copy (no re-encoding)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        cmd = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-fflags", "+discardcorrupt",
            "-i", m3u8_url,
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            "-movflags", "+faststart",
            str(out_path),
        ]
        if referer:
            cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                   "-fflags", "+discardcorrupt",
                   "-headers", f"Referer: {referer}\r\n",
                   "-i", m3u8_url, "-c", "copy", "-bsf:a", "aac_adtstoasc",
                   "-movflags", "+faststart", str(out_path)]
        try:
            subprocess.run(cmd, check=True, timeout=600)
            if out_path.exists() and out_path.stat().st_size > 0:
                return out_path
        except Exception:
            pass

    yt = shutil.which("yt-dlp")
    if yt:
        try:
            subprocess.run([yt, "-o", str(out_path), "--no-playlist", "--no-progress",
                            "--remux-video", "mp4", m3u8_url],
                           check=True, timeout=600)
            if out_path.exists() and out_path.stat().st_size > 0:
                return out_path
        except Exception:
            pass

    return None


def sanitize(name):
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()
