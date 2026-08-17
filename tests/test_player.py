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


def test_stream_is_alive_mp4_head_ok():
    with patch("httpx.head", return_value=FakeResp()):
        assert player_mod.stream_is_alive("https://x/v.mp4", "mp4") is True


def test_stream_is_alive_mp4_head_405_falls_back_range():
    with patch("httpx.head", return_value=FakeResp(status=405)), patch("httpx.get", return_value=FakeResp(status=206)):
        assert player_mod.stream_is_alive("https://x/v.mp4", "mp4") is True


def test_stream_is_alive_mp4_head_404():
    with patch("httpx.head", return_value=FakeResp(status=404)):
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


def test_api_dead_url_rejected_local_wins(monkeypatch):
    """A dead URL from the API must never win the race."""
    alive_seen = []

    def fake_alive(url, rtype="mp4", referer=None, timeout=8):
        alive_seen.append(url)
        return False

    def slow_local(e, prefer_mp4=True):
        time.sleep(0.3)
        return {"url": "https://ok/master.m3u8", "type": "m3u8", "referer": ""}

    monkeypatch.setattr("anisama.cli.api_client.resolve_episode", lambda *a, **k: ("https://dead/master.m3u8", "m3u8", "https://referer/"))
    monkeypatch.setattr("anisama.cli.workflow.resolve_best_mirror", slow_local)
    monkeypatch.setattr("anisama.cli.workflow.pick_fastest_mirror", lambda *a, **k: None)
    monkeypatch.setattr(wf, "_report_local_resolution", lambda *a, **k: None)
    monkeypatch.setattr(player_mod, "stream_is_alive", fake_alive)

    r = wf._resolve_episode({"mirrors": {"eps1": "https://mirror"}}, 12, quiet=True, source="anime-sama", slug="jjk")

    assert r["url"] == "https://ok/master.m3u8"
    assert "https://dead/master.m3u8" in alive_seen


def test_local_winner_reports_to_api(monkeypatch):
    reported = []

    def fake_report(source, slug, n, r):
        reported.append((slug, n, r["url"]))

    def slow_api(source, slug, num, fresh=False):
        time.sleep(0.3)
        return ("https://api/master.m3u8", "m3u8", "")

    monkeypatch.setattr("anisama.cli.api_client.resolve_episode", slow_api)
    monkeypatch.setattr("anisama.cli.workflow.resolve_best_mirror", lambda *a, **k: {"url": "https://ok/master.m3u8", "type": "m3u8", "referer": ""})
    monkeypatch.setattr("anisama.cli.workflow.pick_fastest_mirror", lambda *a, **k: None)
    monkeypatch.setattr(wf, "_report_local_resolution", fake_report)
    monkeypatch.setattr(player_mod, "stream_is_alive", lambda *a, **k: True)

    r = wf._resolve_episode({"mirrors": {"eps1": "https://mirror"}}, 12, quiet=True, source="anime-sama", slug="jjk")

    assert r["url"] == "https://ok/master.m3u8"
    assert reported == [("jjk", 12, "https://ok/master.m3u8")]


def test_embed_type_skips_liveness_check(monkeypatch):
    checked = []

    def fake_alive(url, rtype="mp4", referer=None, timeout=8):
        checked.append(url)
        return True

    monkeypatch.setattr("anisama.cli.api_client.resolve_episode", lambda *a, **k: ("https://embed.example/page", "embed", ""))
    monkeypatch.setattr("anisama.cli.workflow.resolve_best_mirror", lambda *a, **k: None)
    monkeypatch.setattr("anisama.cli.workflow.pick_fastest_mirror", lambda *a, **k: None)
    monkeypatch.setattr(wf, "_report_local_resolution", lambda *a, **k: None)
    monkeypatch.setattr(player_mod, "stream_is_alive", fake_alive)

    r = wf._resolve_episode({"mirrors": {"eps1": "https://mirror"}}, 12, quiet=True, source="anime-sama", slug="jjk")

    assert r["url"] == "https://embed.example/page"
    assert checked == []


class _FakeEvent:
    def set(self):
        pass

    def wait(self, timeout=None):
        return False

    def is_set(self):
        return False


def test_all_dead_returns_none(monkeypatch):
    monkeypatch.setattr(wf.threading, "Event", lambda: _FakeEvent())
    monkeypatch.setattr("anisama.cli.api_client.resolve_episode", lambda *a, **k: ("https://dead/master.m3u8", "m3u8", "https://referer/"))
    monkeypatch.setattr("anisama.cli.workflow.resolve_best_mirror", lambda *a, **k: None)
    monkeypatch.setattr("anisama.cli.workflow.pick_fastest_mirror", lambda *a, **k: {"url": "https://dead2/master.m3u8", "type": "m3u8", "referer": ""})
    monkeypatch.setattr(wf, "_report_local_resolution", lambda *a, **k: None)
    monkeypatch.setattr(player_mod, "stream_is_alive", lambda *a, **k: False)

    r = wf._resolve_episode({"mirrors": {"eps1": "https://mirror"}}, 12, quiet=True, source="anime-sama", slug="jjk")

    assert r is None


def test_fallback_pick_fastest_alive(monkeypatch):
    monkeypatch.setattr(wf.threading, "Event", lambda: _FakeEvent())
    monkeypatch.setattr("anisama.cli.api_client.resolve_episode", lambda *a, **k: ("https://dead/master.m3u8", "m3u8", "https://referer/"))
    monkeypatch.setattr("anisama.cli.workflow.resolve_best_mirror", lambda *a, **k: None)
    monkeypatch.setattr("anisama.cli.workflow.pick_fastest_mirror", lambda *a, **k: {"url": "https://fb/master.m3u8", "type": "m3u8", "referer": ""})
    monkeypatch.setattr(wf, "_report_local_resolution", lambda *a, **k: None)
    monkeypatch.setattr(player_mod, "stream_is_alive", lambda *a, **k: True)

    r = wf._resolve_episode({"mirrors": {"eps1": "https://mirror"}}, 12, quiet=True, source="anime-sama", slug="jjk")

    assert r["url"] == "https://fb/master.m3u8"