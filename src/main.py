import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import click
import httpx
import questionary
from questionary import Style as QStyle
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from . import __version__, __app_name__, cache, player as player_mod, scraper, search, resolver
from .config import RESOLVER_HEADERS

console = Console()
BACK = "<  Back"

# Rich style tokens
ST = {
    "title": "bold blue",
    "sel": "cyan",
    "ok": "green",
    "err": "red",
    "dim": "dim white",
    "accent": "bold cyan",
    "score_hi": "bold green",
    "score_mid": "yellow",
    "score_lo": "red",
}

# Questionary theme: keeps the prompt clean and minimal
QS = QStyle([
    ("qmark", "fg:cyan bold"),
    ("question", "fg:cyan bold"),
    ("answer", "fg:green bold"),
    ("pointer", "fg:cyan bold"),
    ("highlighted", "fg:cyan bold"),
    ("selected", "fg:green"),
    ("separator", "fg:white"),
    ("instruction", "fg:#888888"),
    ("text", "fg:white"),
])


def score_badge_plain(s):
    c = int(round(s))
    if c >= 80:
        return f"[green]{c}%[/green]"
    elif c >= 60:
        return f"[yellow]{c}%[/yellow]"
    return f"[red]{c}%[/red]"


def score_badge(s):
    c = int(round(s))
    if c >= 80:
        return f"[{ST['score_hi']}]{c}%[/{ST['score_hi']}]"
    elif c >= 60:
        return f"[{ST['score_mid']}]{c}%[/{ST['score_mid']}]"
    return f"[{ST['score_lo']}]{c}%[/{ST['score_lo']}]"


def section_header(text, subtitle=None):
    parts = [f"[{ST['accent']}]{text}[/{ST['accent']}]"]
    if subtitle:
        parts.append(f"[{ST['dim']}]{subtitle}[/{ST['dim']}]")
    console.print("  ".join(parts))
    console.print()


def status_line(key, value, color="white"):
    console.print(f"  [{ST['dim']}]{key}:[/{ST['dim']}] [{color}]{value}[/{color}]")


def note(msg):
    console.print(f"[{ST['dim']}]{msg}[/{ST['dim']}]")


def ok(msg):
    console.print(f"[{ST['ok']}]✓ {msg}[/{ST['ok']}]")


def err(msg):
    console.print(f"[{ST['err']}]✗ {msg}[/{ST['err']}]")


def parse_range(txt):
    res = set()
    for p in txt.split(","):
        p = p.strip()
        if not p:
            continue
        if "-" in p:
            try:
                s, e = p.split("-", 1)
                s, e = int(s.strip()), int(e.strip())
                res.update(range(s, e + 1))
            except ValueError:
                continue
        else:
            try:
                res.add(int(p))
            except ValueError:
                continue
    return sorted(res)


def ensure_catalog(domain, force=False, settings=None):
    if not settings:
        settings = cache.load_settings()
    if force or not cache.is_cache_valid():
        if not cache.CATALOG_FILE.exists() or settings.get("auto_fetch_github", True):
            cat = with_spinner("Downloading catalog from GitHub...", cache.fetch_github_catalog)
            if cat:
                ok(f"Catalog downloaded from GitHub: {len(cat)} anime")
        if settings.get("auto_fetch_new", True) or force:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as p:
                p.add_task("Updating catalog with new entries...", total=None)
                cat = cache.download_combined_catalog(domain)
            ok(f"Catalog updated: {len(cat)} anime")
            return cat
    return cache.load_combined_catalog(domain)


def filter_seasons(s):
    return [x for x in s if "scan" not in x["name"].lower()]


def with_spinner(desc, fn, *args, **kwargs):
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console, transient=True) as p:
        p.add_task(desc, total=None)
        return fn(*args, **kwargs)


def show_banner():
    ln = [
        f"[{ST['title']}]    ___    _   ___________ ___    __  ______ [/{ST['title']}]",
        f"[{ST['title']}]   /   |  / | / /  _/ ___//   |  /  |/  /   |[/{ST['title']}]",
        f"[{ST['title']}]  / /| | /  |/ // / \\__ \\/ /| | / /|_/ / /| |[/{ST['title']}]",
        f"[{ST['title']}] / ___ |/ /|  // / ___/ / ___ |/ /  / / ___ |[/{ST['title']}]",
        f"[{ST['title']}]/_/  |_/_/ |_/___//____/_/  |_/_/  /_/_/  |_|[/{ST['title']}]",
        f"[{ST['title']}]                                             [/{ST['title']}]",
    ]
    panel = Panel(
        "\n".join(ln),
        subtitle=f"[{ST['accent']}]Anime-Sama CLI[/{ST['accent']}]  [{ST['dim']}]v{__version__}[/{ST['dim']}]",
        border_style="blue", padding=(0, 1)
    )
    console.print(panel)


def show_anime_info(anime):
    g = anime.get("genres", [])
    src = anime.get("alt_source", anime.get("source", ""))
    lines = []
    info_ok = False

    # Build info from AniList
    try:
        import httpx
        query_anilist = """
        query ($s: String) {
          Page(perPage: 5) {
            media(search: $s, type: ANIME, sort: SEARCH_MATCH) {
              title { romaji english }
              averageScore
              status
              episodes
              duration
              studios { nodes { name } }
              genres
              seasonYear
              description(asHtml: false)
              source
              format
            }
          }
        }"""
        r = httpx.post("https://graphql.anilist.co",
                        json={"query": query_anilist, "variables": {"s": anime["title"]}},
                        timeout=8)
        if r.status_code == 200:
            results = r.json().get("data", {}).get("Page", {}).get("media", [])
            if results:
                from rapidfuzz import fuzz as rfuzz
                best = None
                best_s = 0
                q = anime["title"].lower()
                for m in results:
                    for t in [m["title"].get("romaji", ""), m["title"].get("english", "")]:
                        if not t:
                            continue
                        s = rfuzz.ratio(q, t.lower())
                        if s > best_s:
                            best_s = s
                            best = m
                a = best or results[0]
                if a.get("averageScore"):
                    lines.append(f"[{ST['dim']}]Score:[/{ST['dim']}] {score_badge(a['averageScore'])}")
                    info_ok = True
                parts = []
                if a.get("status"):
                    parts.append(a["status"].replace("_", " ").title())
                if a.get("format"):
                    parts.append(a["format"])
                if a.get("episodes"):
                    parts.append(f"{a['episodes']} eps")
                if a.get("duration"):
                    parts.append(f"{a['duration']} min")
                if a.get("seasonYear"):
                    parts.append(str(a["seasonYear"]))
                if a.get("source"):
                    parts.append(a["source"].replace("_", " ").title())
                if parts:
                    lines.append(f"[{ST['dim']}]{'  .  '.join(parts)}[/{ST['dim']}]")
                if a.get("studios"):
                    st_names = [s["name"] for s in a["studios"]["nodes"]]
                    if st_names:
                        lines.append(f"[{ST['dim']}]Studios:[/{ST['dim']}] {', '.join(st_names[:4])}")
                if a.get("genres"):
                    lines.append(f"[{ST['dim']}]Tags:[/{ST['dim']}] {', '.join(a['genres'][:10])}")
                if a.get("description"):
                    desc = a["description"].replace("<br>", " ").replace("<i>", "").replace("</i>", "")[:300]
                    lines.append("")
                    lines.append(f"[{ST['dim']}]{desc}[/{ST['dim']}]")
                    info_ok = True
    except Exception:
        pass

    if not info_ok:
        try:
            import httpx
            r = httpx.get("https://api.jikan.moe/v4/anime", params={"q": anime["title"], "limit": 1}, timeout=8)
            if r.status_code == 200:
                d = r.json()
                if d.get("data"):
                    a = d["data"][0]
                    if a.get("score"):
                        lines.append(f"[{ST['dim']}]Score:[/{ST['dim']}] {score_badge(a['score'])}")
                        info_ok = True
                    parts = []
                    if a.get("status"):
                        parts.append(a["status"].replace("_", " ").title())
                    if a.get("episodes"):
                        parts.append(f"{a['episodes']} eps")
                    if a.get("duration"):
                        parts.append(a["duration"])
                    yr = a.get("year") or a.get("aired", {}).get("prop", {}).get("from", {}).get("year")
                    if yr:
                        parts.append(str(yr))
                    if a.get("rating"):
                        parts.append(a["rating"])
                    if parts:
                        lines.append(f"[{ST['dim']}]{'  .  '.join(parts)}[/{ST['dim']}]")
                    if a.get("studios"):
                        st_names = [s["name"] for s in a["studios"]]
                        if st_names:
                            lines.append(f"[{ST['dim']}]Studios:[/{ST['dim']}] {', '.join(st_names[:4])}")
                    if a.get("genres"):
                        jgenres = [x["name"] for x in a["genres"]]
                        if jgenres:
                            lines.append(f"[{ST['dim']}]Tags:[/{ST['dim']}] {', '.join(jgenres[:10])}")
                    if a.get("synopsis"):
                        syn = a["synopsis"][:300]
                        lines.append("")
                        lines.append(f"[{ST['dim']}]{syn}[/{ST['dim']}]")
                        info_ok = True
        except Exception:
            pass

    if not info_ok and not g:
        lines.append(f"[{ST['dim']}]No info available[/{ST['dim']}]")

    # Source / genres metadata
    meta = []
    if isinstance(src, list) and src:
        meta.append(f"[{ST['dim']}]Also on:[/{ST['dim']}] [{ST['sel']}]{', '.join(src)}[/{ST['sel']}]")
    if g:
        meta.append(f"[{ST['dim']}]Genres:[/{ST['dim']}] {', '.join(g[:6])}")
    if meta:
        lines.insert(0, "  .  ".join(meta))

    console.print(Panel("\n".join(lines), title=f"[{ST['title']}]{anime['title']}[/{ST['title']}]",
                        border_style="cyan", padding=(1, 2)))


PAGE_SIZE = 10
NEXT = ">  Next page"
PREV = "<  Previous page"


def pick_anime(results):
    if not results:
        err("No results found. Try a different search term.")
        return None

    total = len(results)
    offset = 0
    while True:
        page = results[offset:offset + PAGE_SIZE]
        choices = []
        for r in page:
            src = r.get("source", "")
            tag = f" ({src})" if src and src != "catalog" else ""
            sc = int(round(r["score"]))
            choices.append(f"{r['title']}{tag}  [{sc}%]")
        if offset + PAGE_SIZE < total:
            choices.append(NEXT)
        if offset > 0:
            choices.append(PREV)
        choices.append(BACK)

        header = f"Search results ({offset + 1}-{min(offset + PAGE_SIZE, total)}/{total})"
        sel = questionary.select(
            header,
            style=QS,
            choices=choices,
            instruction="↑/↓ select · Enter confirm · Esc back"
        ).ask()
        if not sel or sel == BACK:
            return None
        if sel == NEXT:
            offset += PAGE_SIZE
            continue
        if sel == PREV:
            offset = max(0, offset - PAGE_SIZE)
            continue

        anime = results[offset + choices.index(sel)]
        console.clear()
        show_anime_info(anime)
        c = questionary.confirm("Continue with this anime?", style=QS, default=True).ask()
        if c:
            return anime


def pick_season(seasons):
    if not seasons:
        err("No seasons available.")
        return None

    choices = [s["name"] for s in seasons] + [BACK]
    sel = questionary.select(
        "Select a season",
        style=QS,
        choices=choices,
        instruction="↑/↓ select · Enter confirm · Esc back"
    ).ask()
    if not sel or sel == BACK:
        return None
    return next(s for s in seasons if s["name"] == sel)


def pick_ep(ep_data, total):
    choices = [f"Episode {e['number']}" for e in ep_data] + ["Download / play range...", BACK]
    sel = questionary.select(
        f"Select an episode (1-{total})",
        style=QS,
        choices=choices,
        instruction="↑/↓ select · Enter confirm · Esc back"
    ).ask()
    if not sel or sel == BACK:
        return None

    if sel == "Download / play range...":
        r = questionary.text("Enter episode range (e.g. 1-5 or 1,3,5):", style=QS).ask()
        if not r:
            return None
        nums = parse_range(r)
        nums = [e for e in nums if 1 <= e <= total]
        if not nums:
            err(f"Invalid range. Must be 1-{total}.")
            return None
        return nums

    return [int(sel.replace("Episode ", ""))]


def pick_lang(available_langs):
    if not available_langs:
        return None
    if len(available_langs) == 1:
        return list(available_langs)[0]
    sel = questionary.select(
        "Select a language",
        style=QS,
        choices=sorted(available_langs),
        instruction="↑/↓ select · Enter confirm · Esc back"
    ).ask()
    return sel


def pick_player(pref=None):
    if pref:
        p = player_mod.find_player(pref)
        if p:
            return p
        note(f"Player '{pref}' not found, detecting available players...")

    avail = player_mod.detect_players()
    if not avail:
        note("No player detected (mpv/vlc/iina/moonplayer/implay).")
        note("Install mpv and add it to PATH, or set a custom path in settings.")
        return None

    if len(avail) == 1:
        return next(iter(avail.values()))

    sel = questionary.select(
        "Select a player",
        style=QS,
        choices=list(avail.keys()),
        instruction="↑/↓ select · Enter confirm · Esc back"
    ).ask()
    return avail.get(sel) if sel else None


PREF_HOSTS = ["sendvid", "vidmoly", "smoothpre", "vidhide", "streamwish", "oneupload", "sibnet"]
MP4_HOSTS = ["sendvid", "oneupload", "sibnet"]


def test_url_speed(url, referer=None, sample_bytes=512000):
    """Measure download speed of a URL by fetching the first sample_bytes.
    Returns bytes per second, or 0 on failure.
    """
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


def pick_fastest_mirror(ep, prefer_mp4=True, test_speed=True, quiet=False):
    """Resolve all mirrors, optionally speed-test them, and return the fastest playable source."""
    candidates = resolve_all_mirrors(ep)
    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    if test_speed:
        # Speed-test in parallel using ThreadPoolExecutor
        from concurrent.futures import ThreadPoolExecutor, as_completed
        speeds = {}
        with ThreadPoolExecutor(max_workers=4) as ex:
            fut_map = {ex.submit(test_url_speed, c["url"], c.get("referer")): i for i, c in enumerate(candidates)}
            for f in as_completed(fut_map):
                i = fut_map[f]
                try:
                    speeds[i] = f.result()
                except Exception:
                    speeds[i] = 0

        # Sort: prefer MP4, then by speed. RAW pages get 0 speed so they drop to bottom.
        def sort_key(item):
            i, c = item
            t = c.get("type", "raw")
            type_rank = {"mp4": 0, "webm": 1, "m3u8": 2, "raw": 3}.get(t, 3)
            speed = speeds.get(i, 0)
            # If we prefer mp4, boost mp4/webm speed artificially so they win over slightly faster m3u8
            if prefer_mp4 and t in ("mp4", "webm"):
                speed = speed * 2 + 1_000_000
            return (type_rank, -speed)

        ranked = sorted(enumerate(candidates), key=sort_key)
        best_idx, best = ranked[0]
        if not quiet:
            for i, c in ranked[:3]:
                spd = speeds.get(i, 0)
                spd_str = format_speed(spd) if spd > 0 else "unreachable"
                note(f"  {c.get('type','raw').upper():6} {spd_str:<12} {urlparse(c['url']).netloc}")
        return best

    # No speed test: just prefer mp4
    candidates.sort(key=lambda c: {"mp4": 0, "webm": 1, "m3u8": 2, "raw": 3}.get(c.get("type", "raw"), 3))
    return candidates[0]


def resolve_best_mirror(ep, prefer_mp4=True):
    """Resolve a single best mirror. Prefers known hosts, then speed if possible."""
    settings = cache.load_settings()
    pref = settings.get("preferred_hosts", "")
    if pref:
        hosts = [h.strip() for h in pref.split(",") if h.strip()]
    else:
        hosts = PREF_HOSTS
    mirrors = ep.get("mirrors", {})
    if not mirrors:
        return None

    def try_mirror(u, want_type=None):
        r = scraper.resolve_episode_url(u)
        if r and r.get("url"):
            r["referer"] = u
            if want_type and r.get("type") != want_type:
                return None
            return r
        return None

    if prefer_mp4:
        mp4_hosts = [h for h in hosts if h in MP4_HOSTS] or MP4_HOSTS
        for h in mp4_hosts:
            for k in sorted(mirrors.keys(), key=lambda x: int(x[3:])):
                u = mirrors[k]
                if h in u.lower():
                    r = try_mirror(u, want_type="mp4")
                    if r:
                        return r
        for k in sorted(mirrors.keys(), key=lambda x: int(x[3:])):
            u = mirrors[k]
            r = try_mirror(u, want_type="mp4")
            if r:
                return r

    for h in hosts:
        for k in sorted(mirrors.keys(), key=lambda x: int(x[3:])):
            u = mirrors[k]
            if h in u.lower():
                r = try_mirror(u)
                if r and r.get("type") != "raw":
                    return r

    for k in sorted(mirrors.keys(), key=lambda x: int(x[3:])):
        u = mirrors[k]
        r = try_mirror(u)
        if r:
            return r
    return None


def resolve_all_mirrors(ep):
    """Resolve every mirror for an episode and return list of {url,type,referer}."""
    found = []
    mirrors = ep.get("mirrors", {})
    if not mirrors:
        return found
    seen = set()
    raw_items = []
    for k in sorted(mirrors.keys(), key=lambda x: int(x[3:])):
        u = mirrors[k]
        r = scraper.resolve_episode_url(u)
        if r and r.get("url") and r["url"] not in seen:
            r.setdefault("referer", u)
            seen.add(r["url"])
            if r.get("type") == "raw":
                raw_items.append(r)
            else:
                found.append(r)

    # Try harder on raw URLs using generic embed resolver
    for r in raw_items:
        deeper = resolver.resolve_generic(r["url"])
        if deeper and deeper.get("url") and deeper["url"] not in seen and deeper.get("type") != "raw":
            deeper.setdefault("referer", r.get("referer", r["url"]))
            seen.add(deeper["url"])
            found.append(deeper)
        else:
            found.append(r)
    return found


def pick_mirror(ep):
    """Let user pick a mirror if multiple resolutions/types exist."""
    all_resolved = resolve_all_mirrors(ep)
    if not all_resolved:
        return None
    if len(all_resolved) == 1:
        return all_resolved[0]

    # Sort playable first: mp4 > m3u8 > raw
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


def check_ytdlp():
    return shutil.which("yt-dlp") is not None


def install_ytdlp_guide():
    console.print()
    console.print(Panel(
        "[bold]yt-dlp is an optional but powerful tool to resolve video URLs from many embed sites.[/bold]\n\n"
        "It can extract direct MP4/m3u8 URLs from hosts like minochinos, embed4me, and many others.\n\n"
        "[bold]How to install yt-dlp:[/bold]\n"
        "Windows:   winget install yt-dlp\n"
        "           pip install yt-dlp\n"
        "Linux:     pip install yt-dlp   or   sudo apt install yt-dlp\n"
        "macOS:     brew install yt-dlp   or   pip install yt-dlp\n\n"
        "After installation, restart your terminal.",
        title="[bold cyan]Install yt-dlp[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print()


def install_ytdlp_interactive():
    """Offer to install yt-dlp automatically on Windows, Linux, or macOS."""
    if check_ytdlp():
        ok("yt-dlp is already installed.")
        return True

    sys_name = platform.system()
    console.print()
    note("yt-dlp not found. It helps resolve many embed sites.")
    c = questionary.confirm(
        f"Try to install yt-dlp automatically on {sys_name}?",
        style=QS,
        default=True,
    ).ask()
    if not c:
        install_ytdlp_guide()
        return False

    installers = {
        "Windows": [
            ("winget", ["winget", "install", "yt-dlp", "--accept-source-agreements", "--accept-package-agreements", "--disable-interactivity"]),
            ("pip", ["pip", "install", "yt-dlp"]),
        ],
        "Linux": [
            ("pip", ["pip", "install", "yt-dlp"]),
            ("apt", ["apt-get", "install", "-y", "yt-dlp"]),
        ],
        "Darwin": [
            ("brew", ["brew", "install", "yt-dlp"]),
            ("pip", ["pip", "install", "yt-dlp"]),
        ],
    }

    candidates = installers.get(sys_name, [])
    for name, cmd in candidates:
        exe = shutil.which(name)
        if not exe:
            continue
        try:
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                          console=console, transient=True) as p:
                p.add_task(f"Installing yt-dlp via {name}...", total=None)
                subprocess.run([exe] + cmd[1:], check=True, timeout=300)
            ok(f"yt-dlp installed via {name}.")
            note("You may need to restart your terminal for PATH changes to take effect.")
            return True
        except Exception as e:
            err(f"{name} install failed: {e}")
            continue

    err("Automatic install failed on your system.")
    install_ytdlp_guide()
    return False


def check_ffmpeg():
    return shutil.which("ffmpeg") is not None


def install_ffmpeg_guide():
    console.print()
    console.print(Panel(
        "[bold]ffmpeg is required for fast m3u8 → mp4 conversion.[/bold]\n\n"
        "The conversion uses '-c copy' (no re-encoding), so it is as fast as your internet connection.\n\n"
        "[bold]Why convert?[/bold]\n"
        "m3u8/HLS streams load segment by segment, which can be slow to start and seek.\n"
        "MP4 is a single file that players can buffer instantly and seek faster.\n\n"
        "[bold]How to install ffmpeg on Windows:[/bold]\n"
        "1. winget:    winget install Gyan.FFmpeg\n"
        "2. choco:     choco install ffmpeg\n"
        "Windows:   winget install Gyan.FFmpeg\\n"
        "           choco install ffmpeg\\n"
        "           https://www.gyan.dev/ffmpeg/builds/\\n\\n"
        "Linux:     sudo apt install ffmpeg\\n"
        "           sudo dnf install ffmpeg\\n"
        "           sudo pacman -S ffmpeg\\n\\n"
        "macOS:     brew install ffmpeg\\n\\n"
        "After installation, restart your terminal and run anisama again.",
        title="[bold cyan]Install ffmpeg[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print()


def explain_auto_convert():
    console.print()
    console.print(Panel(
        "[bold]Auto-convert downloads to MP4[/bold]\n\n"
        "When enabled, any episode that only resolves to an HLS/m3u8 stream will be "
        "converted to a single MP4 file during download.\n\n"
        "[bold]Why?[/bold]\n"
        "• MP4 starts instantly in players, no segment loading delay.\n"
        "• MP4 is a single file, easier to keep, share, and seek.\n"
        "• m3u8 requires downloading many small segments, which is slower and fragile.\n\n"
        "[bold]Is it fast?[/bold]\n"
        "Yes. The conversion uses ffmpeg with '-c copy', meaning it copies the video/audio "
        "streams without re-encoding. Speed is limited only by your internet, not CPU.\n\n"
        "[bold]Required tool:[/bold] ffmpeg\n"
        "If ffmpeg is missing, anisama will prompt you to install it when you enable this option.",
        title="[bold cyan]Auto-convert MP4[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print()


def install_ffmpeg_interactive():
    """Offer to install ffmpeg automatically on Windows, Linux, or macOS with user consent."""
    if check_ffmpeg():
        ok("ffmpeg is already installed.")
        return True

    sys_name = platform.system()
    console.print()
    note("ffmpeg not found. It is needed for fast m3u8 → mp4 conversion.")
    c = questionary.confirm(
        f"Try to install ffmpeg automatically on {sys_name}?",
        style=QS,
        default=True,
    ).ask()
    if not c:
        install_ffmpeg_guide()
        return False

    installers = {
        "Windows": [
            ("winget", ["winget", "install", "Gyan.FFmpeg", "--accept-source-agreements", "--accept-package-agreements", "--disable-interactivity"]),
            ("choco", ["choco", "install", "ffmpeg", "-y"]),
        ],
        "Linux": [
            ("apt", ["apt-get", "install", "-y", "ffmpeg"]),
            ("dnf", ["dnf", "install", "-y", "ffmpeg"]),
            ("pacman", ["pacman", "-S", "--noconfirm", "ffmpeg"]),
            ("snap", ["snap", "install", "ffmpeg"]),
        ],
        "Darwin": [
            ("brew", ["brew", "install", "ffmpeg"]),
        ],
    }

    candidates = installers.get(sys_name, [])
    for name, cmd in candidates:
        exe = shutil.which(name)
        if not exe:
            continue
        try:
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                          console=console, transient=True) as p:
                p.add_task(f"Installing ffmpeg via {name}...", total=None)
                subprocess.run([exe] + cmd[1:], check=True, timeout=600)
            ok(f"ffmpeg installed via {name}.")
            note("You may need to restart your terminal for PATH changes to take effect.")
            return True
        except Exception as e:
            err(f"{name} install failed: {e}")
            continue

    err("Automatic install failed on your system.")
    install_ffmpeg_guide()
    return False


def sanitize(name):
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()


def show_info(domain, catalog):
    console.print()
    status_line("Domain", domain, ST['sel'])
    status_line("Catalog", f"{len(catalog)} anime", ST['sel'])
    console.print()


def search_all(query, catalog, domain, max_res=100, quiet=False):
    results = search.search_combined(query, catalog, domain=domain, limit=max_res)
    if results:
        return results

    if not quiet:
        note("Not in catalog, searching Voiranime live...")
    vr = search.search_voiranime(query)
    return vr[:max_res] if max_res else vr


def anime_flow(anime, lang, download, episodes, pref, quiet, dl_dir, settings,
               start_season_url=None, start_episode_num=None):
    """Run season/episode/player flow for a known anime object (used by Continue and workflow)."""
    auto_next = settings.get("auto_next", False)
    player_path = None
    source = anime.get("source", "catalog")
    url = anime["link"]

    if not quiet:
        ok(f"Selected: {anime['title']} ({source})")

    if source == "voiranime":
        voiranime_flow(anime, lang, download, episodes, pref, quiet, dl_dir, settings.get("keep_open", True), auto_next)
        return

    while True:
        all_s = with_spinner("Fetching seasons...", scraper.get_anime_seasons, url)
        seasons = filter_seasons(all_s)

        if lang:
            f = [s for s in seasons if f"/{lang}/" in s["url"] or s["url"].endswith(f"/{lang}")]
            if f:
                seasons = f
            elif not quiet:
                note(f"No '{lang}' seasons, showing all.")

        # If continuing from history with a known season, pre-select it
        if start_season_url and not episodes and start_episode_num is None:
            season = next((s for s in seasons if s["url"] == start_season_url), None)
            if season is None:
                season = pick_season(seasons)
        else:
            season = pick_season(seasons)
        if season is None:
            break

        s_url = season["url"]
        s_name = season.get("name", "")

        while True:
            eps = with_spinner("Fetching episodes...", scraper.get_episodes, s_url)
            if not eps:
                err("No episodes found.")
                break

            total = len(eps)

            if episodes:
                nums = parse_range(episodes)
                nums = [e for e in nums if 1 <= e <= total]
                if not nums:
                    err(f"Invalid range. Must be 1-{total}.")
                    break
            elif start_episode_num and not episodes:
                # Pre-select the episode from history
                nums = [start_episode_num]
                if not quiet:
                    ok(f"Resuming episode {start_episode_num}")
                start_episode_num = None
            else:
                r = pick_ep(eps, total)
                if r is None:
                    break
                nums = r

            if player_path is None and not download:
                player_path = pick_player(pref)
                if player_path is None:
                    break
                if not quiet:
                    ok(f"Player: {Path(player_path).name}")

            if download:
                download_eps(eps, nums, anime["title"], quiet, dl_dir, anime["link"], season_url=s_url, season_name=s_name)
            else:
                play_eps(eps, nums, player_path, quiet, settings.get("keep_open", True), anime["title"], anime["link"], season_url=s_url, season_name=s_name)
                d = ", ".join(str(e) for e in nums)
                ok(f"Episode {d} launched, enjoy!")
                if auto_next:
                    continue
                cont = questionary.confirm("Return to episode list?", style=QS, default=False).ask()
                if not cont:
                    break

            episodes = None
            continue


def workflow(query, lang, download, episodes, pref, quiet, domain, catalog, from_menu=False):
    if not quiet:
        if not from_menu:
            show_banner()
        show_info(domain, catalog)

    settings = cache.load_settings()
    dl_dir = settings.get("download_dir", "downloads")
    max_res = settings.get("max_results", 50)

    while True:
        if not query:
            q = questionary.text("Search anime:", style=QS).ask()
            if not q:
                err("No search term.")
                return
            query = q

        results = search_all(query, catalog, domain, max_res, quiet)
        if not results:
            note(f"No results for '{query}'.")
            query = None
            continue

        anime = pick_anime(results)
        if not anime:
            query = None
            continue

        anime_flow(anime, lang, download, episodes, pref, quiet, dl_dir, settings)
        query = None
        episodes = None


def voiranime_flow(anime, lang, download, episodes, pref, quiet, dl_dir="downloads", keep_open=True, auto_next=False):
    player_path = None
    url = anime["link"]
    title = anime["title"]

    while True:
        all_s = with_spinner("Fetching seasons...", scraper.voiranime_get_seasons, url)
        if not all_s:
            err("No seasons found.")
            return

        season = pick_season(all_s)
        if season is None:
            return

        available_langs = season.get("langs", set())
        chosen_lang = lang or pick_lang(available_langs)
        if not chosen_lang:
            note("No language selected.")
            return

        s_url = season["url"]
        if not quiet:
            ok(f"Language: {chosen_lang.upper()}")

        while True:
            eps = with_spinner("Fetching episodes...", scraper.voiranime_get_episodes, s_url, chosen_lang)
            if not eps:
                err("No episodes found for this language.")
                break

            total = len(eps)

            if episodes:
                nums = parse_range(episodes)
                nums = [e for e in nums if 1 <= e <= total]
                if not nums:
                    err(f"Invalid range. Must be 1-{total}.")
                    break
            else:
                r = pick_ep(eps, total)
                if r is None:
                    break
                nums = r

            if player_path is None and not download:
                player_path = pick_player(pref)
                if player_path is None:
                    break
                if not quiet:
                    ok(f"Player: {Path(player_path).name}")

            if download:
                voiranime_download(eps, nums, title, chosen_lang, quiet, dl_dir, url, season_url=s_url, season_name=season.get("name", ""))
            else:
                voiranime_play(eps, nums, chosen_lang, player_path, quiet, keep_open, title, url, season_url=s_url, season_name=season.get("name", ""))
                d = ", ".join(str(e) for e in nums)
                ok(f"Episode {d} launched, enjoy!")
                if auto_next:
                    continue
                cont = questionary.confirm("Return to episode list?", style=QS, default=False).ask()
                if not cont:
                    break

            episodes = None
            continue


def voiranime_play(eps, nums, lang, player_path, quiet, keep_open=True, title="", url_orig="", season_url=None, season_name=None):
    for n in nums:
        e = eps[n - 1]
        ep_url = e["url"]
        if not quiet:
            console.print(f"\n[{ST['sel']}]Episode {n}:[/{ST['sel']}] Resolving video URL...")
        r = with_spinner("Resolving...", resolver.resolve_voiranime_episode, ep_url, lang)
        if not r:
            err(f"Failed to resolve episode {n}.")
            continue
        if not quiet:
            ok(f"Playing episode {n}...")
        player_mod.play_url(r["url"], player_path, ep_url, keep_open)
        cache.add_history(title, url_orig, "voiranime", n, season_url=season_url, season_name=season_name)


def voiranime_download(eps, nums, title, lang, quiet, dl_dir="downloads", url_orig="", season_url=None, season_name=None):
    d = Path.cwd() / dl_dir / sanitize(title)
    for n in nums:
        e = eps[n - 1]
        ep_url = e["url"]
        if not quiet:
            console.print(f"\n[{ST['sel']}]Episode {n}:[/{ST['sel']}] Resolving video URL...")
        r = with_spinner("Resolving...", resolver.resolve_voiranime_episode, ep_url, lang)
        if not r:
            err(f"Failed to resolve episode {n}.")
            continue
        ext = "mp4"
        fname = f"E{n:02d}.{ext}"
        if not quiet:
            ok(f"Downloading episode {n}...")
        out = player_mod.download_url(r["url"], d, fname)
        if out and out.exists():
            ok(f"Downloaded: {out}")
            cache.add_history(title, url_orig, "voiranime", n, season_url=season_url, season_name=season_name)


def _resolve_episode(e, n, quiet, prefer_mp4=True, allow_pick=False):
    """Resolve an episode, preferring MP4 and speed-testing sources. Returns resolved dict or None."""
    if not quiet:
        console.print(f"\n[{ST['sel']}]Episode {n}:[/{ST['sel']}] Resolving video URL...")

    # Auto-pick with speed test and MP4 preference
    r = pick_fastest_mirror(e, prefer_mp4=prefer_mp4, test_speed=True, quiet=quiet)
    if not r:
        err(f"Failed to resolve episode {n}.")
        return None

    if not quiet:
        ok(f"Best source: {r.get('type','raw').upper()} from {urlparse(r['url']).netloc}")

    return r


def download_eps(eps, nums, title, quiet, dl_dir="downloads", anime_link="", season_url=None, season_name=None):
    settings = cache.load_settings()
    prefer_mp4 = settings.get("prefer_mp4", True)
    auto_convert = settings.get("auto_convert_mp4", True)
    d = Path.cwd() / dl_dir / sanitize(title)
    for n in nums:
        e = eps[n - 1]
        r = _resolve_episode(e, n, quiet, prefer_mp4=prefer_mp4, allow_pick=True)
        if not r:
            continue

        ext = "mp4"
        fname = f"E{n:02d}.{ext}"
        out = d / fname

        # If source is m3u8 and user wants mp4 conversion, try ffmpeg fast remux
        if r.get("type") == "m3u8" and (prefer_mp4 or auto_convert):
            if not check_ffmpeg() and auto_convert:
                if not quiet:
                    note("ffmpeg not found. Conversion needs ffmpeg for fast m3u8 → mp4.")
                install_ffmpeg_interactive()
            if check_ffmpeg():
                if not quiet:
                    ok(f"Converting episode {n} from HLS to MP4 (fast remux, speed-limited by your connection)...")
                converted = convert_m3u8_to_mp4(r["url"], out, referer=r.get("referer"))
                if converted and converted.exists():
                    ok(f"Downloaded: {converted}")
                    cache.add_history(title, anime_link, "anime-sama", n, season_url=season_url, season_name=season_name)
                    continue
                if not quiet:
                    err("HLS conversion failed, falling back to direct download...")
            elif not quiet:
                note("Skipping conversion (ffmpeg not available). Downloading HLS stream directly...")

        if not quiet:
            ok(f"Downloading episode {n} ({r.get('type', 'raw')})...")
        out = player_mod.download_url(r["url"], d, fname)
        if out and out.exists():
            ok(f"Downloaded: {out}")
            cache.add_history(title, anime_link, "anime-sama", n, season_url=season_url, season_name=season_name)


def play_eps(eps, nums, player_path, quiet, keep_open=True, anime_title="", anime_link="", season_url=None, season_name=None):
    settings = cache.load_settings()
    prefer_mp4 = settings.get("prefer_mp4", True)
    for n in nums:
        e = eps[n - 1]
        r = _resolve_episode(e, n, quiet, prefer_mp4=prefer_mp4, allow_pick=True)
        if not r:
            continue
        if not quiet:
            ok(f"Playing episode {n} ({r.get('type', 'raw')})...")
        player_mod.play_url(r["url"], player_path, r.get("referer"), keep_open)
        cache.add_history(anime_title, anime_link, "anime-sama", n, season_url=season_url, season_name=season_name)


@click.command(context_settings=dict(help_option_names=["-h", "--help"]))
@click.argument("query", required=False)
@click.option("--lang", default=None, type=click.Choice(["vostfr", "vf"]), help="Language (vostfr or vf)")
@click.option("--dub", is_flag=True, help="Shorthand for VF (French dub)")
@click.option("--download", "-d", is_flag=True, help="Download instead of playing")
@click.option("--episodes", "-e", default=None, help="Episode(s): single (5), range (1-5), or list (1,3,5)")
@click.option("--player", "-p", default=None, help="Video player (mpv, vlc, iina, moonplayer, implay)")
@click.option("--update", "-U", is_flag=True, help="Force update the anime catalog")
@click.option("--settings", "-s", "show_settings", is_flag=True, help="Open settings menu")
@click.option("--quiet", "-q", is_flag=True, help="Reduce output verbosity")
@click.version_option(version=__version__, prog_name=__app_name__)
def cli(query, lang, dub, download, episodes, player, update, show_settings, quiet):
    """Browse and watch anime from Anime-Sama (VOSTFR/VF)."""
    if dub:
        lang = "vf"

    cli_lang = lang
    cli_download = download

    if show_settings:
        settings_menu()
        return

    settings = cache.load_settings()
    if not lang and settings.get("lang"):
        lang = settings["lang"]
    if not player and settings.get("player"):
        player = settings["player"]
    if not download and settings.get("default_download", False):
        download = True
    if settings.get("proxy"):
        os.environ["HTTP_PROXY"] = settings["proxy"]
        os.environ["HTTPS_PROXY"] = settings["proxy"]

    no_cli = not any([cli_download, episodes, player, update, quiet, dub, cli_lang])

    if not query and no_cli:
        while True:
            console.clear()
            show_banner()
            recent = cache.get_recent_anime()
            choices = ["Search"]
            if recent:
                choices.append(f"Continue ({len(recent)} recent)")
            choices.append("Settings")
            choice = questionary.select(
                "Main menu",
                style=QS,
                choices=choices,
                instruction="↑/↓ select · Enter confirm · Esc back"
            ).ask()
            if not choice:
                return
            if choice.startswith("Continue"):
                continue_menu(recent)
                continue
            if choice == "Settings":
                settings_menu()
                continue
            query = questionary.text("Search anime:", style=QS).ask()
            if query:
                break

    if not query:
        return

    domain = scraper.find_active_domain()
    if not domain:
        err("Could not reach any Anime-Sama domain.")
        sys.exit(1)

    catalog = ensure_catalog(domain, force=update, settings=settings)
    workflow(query, lang, download, episodes, player, quiet, domain, catalog, from_menu=no_cli)


def settings_menu():
    s = cache.load_settings()
    while True:
        choices = [
            f"Default language: {s.get('lang') or 'None'}",
            f"Default player: {s.get('player') or 'Auto'}",
            f"Auto-update catalog: {'Yes' if s.get('auto_update', True) else 'No'}",
            f"Auto-fetch GitHub catalog: {'Yes' if s.get('auto_fetch_github', True) else 'No'}",
            f"Auto-fetch new anime: {'Yes' if s.get('auto_fetch_new', True) else 'No'}",
            f"Download directory: {s.get('download_dir', 'downloads')}",
            f"Auto-play next episode: {'Yes' if s.get('auto_next', False) else 'No'}",
            f"Default download mode: {'Yes' if s.get('default_download', False) else 'No'}",
            f"Max search results: {s.get('max_results', 50)}",
            f"Cache max hours: {s.get('cache_hours', 24)}",
            f"Preferred hosts: {s.get('preferred_hosts', 'sendvid,vidmoly,...')}",
            f"Keep player open: {'Yes' if s.get('keep_open', True) else 'No'}",
            f"Prefer MP4 over HLS: {'Yes' if s.get('prefer_mp4', True) else 'No'}",
            f"Auto-convert downloads to MP4: {'Yes' if s.get('auto_convert_mp4', True) else 'No'}",
            f"Proxy: {s.get('proxy', '') or 'None'}", 
            BACK,
        ]

        console.clear()
        section_header("Settings")
        sel = questionary.select(
            "Select an option to change",
            style=QS,
            choices=choices,
            instruction="↑/↓ select · Enter confirm · Esc back"
        ).ask()
        if not sel or sel == BACK:
            return

        if sel.startswith("Default language"):
            v = questionary.text("Language (None/vostfr/vf):", style=QS, default=s.get("lang") or "None").ask()
            if v and v in ("None", "vostfr", "vf"):
                s["lang"] = None if v == "None" else v
        elif sel.startswith("Default player"):
            v = questionary.text("Player (Auto/mpv/vlc/iina/moonplayer/implay):", style=QS, default=s.get("player") or "Auto").ask()
            if v and v in ("Auto", "mpv", "vlc", "iina", "moonplayer", "implay"):
                s["player"] = None if v == "Auto" else v
        elif sel.startswith("Auto-update catalog"):
            s["auto_update"] = not s.get("auto_update", True)
        elif sel.startswith("Auto-fetch GitHub"):
            s["auto_fetch_github"] = not s.get("auto_fetch_github", True)
        elif sel.startswith("Auto-fetch new anime"):
            s["auto_fetch_new"] = not s.get("auto_fetch_new", True)
        elif sel.startswith("Download directory"):
            v = questionary.text("Download directory:", style=QS, default=s.get("download_dir", "downloads")).ask()
            if v:
                s["download_dir"] = v
        elif sel.startswith("Auto-play next episode"):
            s["auto_next"] = not s.get("auto_next", False)
        elif sel.startswith("Default download mode"):
            s["default_download"] = not s.get("default_download", False)
        elif sel.startswith("Max search results"):
            v = questionary.text("Max search results:", style=QS, default=str(s.get("max_results", 50))).ask()
            if v and v.isdigit():
                s["max_results"] = int(v)
        elif sel.startswith("Cache max hours"):
            v = questionary.text("Cache max hours:", style=QS, default=str(s.get("cache_hours", 24))).ask()
            if v and v.isdigit():
                s["cache_hours"] = int(v)
        elif sel.startswith("Preferred hosts"):
            v = questionary.text("Preferred hosts (comma separated):", style=QS, default=s.get("preferred_hosts", "")).ask()
            if v:
                s["preferred_hosts"] = v
        elif sel.startswith("Keep player open"):
            s["keep_open"] = not s.get("keep_open", True)
        elif sel.startswith("Prefer MP4"):
            s["prefer_mp4"] = not s.get("prefer_mp4", True)
        elif sel.startswith("Auto-convert downloads"):
            s["auto_convert_mp4"] = not s.get("auto_convert_mp4", True)
            if s.get("auto_convert_mp4", True):
                if not check_ffmpeg():
                    install_ffmpeg_interactive()
                explain_auto_convert()
        elif sel.startswith("Proxy"):
            v = questionary.text("Proxy (e.g. http://127.0.0.1:8080):", style=QS, default=s.get("proxy", "")).ask()
            if v is not None:
                s["proxy"] = v

        cache.save_settings(s)


def continue_menu(recent):
    if not recent:
        note("No history.")
        return
    total = len(recent)
    offset = 0
    while True:
        page = recent[offset:offset + PAGE_SIZE]
        choices = [f"E{r['episode']} - {r['title']}" for r in page]
        if offset + PAGE_SIZE < total:
            choices.append(NEXT)
        if offset > 0:
            choices.append(PREV)
        choices.append(BACK)

        header = f"Continue watching ({offset + 1}-{min(offset + PAGE_SIZE, total)}/{total})"
        sel = questionary.select(
            header,
            style=QS,
            choices=choices,
            instruction="↑/↓ select · Enter confirm · Esc back"
        ).ask()
        if not sel or sel == BACK:
            return
        if sel == NEXT:
            offset += PAGE_SIZE
            continue
        if sel == PREV:
            offset = max(0, offset - PAGE_SIZE)
            continue

        idx = offset + choices.index(sel)
        entry = recent[idx]
        anime = {"title": entry["title"], "link": entry["link"], "source": entry.get("source", "catalog"), "genres": []}
        show_anime_info(anime)
        c = questionary.confirm("Continue watching?", style=QS, default=True).ask()
        if c:
            settings = cache.load_settings()
            domain = scraper.find_active_domain()
            if not domain:
                err("Could not reach any Anime-Sama domain.")
                return
            catalog = ensure_catalog(domain, settings=settings)
            console.clear()
            show_banner()
            show_info(domain, catalog)
            anime_flow(
                anime,
                settings.get("lang"),
                settings.get("default_download", False),
                None,
                settings.get("player"),
                False,
                settings.get("download_dir", "downloads"),
                settings,
                start_season_url=entry.get("season_url"),
                start_episode_num=entry.get("episode"),
            )


def main():
    try:
        cli()
    except KeyboardInterrupt:
        console.print(f"\n[{ST['dim']}]Interrupted.[/{ST['dim']}]")
        sys.exit(0)


if __name__ == "__main__":
    main()
