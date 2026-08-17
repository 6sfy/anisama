"""Click CLI entry point for anisama."""

import os
import sys

import click
import questionary

from anisama import __version__, __app_name__
from anisama import cache
from anisama.scraper import find_active_domain
from . import api_client
from .display import console, ST, QS, show_banner, err, note
from .workflow import continue_menu, ensure_catalog, _background_update, workflow
from .settings import settings_menu


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

    no_cli = not any([cli_download, episodes, update, quiet, dub, cli_lang])

    if not query and no_cli:
        first_run = True
        while True:
            if not first_run:
                console.clear()
            first_run = False
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

    domain = find_active_domain()
    if not domain:
        err("Could not reach any Anime-Sama domain.")
        sys.exit(1)

    catalog = ensure_catalog(domain, force=update, settings=settings, api_base=api_client.API_BASE)
    _background_update(domain, settings)
    workflow(query, lang, download, episodes, player, quiet, domain, catalog, from_menu=no_cli, api_base=api_client.API_BASE)


def main():
    try:
        cli()
    except KeyboardInterrupt:
        console.print(f"\n[{ST['dim']}]Interrupted.[/{ST['dim']}]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)
