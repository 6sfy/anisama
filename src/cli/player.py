"""Player detection, play, and download functions."""

import os
import platform
import shutil
import subprocess
from pathlib import Path

from .config import PLAYER_PATHS

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _fetch_headers(referer=None):
    headers = {"User-Agent": BROWSER_UA}
    if referer:
        headers["Referer"] = referer
    return headers


def stream_is_alive(url, rtype="mp4", referer=None, timeout=8):
    """Lightweight liveness check before handing a URL to a player."""
    import httpx

    headers = _fetch_headers(referer)
    try:
        if rtype == "m3u8":
            r = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
            if r.status_code != 200:
                return False
            body = r.content[:1024].lower()
            ctype = r.headers.get("content-type", "").lower()
            return b"#extm3u" in body or "mpegurl" in ctype
        r = httpx.head(url, headers=headers, timeout=timeout, follow_redirects=True)
        if r.status_code in (200, 206):
            return True
        if r.status_code == 405:
            r = httpx.get(url, headers={**headers, "Range": "bytes=0-0"}, timeout=timeout, follow_redirects=True)
            return r.status_code in (200, 206, 416)
        return False
    except Exception:
        return False


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
                cmd += [f"--http-header-fields=Referer: {referer}", f"--http-header-fields=User-Agent: {BROWSER_UA}"]
            cmd.append(url)
            subprocess.Popen(cmd, shell=False)
        elif sys_name == "Darwin":
            subprocess.Popen(["open", "-a", path, url])
        else:
            subprocess.Popen([path, url])
    except Exception as e:
        from rich.console import Console
        Console().print(f"[red]Error launching player:[/red] {e}")


def download_url(url, out_dir, fname, use_ytdlp=True, referer=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / fname

    if use_ytdlp:
        yt = shutil.which("yt-dlp")
        if yt:
            args = [yt, "-o", str(out), "--no-playlist", "--no-progress", "--add-header", f"User-Agent: {BROWSER_UA}"]
            if referer:
                args += ["--add-header", f"Referer: {referer}"]
            args.append(url)
            subprocess.run(args, check=False)
            if out.exists():
                return out

    import requests
    from rich.console import Console

    c = Console()
    r = requests.get(url, stream=True, timeout=30, headers=_fetch_headers(referer))
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
