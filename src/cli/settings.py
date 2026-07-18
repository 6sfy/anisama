import questionary

from ..core import cache
from .display import console, ST, QS, section_header, ok, note, err
from .install import check_ffmpeg, install_ffmpeg_interactive, explain_auto_convert
from .picker import BACK

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


