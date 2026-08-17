"""Player detection, play, and download functions."""

import os
import platform
import shutil
import subprocess
from pathlib import Path

from .config import PLAYER_PATHS


def find_player(name):
    sys_name = platform.system()
    exe = name
    if sys_name == "Windows" and not exe.endswith(".exe"):
        exe = f"{name}.exe"

    f = shutil.which(exe)
    if f:
        return f

    for p in PLAYER_PATHS.get(sys_name, {}).get(name, []):
        if "\\" in p or "/" in p:
            if Path(p).exists():
                return p

    return None


def detect_player(pref=None):
    if pref:
        cmd = find_player(pref)
        return cmd if cmd else None

    for p in ["mpv", "vlc", "iina", "moonplayer", "implay"]:
        cmd = find_player(p)
        if cmd:
            return cmd

    return None


def detect_players():
    r = {}
    for p in ["mpv", "vlc", "iina", "moonplayer", "implay"]:
        cmd = find_player(p)
        if cmd:
            r[p] = cmd
    return r


def play_url(url, path, referer=None, keep_open=True):
    sys_name = platform.system()
    try:
        if sys_name == "Windows":
            cmd = [path]
            base = os.path.basename(path).lower()
            if "mpv" in base:
                flags = ["--vo=gpu", "--gpu-context=d3d11", "--hwdec=no", "--d3d11-flip=no", "--d3d11-output-format=auto"]
                if keep_open:
                    flags.insert(0, "--keep-open")
                cmd += flags
            elif "implay" in base:
                if keep_open:
                    cmd += ["--keep-open"]
            if referer and ("mpv" in base or "implay" in base):
                cmd += [f"--http-header-fields=Referer: {referer}"]
            cmd.append(url)
            subprocess.Popen(cmd, shell=False)
        elif sys_name == "Darwin":
            subprocess.Popen(["open", "-a", path, url])
        else:
            subprocess.Popen([path, url])
    except Exception as e:
        from rich.console import Console
        Console().print(f"[red]Error launching player:[/red] {e}")


def download_url(url, out_dir, fname, use_ytdlp=True):
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / fname

    if use_ytdlp:
        yt = shutil.which("yt-dlp")
        if yt:
            subprocess.run(
                [yt, "-o", str(out), "--no-playlist", "--no-progress", url],
                check=False,
            )
            if out.exists():
                return out

    import requests
    from rich.console import Console

    c = Console()
    r = requests.get(url, stream=True, timeout=30)
    r.raise_for_status()
    total = int(r.headers.get("content-length", 0))
    with open(out, "wb") as f:
        if total:
            with c.status(f"Downloading {fname}...", spinner="dots"):
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        else:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    return out
