"""Tests for stream liveness checks and dead-URL retry logic."""

from unittest.mock import patch

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


def test_dead_api_url_triggers_fresh_retry(monkeypatch):
    calls = []

    def fake_api(source, slug, num, fresh=False):
        calls.append(fresh)
        if fresh:
            return ("https://good/master.m3u8", "m3u8", "https://referer/")
        return ("https://dead/master.m3u8", "m3u8", "https://referer/")

    monkeypatch.setattr("anisama.cli.api_client.resolve_episode", fake_api)
    monkeypatch.setattr("anisama.cli.workflow.resolve_best_mirror", lambda *a, **k: None)
    monkeypatch.setattr("anisama.cli.workflow.pick_fastest_mirror", lambda *a, **k: None)
    monkeypatch.setattr(player_mod, "stream_is_alive", lambda *a, **k: False)

    r = wf._resolve_episode({"mirrors": {"eps1": "https://mirror"}}, 12, quiet=True, source="anime-sama", slug="jjk")

    assert r["url"] == "https://good/master.m3u8"
    assert calls == [False, True]


def test_alive_local_result_skips_retry(monkeypatch):
    import time

    calls = []

    def fake_api(source, slug, num, fresh=False):
        calls.append(fresh)
        time.sleep(0.4)
        return ("https://dead/master.m3u8", "m3u8", "https://referer/")

    alive_checks = []

    def fake_alive(url, rtype="mp4", referer=None, timeout=8):
        alive_checks.append(url)
        return True

    monkeypatch.setattr("anisama.cli.api_client.resolve_episode", fake_api)
    monkeypatch.setattr("anisama.cli.workflow.resolve_best_mirror", lambda *a, **k: {"url": "https://ok/master.m3u8", "type": "m3u8", "referer": ""})
    monkeypatch.setattr("anisama.cli.workflow.pick_fastest_mirror", lambda *a, **k: None)
    monkeypatch.setattr(player_mod, "stream_is_alive", fake_alive)

    r = wf._resolve_episode({"mirrors": {"eps1": "https://mirror"}}, 12, quiet=True, source="anime-sama", slug="jjk")

    assert r["url"] == "https://ok/master.m3u8"
    assert len(alive_checks) == 1