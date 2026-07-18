import questionary
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..core import cache as cache_mod, scraper
from .display import console, ST, QS, score_badge, err, note, show_anime_info, section_header
from . import player as player_mod

PAGE_SIZE = 10
NEXT = ">  Next page"
PREV = "<  Previous page"
BACK = "<  Back"

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



def filter_seasons(s):
    return [x for x in s if "scan" not in x["name"].lower()]



def with_spinner(desc, fn, *args, **kwargs):
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  console=console, transient=True) as p:
        p.add_task(desc, total=None)
        return fn(*args, **kwargs)



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
            sc = int(round(r["score"]))
            choices.append(f"{r['title']}  [{sc}%]")
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


