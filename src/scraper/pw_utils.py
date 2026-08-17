"""Shared Playwright/Chromium launch helpers with hardening flags."""

import os

from ..config import PLAYWRIGHT_EXECUTABLE_PATH

_PW_ARGS = [
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-accelerated-2d-canvas",
    "--js-flags=--max-old-space-size=512",
]


def chromium_launch_args():
    """Chromium hardening args. Sandbox is disabled only when running as
    root (Docker/Pterodactyl), where Chromium refuses to launch otherwise."""
    args = list(_PW_ARGS)
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        args.append("--no-sandbox")
        args.append("--disable-setuid-sandbox")
    return args


def launch_browser(pw):
    """Launch a headless hardened Chromium browser via a sync playwright."""
    kwargs = {"headless": True, "args": chromium_launch_args()}
    if PLAYWRIGHT_EXECUTABLE_PATH:
        kwargs["executable_path"] = PLAYWRIGHT_EXECUTABLE_PATH
    return pw.chromium.launch(**kwargs)