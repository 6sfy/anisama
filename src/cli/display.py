"""Rich console, banners, panels, and display helpers."""

from questionary import Style as QStyle
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

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
        subtitle=f"[{ST['accent']}]Anime-Sama CLI[/{ST['accent']}]",
        border_style="blue", padding=(0, 1)
    )
    console.print(panel)


def show_anime_info(anime):
    g = anime.get("genres", [])
    src = anime.get("alt_source", anime.get("source", ""))
    lines = []
    info_ok = False

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
                    raw = a["description"].replace("<br>", " ").replace("<i>", "").replace("</i>", "")
                    desc = raw[:297] + "..." if len(raw) > 300 else raw
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
                        raw = a["synopsis"]
                        syn = raw[:297] + "..." if len(raw) > 300 else raw
                        lines.append("")
                        lines.append(f"[{ST['dim']}]{syn}[/{ST['dim']}]")
                        info_ok = True
        except Exception:
            pass

    if not info_ok and not g:
        lines.append(f"[{ST['dim']}]No info available[/{ST['dim']}]")

    meta = []
    if isinstance(src, list) and src:
        meta.append(f"[{ST['dim']}]Also on:[/{ST['dim']}] [{ST['sel']}]{', '.join(src)}[/{ST['sel']}]")
    if g:
        meta.append(f"[{ST['dim']}]Genres:[/{ST['dim']}] {', '.join(g[:6])}")
    if meta:
        lines.insert(0, "  .  ".join(meta))

    console.print(Panel("\n".join(lines), title=f"[{ST['title']}]{anime['title']}[/{ST['title']}]",
                        border_style="cyan", padding=(1, 2)))


def show_info(domain, catalog, api_base=None):
    from .api_client import fetch_catalog_count
    console.print()
    if api_base:
        status_line("API", api_base, ST['sel'])
        n = fetch_catalog_count(api_base) or len(catalog)
        status_line("Catalog", f"{n} anime", ST['sel'])
    else:
        status_line("Domain", domain, ST['sel'])
        status_line("Catalog", f"{len(catalog)} anime", ST['sel'])
    console.print()
