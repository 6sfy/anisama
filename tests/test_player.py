"""Tests for stream liveness checks and dead-URL rejection in resolution."""

import time
from unittest.mock import patch

from anisama.cli import mirror as mirror_mod
from anisama.cli import player as player_mod
from anisama.cli import workflow as wf


class FakeResp:
    status_code = 200
    content = b""
    headers = {}

    def __init__(self, status=200, content=b"", headers=None):
        self.status_code = status
        self.content = content
        self.headers = headers or {}


def test_stream_is_alive_m3u8_ok():
    resp = FakeResp(content=b"#EXTM3U\n#EXT-X-VERSION:3\n", headers={"content-type": "application/vnd.apple.mpegurl"})
    with patch("httpx.get", return_value=resp):
        assert player_mod.stream_is_alive("https://x/master.m3u8", "m3u8") is True


def test_stream_is_alive_m3u8_error_page():
    resp = FakeResp(content=b"<html>Forbidden</html>", headers={"content-type": "text/html"})
    with patch("httpx.get", return_value=resp):
        assert player_mod.stream_is_alive("https://x/master.m3u8", "m3u8") is False


def test_stream_is_alive_m3u8_http_error():
    resp = FakeResp(status=403)
    with patch("httpx.get", return_value=resp):
        assert player_mod.stream_is_alive("https://x/master.m3u8", "m3u8") is False


def test_stream_is_alive_m3u8_timeout():
    def boom(*a, **k):
        raise TimeoutError("timeout")

    with patch("httpx.get", side_effect=boom):
        assert player_mod.stream_is_alive("https://x/master.m3u8", "m3u8") is False


def test_stream_is_alive_m3u8_segment_ok():
    playlist = FakeResp(content=b"#EXTM3U\n#EXTINF:20,\nseg-1.ts?t=1\n")
    segment = FakeResp(status=206, headers={"content-type": "video/mp2t"})
    with patch("httpx.get", side_effect=[playlist, segment]):
        assert player_mod.stream_is_alive("https://x/master.m3u8", "m3u8") is True


def test_stream_is_alive_m3u8_segment_forbidden():
    playlist = FakeResp(content=b"#EXTM3U\n#EXTINF:20,\nseg-1.ts?t=1\n")
    segment = FakeResp(status=403, headers={"content-type": "text/html"})
    with patch("httpx.get", side_effect=[playlist, segment]):
        assert player_mod.stream_is_alive("https://x/master.m3u8", "m3u8") is False


def test_stream_is_alive_m3u8_master_variant_segment():
    master = FakeResp(content=b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1\nv/index.m3u8?t=1\n")
    variant = FakeResp(content=b"#EXTM3U\n#EXTINF:20,\nseg-1.ts?t=1\n")
    segment = FakeResp(status=206)
    with patch("httpx.get", side_effect=[master, variant, segment]):
        assert player_mod.stream_is_alive("https://x/master.m3u8", "m3u8") is True


def test_stream_is_alive_mp4_range_ok():
    with patch("httpx.get", return_value=FakeResp(headers={"content-type": "video/mp4"})):
        assert player_mod.stream_is_alive("https://x/v.mp4", "mp4") is True


def test_stream_is_alive_mp4_html_rejected():
    with patch("httpx.get", return_value=FakeResp(headers={"content-type": "text/html; charset=utf-8"})):
        assert player_mod.stream_is_alive("https://x/page.php", "mp4") is False


def test_stream_is_alive_mp4_no_content_type():
    with patch("httpx.get", return_value=FakeResp()):
        assert player_mod.stream_is_alive("https://x/v.mp4", "mp4") is True


def test_stream_is_alive_mp4_404():
    with patch("httpx.get", return_value=FakeResp(status=404)):
        assert player_mod.stream_is_alive("https://x/gone.mp4", "mp4") is False


def test_resolve_best_mirror_returns_first_alive_in_preference_order(monkeypatch):
    monkeypatch.setattr(mirror_mod, "resolve_all_mirrors", lambda ep: [
        {"url": "https://a/master.m3u8", "type": "m3u8", "referer": ""},
        {"url": "https://b/master.m3u8", "type": "m3u8", "referer": ""},
        {"url": "https://c/v.mp4", "type": "mp4", "referer": ""},
    ])
    alive = {"https://a/master.m3u8": False, "https://b/master.m3u8": True, "https://c/v.mp4": True}
    monkeypatch.setattr(mirror_mod, "_stream_is_alive", lambda url, rtype="mp4", referer=None, timeout=8: alive.get(url, False))

    r = mirror_mod.resolve_best_mirror({"mirrors": {"eps1": "x"}})
    assert r["url"] == "https://c/v.mp4"


def test_resolve_best_mirror_all_dead_returns_none(monkeypatch):
    monkeypatch.setattr(mirror_mod, "resolve_all_mirrors", lambda ep: [
        {"url": "https://a/master.m3u8", "type": "m3u8", "referer": ""},
        {"url": "https://b/master.m3u8", "type": "m3u8", "referer": ""},
    ])
    monkeypatch.setattr(mirror_mod, "_stream_is_alive", lambda *a, **k: False)

    assert mirror_mod.resolve_best_mirror({"mirrors": {"eps1": "x"}}) is None


def test_resolve_best_mirror_single_candidate_dead(monkeypatch):
    monkeypatch.setattr(mirror_mod, "resolve_all_mirrors", lambda ep: [
        {"url": "https://d/master.m3u8", "type": "m3u8", "referer": ""},
    ])
    monkeypatch.setattr(mirror_mod, "_stream_is_alive", lambda *a, **k: False)

    assert mirror_mod.resolve_best_mirror({"mirrors": {"eps1": "x"}}) is None


def _no_local(monkeypatch):
    monkeypatch.setattr(wf, "_resolve_first_playable", lambda *a, **k: None)
    monkeypatch.setattr(wf, "pick_fastest_mirror", lambda *a, **k: None)
    monkeypatch.setattr(wf, "_report_local_resolution", lambda *a, **k: None)


def test_api_dead_url_rejected_local_wins(monkeypatch):
    """A dead URL from the API must never win the race."""
    alive_seen = []

    def fake_alive(url, rtype="mp4", referer=None, timeout=8):
        alive_seen.append(url)
        return False

    def slow_local(*a, **k):
        time.sleep(0.3)
        return {"url": "https://ok/master.m3u8", "type": "m3u8", "referer": ""}

    monkeypatch.setattr("anisama.cli.api_client.resolve_episode", lambda *a, **k: ("https://dead/master.m3u8", "m3u8", "https://referer/"))
    monkeypatch.setattr(wf, "_resolve_first_playable", slow_local)
    monkeypatch.setattr(wf, "pick_fastest_mirror", lambda *a, **k: None)
    monkeypatch.setattr(wf, "_report_local_resolution", lambda *a, **k: None)
    monkeypatch.setattr(player_mod, "stream_is_alive", fake_alive)

    r = wf._resolve_episode({"mirrors": {"eps1": "https://mirror"}}, 12, quiet=True, source="anime-sama", slug="jjk")

    assert r["url"] == "https://ok/master.m3u8"
    assert "https://dead/master.m3u8" in alive_seen


def test_api_dead_url_embed_ref_fallback_wins_and_reports(monkeypatch):
    """Dead API URL with an embed referer -> re-resolve the embed locally,
    win as api-fallback, and write the fresh URL back to the API."""
    reported = []

    def fake_report(source, slug, n, r):
        reported.append((slug, n, r["url"]))

    monkeypatch.setattr("anisama.cli.api_client.resolve_episode", lambda *a, **k: ("https://dead/master.m3u8", "m3u8", "https://smoothpre.com/embed/abc123"))
    monkeypatch.setattr("anisama.resolver.resolve_url", lambda u: {"url": "https://ok/master.m3u8", "type": "m3u8"})
    _no_local(monkeypatch)
    monkeypatch.setattr(wf, "_report_local_resolution", fake_report)
    monkeypatch.setattr(player_mod, "stream_is_alive", lambda url, rtype="mp4", referer=None, timeout=8: url == "https://ok/master.m3u8")

    r = wf._resolve_episode({"mirrors": {"eps1": "https://mirror"}}, 12, quiet=True, source="anime-sama", slug="jjk")

    assert r["url"] == "https://ok/master.m3u8"
    assert r["referer"] == "https://smoothpre.com/embed/abc123"
    assert reported == [("jjk", 12, "https://ok/master.m3u8")]


def test_api_dead_url_embed_ref_fallback_dead_rejected(monkeypatch):
    """If the embed re-resolve is also dead, nothing wins."""
    monkeypatch.setattr("anisama.cli.api_client.resolve_episode", lambda *a, **k: ("https://dead/master.m3u8", "m3u8", "https://smoothpre.com/embed/abc123"))
    monkeypatch.setattr("anisama.resolver.resolve_url", lambda u: {"url": "https://also-dead/master.m3u8", "type": "m3u8"})
    _no_local(monkeypatch)
    monkeypatch.setattr(player_mod, "stream_is_alive", lambda *a, **k: False)

    r = wf._resolve_episode({"mirrors": {"eps1": "https://mirror"}}, 12, quiet=True, source="anime-sama", slug="jjk")

    assert r is None


def test_api_dead_non_embed_ref_not_re_resolved(monkeypatch):
    """A dead API URL whose referer is not an embed page is simply rejected."""
    called = []

    monkeypatch.setattr("anisama.cli.api_client.resolve_episode", lambda *a, **k: ("https://dead/master.m3u8", "m3u8", "https://anime-sama.to/catalogue/x/ep12"))
    monkeypatch.setattr("anisama.resolver.resolve_url", lambda u: called.append(u) or {})
    _no_local(monkeypatch)
    monkeypatch.setattr(player_mod, "stream_is_alive", lambda *a, **k: False)

    r = wf._resolve_episode({"mirrors": {"eps1": "https://mirror"}}, 12, quiet=True, source="anime-sama", slug="jjk")

    assert r is None
    assert called == []


def test_local_winner_reports_to_api(monkeypatch):
    reported = []

    def fake_report(source, slug, n, r):
        reported.append((slug, n, r["url"]))

    def slow_api(source, slug, num, fresh=False):
        time.sleep(0.3)
        return ("https://api/master.m3u8", "m3u8", "")

    monkeypatch.setattr("anisama.cli.api_client.resolve_episode", slow_api)
    monkeypatch.setattr(wf, "_resolve_first_playable", lambda *a, **k: {"url": "https://ok/master.m3u8", "type": "m3u8", "referer": ""})
    monkeypatch.setattr(wf, "pick_fastest_mirror", lambda *a, **k: None)
    monkeypatch.setattr(wf, "_report_local_resolution", fake_report)
    monkeypatch.setattr(player_mod, "stream_is_alive", lambda *a, **k: True)

    r = wf._resolve_episode({"mirrors": {"eps1": "https://mirror"}}, 12, quiet=True, source="anime-sama", slug="jjk")

    assert r["url"] == "https://ok/master.m3u8"
    assert reported == [("jjk", 12, "https://ok/master.m3u8")]


def test_embed_resolved_to_direct_stream(monkeypatch):
    """API embeds are resolved to a direct stream, never handed to the player."""
    checked = []

    def fake_alive(url, rtype="mp4", referer=None, timeout=8):
        checked.append(url)
        return True

    embed = "https://uqload.vc/embed-abc.html"
    monkeypatch.setattr("anisama.cli.api_client.resolve_episode", lambda *a, **k: (embed, "embed", ""))
    monkeypatch.setattr("anisama.resolver.resolve_url", lambda u: {"url": "https://cdn/master.m3u8", "type": "m3u8"})
    _no_local(monkeypatch)
    monkeypatch.setattr(player_mod, "stream_is_alive", fake_alive)

    r = wf._resolve_episode({"mirrors": {"eps1": "https://mirror"}}, 12, quiet=True, source="anime-sama", slug="jjk")

    assert r["url"] == "https://cdn/master.m3u8"
    assert r["type"] == "m3u8"
    assert embed not in checked
    assert "https://cdn/master.m3u8" in checked


def test_embed_browser_fallback(monkeypatch):
    """When no direct stream exists, playback keeps the embed for the browser."""
    embed = "https://franime.fr/watch2/?a=1"
    monkeypatch.setattr("anisama.cli.api_client.resolve_episode", lambda *a, **k: (embed, "embed", ""))
    monkeypatch.setattr("anisama.resolver.resolve_url", lambda u: {"url": u, "type": "embed"})
    _no_local(monkeypatch)

    r = wf._resolve_episode({"mirrors": {"eps1": "https://mirror"}}, 12, quiet=True, source="anime-sama", slug="jjk",
                            allow_embed=True)

    assert r["url"] == embed
    assert r["type"] == "embed"


def test_embed_not_returned_for_download(monkeypatch):
    embed = "https://franime.fr/watch2/?a=1"
    monkeypatch.setattr("anisama.cli.api_client.resolve_episode", lambda *a, **k: (embed, "embed", ""))
    monkeypatch.setattr("anisama.resolver.resolve_url", lambda u: {"url": u, "type": "embed"})
    _no_local(monkeypatch)

    r = wf._resolve_episode({"mirrors": {"eps1": "https://mirror"}}, 12, quiet=True, source="anime-sama", slug="jjk")

    assert r is None


def test_all_dead_returns_none(monkeypatch):
    monkeypatch.setattr("anisama.cli.api_client.resolve_episode", lambda *a, **k: ("https://dead/master.m3u8", "m3u8", "https://referer/"))
    monkeypatch.setattr(wf, "_resolve_first_playable", lambda *a, **k: None)
    monkeypatch.setattr(wf, "pick_fastest_mirror", lambda *a, **k: {"url": "https://dead2/master.m3u8", "type": "m3u8", "referer": ""})
    monkeypatch.setattr(wf, "_report_local_resolution", lambda *a, **k: None)
    monkeypatch.setattr(player_mod, "stream_is_alive", lambda *a, **k: False)

    r = wf._resolve_episode({"mirrors": {"eps1": "https://mirror"}}, 12, quiet=True, source="anime-sama", slug="jjk")

    assert r is None


def test_fallback_pick_fastest_alive(monkeypatch):
    monkeypatch.setattr("anisama.cli.api_client.resolve_episode", lambda *a, **k: ("https://dead/master.m3u8", "m3u8", "https://referer/"))
    monkeypatch.setattr(wf, "_resolve_first_playable", lambda *a, **k: None)
    monkeypatch.setattr(wf, "pick_fastest_mirror", lambda *a, **k: {"url": "https://fb/master.m3u8", "type": "m3u8", "referer": ""})
    monkeypatch.setattr(wf, "_report_local_resolution", lambda *a, **k: None)
    monkeypatch.setattr(player_mod, "stream_is_alive", lambda url, *a, **k: url == "https://fb/master.m3u8")

    r = wf._resolve_episode({"mirrors": {"eps1": "https://mirror"}}, 12, quiet=True, source="anime-sama", slug="jjk")

    assert r["url"] == "https://fb/master.m3u8"
