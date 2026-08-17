"""Main workflow: search → pick → resolve → play/download."""

import os
import re
import threading
import time
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
import questionary
from rich.progress import Progress, SpinnerColumn, TextColumn

from anisama import __version__, cache, search, resolver
from anisama.config import RESOLVER_HEADERS
from anisama.scraper import find_active_domain
from anisama.scraper.anime_sama import get_anime_seasons, get_episodes
from anisama.scraper.voiranime import voiranime_get_seasons, voiranime_get_episodes

from . import api_client
from .display import console, ST, QS, score_badge, note, ok, err, section_header, show_banner, show_anime_info, show_info
from . import player as player_mod
from .picker import parse_range, filter_seasons, with_spinner, pick_anime, pick_season, pick_ep, pick_lang, pick_player, BACK, PAGE_SIZE, NEXT, PREV
from .mirror import pick_fastest_mirror, resolve_best_mirror, resolve_all_mirrors, pick_mirror, test_url_speed, format_speed, convert_m3u8_to_mp4, sanitize
from .install import check_ffmpeg, install_ffmpeg_interactive


def ensure_catalog(domain, force=False, settings=None, api_base=None):
    if api_base:
        return []

    if not settings:
        settings = cache.load_settings()

    if force:
        cat = _fetch_github_catalog_if_enabled(settings)
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as p:
            p.add_task("Updating catalog with new entries...", total=None)
            cat = cache.download_combined_catalog(domain)
        ok(f"Catalog updated: {len(cat)} anime")
        return cat

    if not cache.is_cache_valid() or not cache.CATALOG_FILE.exists():
        cat = _fetch_github_catalog_if_enabled(settings)
        if cat:
            ok(f"Catalog downloaded from GitHub: {len(cat)} anime")
        else:
            note("Could not fetch GitHub catalog, using local catalog.")

    return cache.load_combined_catalog(domain)


def _slug(link):
    return link.rstrip("/").split("/")[-1] if link else ""


def anime_flow(anime, lang, download, episodes, pref, quiet, dl_dir, settings,
               start_season_url=None, start_episode_num=None):
    auto_next = settings.get("auto_next", False)
    player_path = None
    source = anime.get("source", "catalog")
    url = anime["link"]
    slug = _slug(url)

    if not quiet:
        ok(f"Selected: {anime['title']}")

    if source == "voiranime":
        voiranime_flow(anime, lang, download, episodes, pref, quiet, dl_dir, settings.get("keep_open", True), auto_next)
        return

    while True:
        all_s = with_spinner("Fetching seasons...", get_anime_seasons, url)
        seasons = filter_seasons(all_s)

        if lang:
            f = [s for s in seasons if f"/{lang}/" in s["url"] or s["url"].endswith(f"/{lang}")]
            if f:
                seasons = f
            elif not quiet:
                note(f"No '{lang}' seasons, showing all.")

        if start_season_url and not episodes and start_episode_num is None:
            season = next((s for s in seasons if s["url"] == start_season_url), None)
            if season is None:
                season = pick_season(seasons)
            start_season_url = None
        else:
            season = pick_season(seasons)
        if season is None:
            break

        s_url = season["url"]
        s_name = season.get("name", "")
        eps = with_spinner("Fetching episodes...", get_episodes, s_url)
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
                return

        episodes = None
        continue


def workflow(query, lang, download, episodes, pref, quiet, domain, catalog, from_menu=False, api_base=None):
    if not quiet:
        if not from_menu:
            show_banner()
        show_info(domain, catalog, api_base=api_base)

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
        all_s = with_spinner("Fetching seasons...", voiranime_get_seasons, url)
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
            eps = with_spinner("Fetching episodes...", voiranime_get_episodes, s_url, chosen_lang)
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
                    return

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


def _report_local_resolution(source, slug, n, r):
    """Tell the API we resolved locally, so it can serve this instantly next time."""
    try:
        api_client.submit_resolution(
            source, slug, n,
            r.get("url", ""), r.get("type", "raw"), r.get("referer", ""),
        )
    except Exception:
        pass


def _resolve_episode(e, n, quiet, prefer_mp4=True, allow_pick=False, source="anime-sama", slug=""):
    if not quiet:
        console.print(f"\n[{ST['sel']}]Episode {n}:[/{ST['sel']}] Resolving video URL...")

    box = {"winner": None}
    lock = threading.Lock()
    done = threading.Event()

    def _win(tag, r):
        with lock:
            if box["winner"] is None:
                box["winner"] = (tag, r)
                done.set()

    def _api_worker():
        try:
            url, rtype, ref = api_client.resolve_episode(source, slug, n)
            if url:
                _win("api", {"url": url, "type": rtype, "referer": ref})
        except Exception:
            pass

    def _local_worker():
        try:
            r = resolve_best_mirror(e, prefer_mp4=prefer_mp4)
            if r:
                _win("local", r)
        except Exception:
            pass

    workers = [threading.Thread(target=_api_worker, daemon=True)]
    if e and e.get("mirrors"):
        workers.append(threading.Thread(target=_local_worker, daemon=True))
    for w in workers:
        w.start()

    done.wait(timeout=25)
    winner = box["winner"]

    if winner:
        tag, r = winner
        if tag == "local":
            _report_local_resolution(source, slug, n, r)
            if not quiet:
                ok(f"Resolved locally: {r.get('type','raw').upper()} from {urlparse(r['url']).netloc}")
        elif not quiet:
            ok(f"Resolved via API: {r.get('type','raw').upper()} from {urlparse(r['url']).netloc}")
        return r

    local_r = pick_fastest_mirror(e, prefer_mp4=prefer_mp4, test_speed=True, quiet=quiet)
    if local_r:
        _report_local_resolution(source, slug, n, local_r)
        if not quiet:
            ok(f"Best source: {local_r.get('type','raw').upper()} from {urlparse(local_r['url']).netloc}")
        return local_r

    err(f"Failed to resolve episode {n}.")
    return None


def download_eps(eps, nums, title, quiet, dl_dir="downloads", anime_link="", season_url=None, season_name=None):
    settings = cache.load_settings()
    prefer_mp4 = settings.get("prefer_mp4", True)
    auto_convert = settings.get("auto_convert_mp4", True)
    slug = _slug(anime_link)
    d = Path.cwd() / dl_dir / sanitize(title)
    for n in nums:
        e = eps[n - 1]
        r = _resolve_episode(e, n, quiet, prefer_mp4=prefer_mp4, allow_pick=True, source="anime-sama", slug=slug)
        if not r:
            continue

        ext = "mp4"
        fname = f"E{n:02d}.{ext}"
        out = d / fname

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
    slug = anime_link.rstrip("/").split("/")[-1] if anime_link else ""
    for n in nums:
        e = eps[n - 1]
        r = _resolve_episode(e, n, quiet, prefer_mp4=prefer_mp4, allow_pick=True, source="anime-sama", slug=slug)
        if not r:
            continue
        if not quiet:
            ok(f"Playing episode {n} ({r.get('type', 'raw')})...")
        player_mod.play_url(r["url"], player_path, r.get("referer"), keep_open)
        cache.add_history(anime_title, anime_link, "anime-sama", n, season_url=season_url, season_name=season_name)


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
            domain = find_active_domain()
            if not domain:
                err("Could not reach any Anime-Sama domain.")
                return
            catalog = ensure_catalog(domain, settings=settings, api_base=api_client.API_BASE)
            _background_update(domain, settings)
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


def _fetch_github_catalog_if_enabled(settings):
    if settings.get("auto_fetch_github", True):
        return with_spinner("Downloading catalog from GitHub...", cache.fetch_github_catalog)
    return None


def _background_update(domain, settings):
    if not settings.get("auto_fetch_new", True):
        return

    def _run():
        try:
            cache.download_combined_catalog(domain)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


def _dedup_results(results, max_res=100, query=None):
    seen = {}
    out = []
    q_tokens = set(search.clean(query).split()) if query else set()
    for r in results:
        t = search.clean(r.get("title", ""))
        score = r.get("score", 0)
        if q_tokens and score < 90:
            t_tokens = set(t.split())
            if not q_tokens & t_tokens:
                continue
        key = search._base_key(r.get("title", ""))
        if not key:
            continue
        if key in seen:
            idx = seen[key]
            if score > out[idx].get("score", 0):
                out[idx] = r
        else:
            seen[key] = len(out)
            out.append(r)
    out.sort(key=lambda x: (-x.get("score", 0), x.get("title", "")))
    return out[:max_res] if max_res else out


def search_all(query, catalog, domain, max_res=100, quiet=False):
    try:
        results = api_client.search(query)
        if results:
            if not quiet:
                ok(f"Found {len(results)} results via API")
            return _dedup_results(results, max_res, query)
    except Exception:
        pass

    results = search.search_combined(query, catalog, domain=domain, limit=max_res)
    if results:
        return results
    if not quiet:
        note("Not in catalog, searching Voiranime live...")
    vr = search.search_voiranime(query)
    if vr:
        return _dedup_results(vr, max_res, query)
    return []
