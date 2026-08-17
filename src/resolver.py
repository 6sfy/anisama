"""Video URL resolution for various hosting providers.

Each resolver takes an embed URL and returns ``{"url": ..., "type": ...}``
where type is one of "m3u8", "mp4", "embed", or "raw".
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .config import REQUEST_TIMEOUT, RESOLVER_HEADERS, VOIRANIME_HEADERS
from .http_client import get_client


# ── Generic video URL extraction ──

def _extract_video_url(text: str, base_url: str = "") -> dict[str, str] | None:
    """Try to extract a direct video URL from page source text."""
    # try m3u8 first, then mp4/webm
    patterns = [
        # JS/JSON common patterns
        (r'(?:var|let|const)\s+(?:video[_-]?url|source[_-]?url|file|src|url|video)\s*=\s*["\']([^"\']+)["\']', None),
        (r'(?:video[_-]?url|file|src|url)\s*:\s*["\'](https?://[^"\']+)["\']', None),
        (r'"(?:file|src|url|video|source)"\s*:\s*"([^"]+)"', None),
        (r"'(?:file|src|url|video|source)'\s*:\s*'([^']+)'", None),
        (r'sources\s*:\s*\[\s*\{[^}]*(?:file|src)\s*:\s*["\']([^"\']+)["\']', None),
        # HTML5 video/source tags
        (r'<(?:video|source)[^>]+src=["\']([^"\']+)["\']', None),
        # Direct file URLs
        (r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', "m3u8"),
        (r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']', "mp4"),
        (r'["\'](https?://[^"\']+\.webm[^"\']*)["\']', "webm"),
        (r'["\'](https?://[^"\']+/hls/[^"\']*)["\']', "m3u8"),
        (r'["\'](https?://[^"\']+/playlist[^"\']*)["\']', "m3u8"),
        # Generic fallback for any http(s) URL that looks like video
        (r'["\'](https?://[^"\']+\.(?:m3u8|mp4|webm|mkv|mov)[^"\']*)["\']', None),
    ]

    found: list[str] = []
    for pat, forced_type in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            u = m.group(1)
            if not u or u in found:
                continue
            found.append(u)
            if u.startswith("//"):
                u = "https:" + u
            elif u.startswith("/") and base_url:
                u = urljoin(base_url, u)
            elif not u.startswith("http"):
                continue

            path = urlparse(u).path.split("?")[0].lower()
            ext = path.split(".")[-1] if "." in path else ""

            if forced_type:
                return {"url": u, "type": forced_type}
            if ext in ("m3u8",):
                return {"url": u, "type": "m3u8"}
            if ext in ("mp4", "webm", "mkv", "mov"):
                return {"url": u, "type": ext if ext != "mov" else "mp4"}
            if "/hls" in u.lower() or "/playlist" in u.lower() or ".m3u8" in u.lower():
                return {"url": u, "type": "m3u8"}
            # If it has a video-like domain or path, assume mp4
            if any(x in u.lower() for x in ["/video/", "/videos/", "cdn", "stream", "media"]):
                return {"url": u, "type": "mp4"}
    return None


def _resolve_embed_page(url: str, depth: int = 0) -> dict[str, str] | None:
    """Recursively resolve an embed page to find a direct video URL."""
    if depth > 2:
        return None
    c = get_client()
    try:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        r = c.get(url, headers={**RESOLVER_HEADERS, "Referer": base + "/"}, follow_redirects=True)
        if r.status_code != 200:
            return None

        # Direct video found
        direct = _extract_video_url(r.text, base)
        if direct:
            return direct

        # Follow iframe recursively
        iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', r.text, re.IGNORECASE)
        for src in iframes:
            if not src:
                continue
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = urljoin(base, src)
            elif not src.startswith("http"):
                continue
            resolved = _resolve_embed_page(src, depth + 1)
            if resolved:
                return resolved
    except Exception:
        pass
    return None


# ── Packed JS decoder (for smoothpre/vidhide/streamwish) ──

def _to_base_n(num: int, base: int) -> str:
    """Convert a number to a base-N string representation."""
    if num == 0:
        return '0'
    chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    res = ""
    while num > 0:
        res = chars[num % base] + res
        num //= base
    return res


def _decode_pack(p: str, a: int, c: int, k_str: str) -> str:
    """Decode a packed JS string (Dean Edwards packer)."""
    k_list = k_str.split("|")
    for i in range(c - 1, -1, -1):
        if i < len(k_list) and k_list[i]:
            alias = _to_base_n(i, a)
            p = re.sub(r"\b" + re.escape(alias) + r"\b", k_list[i], p)
    return p


# ── Individual host resolvers ──

def resolve_vidmoly(url: str) -> dict[str, str] | None:
    """Resolve a Vidmoly embed URL."""
    url_net = url.replace("vidmoly.to", "vidmoly.net")
    c = get_client()
    try:
        r = c.get(
            url_net,
            headers={**RESOLVER_HEADERS, "Referer": url_net},
        )
        redirect = re.search(r"window\.location\.replace\('([^']+)'\)", r.text)
        if redirect:
            r = c.get(
                redirect.group(1),
                headers={**RESOLVER_HEADERS, "Referer": url_net},
            )
        match = re.search(
            r'file\s*:\s*["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text
        )
        if match:
            return {"url": match.group(1), "type": "m3u8"}
    except Exception:
        pass
    return None


def resolve_smoothpre(url: str) -> dict[str, str] | None:
    """Resolve a SmoothPre/VidHide/StreamWish embed URL."""
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    c = get_client()
    try:
        r = c.get(url, headers={**RESOLVER_HEADERS, "Referer": f"{base_url}/"})
        eval_match = re.search(
            r"eval\(function\(p,a,c,k,e,d\)\{.*?\}\('(.*?)',(\d+),(\d+),'(.*?)'\.split\('\|'\)\)\)",
            r.text,
            re.DOTALL,
        )
        if eval_match:
            decoded = _decode_pack(
                eval_match.group(1),
                int(eval_match.group(2)),
                int(eval_match.group(3)),
                eval_match.group(4),
            )
            for key in ["hls4", "hls3", "hls2", "hls"]:
                m = re.search(f'"{key}"\\s*:\\s*"(.*?)"', decoded)
                if m:
                    target_url = m.group(1).replace("\\", "")
                    if target_url.startswith("/"):
                        target_url = base_url + target_url
                    return {"url": target_url, "type": "m3u8"}
    except Exception:
        pass
    return None


def resolve_sendvid(url: str) -> dict[str, str] | None:
    """Resolve a SendVid embed URL."""
    c = get_client()
    try:
        r = c.get(
            url,
            headers={**RESOLVER_HEADERS, "Referer": "https://sendvid.com/"},
        )
        match = re.search(r'<source\s+src="([^"]+\.mp4[^"]*)"', r.text)
        if not match:
            match = re.search(r'property="og:video"\s+content="([^"]+)"', r.text)
        if not match:
            match = re.search(
                r'property="og:video:url"\s+content="([^"]+)"', r.text
            )
        if match:
            video_url = match.group(1)
            if video_url.startswith("//"):
                video_url = "https:" + video_url
            return {"url": video_url, "type": "mp4"}
    except Exception:
        pass
    return None


def resolve_oneupload(url: str) -> dict[str, str] | None:
    """Resolve a OneUpload embed URL."""
    c = get_client()
    try:
        r = c.get(url, headers={**RESOLVER_HEADERS, "Referer": url})
        match = re.search(
            r'file\s*:\s*["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', r.text
        )
        if match:
            return {"url": match.group(1), "type": "m3u8"}
        match = re.search(r'<source\s+src="([^"]+)"', r.text)
        if match:
            return {"url": match.group(1), "type": "mp4"}
    except Exception:
        pass
    return None


def resolve_sibnet(url: str) -> dict[str, str] | None:
    """Resolve a Sibnet embed URL."""
    c = get_client()
    try:
        r = c.get(url, headers={**RESOLVER_HEADERS, "Referer": url})
        # Try generic extraction first
        direct = _extract_video_url(r.text, url)
        if direct and direct.get("type") != "raw":
            return direct

        iframe = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', r.text, re.IGNORECASE)
        if iframe:
            iframe_url = iframe.group(1)
            if iframe_url.startswith("//"):
                iframe_url = "https:" + iframe_url
            elif iframe_url.startswith("/"):
                iframe_url = urljoin(url, iframe_url)
            inner = c.get(
                iframe_url,
                headers={**RESOLVER_HEADERS, "Referer": url},
            )
            direct = _extract_video_url(inner.text, iframe_url)
            if direct and direct.get("type") != "raw":
                return direct
    except Exception:
        pass
    return None


def resolve_minochinos(url: str) -> dict[str, str] | None:
    """Resolve a Minochinos embed URL."""
    return _resolve_embed_page(url)


def resolve_embed4me(url: str) -> dict[str, str] | None:
    """Resolve an embed4me embed URL."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    c = get_client()
    try:
        r = c.get(url, headers={**RESOLVER_HEADERS, "Referer": base + "/"}, follow_redirects=True)
        if r.status_code == 200:
            # embed4me sometimes stores the real video URL in a hash fragment after #
            frag = parsed.fragment
            if frag and (frag.startswith("http") or "://" in frag):
                decoded = frag
                if decoded.startswith("//"):
                    decoded = "https:" + decoded
                ext = urlparse(decoded).path.split("?")[0].split(".")[-1].lower()
                t = "m3u8" if ext == "m3u8" else "mp4"
                return {"url": decoded, "type": t}
            # Try generic extraction
            direct = _extract_video_url(r.text, base)
            if direct:
                return direct
    except Exception:
        pass
    return _resolve_embed_page(url)


# ── yt-dlp fallback ──

def resolve_with_ytdlp(url: str) -> dict[str, str] | None:
    """Use yt-dlp to extract a direct video URL from an embed page."""
    yt = shutil.which("yt-dlp")
    if not yt:
        return None
    try:
        result = subprocess.run(
            [yt, "--no-playlist", "--get-url", "--format", "best", url],
            capture_output=True, text=True, timeout=30, check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            video_url = result.stdout.strip().splitlines()[0]
            ext = urlparse(video_url).path.split("?")[0].split(".")[-1].lower()
            t = "m3u8" if ext == "m3u8" else "mp4"
            return {"url": video_url, "type": t}
    except Exception:
        pass

    try:
        result = subprocess.run(
            [yt, "--no-playlist", "--dump-json", "--format", "best", url],
            capture_output=True, text=True, timeout=30, check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip().splitlines()[0])
            video_url = data.get("url") or data.get("manifest_url")
            if not video_url and data.get("formats"):
                video_url = data["formats"][-1].get("url")
            if video_url:
                ext = urlparse(video_url).path.split("?")[0].split(".")[-1].lower()
                t = "m3u8" if ext == "m3u8" else "mp4"
                return {"url": video_url, "type": t}
    except Exception:
        pass
    return None


def resolve_generic(url: str) -> dict[str, str] | None:
    """Try yt-dlp first, then generic embed page resolution."""
    ytdlp_result = resolve_with_ytdlp(url)
    if ytdlp_result:
        return ytdlp_result
    return _resolve_embed_page(url)


# ── Voiranime episode resolver ──

def resolve_voiranime_episode(episode_url: str, lang: str) -> dict[str, str] | None:
    """Resolve a Voiranime episode URL for a given language."""
    c = get_client()
    try:
        r = c.get(episode_url, headers={**VOIRANIME_HEADERS, "Referer": episode_url})
        if r.status_code != 200:
            return None
        m = re.search(r"const\s+videoUrls\s*=\s*({.*?});", r.text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                url = data.get(lang)
                if url:
                    return {"url": url, "type": "mp4"}
            except Exception:
                pass
        soup = BeautifulSoup(r.text, "html.parser")
        iframe = soup.find("iframe", id="videoPlayer")
        if iframe:
            src = iframe.get("src")
            if src:
                return {"url": src, "type": "raw"}
    except Exception:
        pass
    return None


# ── Resolver dispatch ──

RESOLVER_MAP: dict[str, Any] = {
    "vidmoly.to": resolve_vidmoly,
    "vidmoly.net": resolve_vidmoly,
    "smoothpre.com": resolve_smoothpre,
    "vidhide.com": resolve_smoothpre,
    "streamwish.com": resolve_smoothpre,
    "sendvid.com": resolve_sendvid,
    "oneupload.to": resolve_oneupload,
    "video.sibnet.ru": resolve_sibnet,
    "minochinos.com": resolve_minochinos,
    "embed4me.com": resolve_embed4me,
    "lpayer.embed4me.com": resolve_embed4me,
}


def resolve_url(url: str) -> dict[str, str]:
    """Resolve an embed URL to a direct video URL.

    Uses the appropriate resolver based on the domain, falling back
    to yt-dlp and then generic embed page resolution.
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace("www.", "")
    resolver = RESOLVER_MAP.get(domain)
    if resolver:
        result = resolver(url)
        if result:
            return result
    # Try generic embed resolver before giving up
    generic = resolve_generic(url)
    if generic:
        return generic
    return {"url": url, "type": "raw"}
