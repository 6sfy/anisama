import platform
import shutil
import subprocess

from rich.progress import Progress, SpinnerColumn, TextColumn

from ..core import cache
from .display import console, ST, note, ok, err, section_header

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


