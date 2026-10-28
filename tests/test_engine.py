"""Tests du fast engine local (anisama.engine) — parsing offline via mocks réseau.

Les fixtures reproduisent le format RÉEL documenté dans anisama/engine/README.md
(episodes.js, panneauAnime, lecteursInfos, résultats de recherche).
"""

import pytest
from anisama.engine import anime_sama as AS

CATALOGUE_HTML = """
<html><body>
<script>
panneauAnime("Avec Fillers", "saison1/vostfr");
panneauAnime("Sans Fillers", "saison1hs/vostfr");
panneauFilm("Film", "film/vostfr");
panneauScan("Manga", "scan/vostfr");
</script>
<script src='https://anime-sama.to/catalogue/naruto/saison1/vostfr/episodes.js?filever=18916'></script>
</body></html>
"""

EPISODES_JS = """
var eps1 = ['https://lpayer.embed4me.com/#sat5e', 'https://lpayer.embed4me.com/#z9j18', 'https://lpayer.embed4me.com/#aa11b'];
var eps2 = ['https://ansembed.net/embed-y2dfh1ndem54.html', 'https://ansembed.net/embed-xyz99.html', 'https://ansembed.net/embed-ooo11.html'];
var lecteursInfos = {"ansembed.net":{"nom":"Vidmoly","pub":1,"hd":true},
                     "sibnet.ru":{"nom":"Sibnet","pub":0,"hd":false,"mort":true}};
"""

SEARCH_HTML = """
<div>
<a href="https://anime-sama.to/catalogue/naruto/" class="asn-search-result">
  <h3 class="asn-search-result-title">Naruto</h3>
</a>
<a href="https://anime-sama.to/catalogue/naruto-shippuden/" class="asn-search-result">
  <h3 class="asn-search-result-title">Naruto: Shippuden</h3>
</a>
</div>
"""


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code
        self.headers = {}


@pytest.fixture
def engine_offline(monkeypatch):
    """AnimeSama avec réseau mocké + domaine forcé (pas d'appel sortant)."""
    monkeypatch.setattr(AS.AnimeSama, "_pick_domain", lambda self: "anime-sama.to")

    def fake_request(sess, method, url, **kw):
        if "fetch.php" in url and method == "POST":
            return FakeResponse(SEARCH_HTML)
        if "episodes.js" in url:
            return FakeResponse(EPISODES_JS)
        if "/catalogue/" in url:
            return FakeResponse(CATALOGUE_HTML)
        return FakeResponse("<html></html>")

    monkeypatch.setattr(AS, "request", fake_request)
    return AS.AnimeSama()


def test_seasons_filters_scans(engine_offline):
    ss = engine_offline.seasons("naruto")
    assert ss == [
        {"name": "Avec Fillers", "url": "https://anime-sama.to/catalogue/naruto/saison1/vostfr/"},
        {"name": "Sans Fillers", "url": "https://anime-sama.to/catalogue/naruto/saison1hs/vostfr/"},
        {"name": "Film", "url": "https://anime-sama.to/catalogue/naruto/film/vostfr/"},
    ]


def test_episodes_mirrors_by_index(engine_offline):
    eps = engine_offline.episodes("naruto")
    assert len(eps) == 3
    assert eps[0]["mirrors"] == {
        "eps1": "https://lpayer.embed4me.com/#sat5e",
        "eps2": "https://ansembed.net/embed-y2dfh1ndem54.html",
    }
    assert [e["number"] for e in eps] == [1, 2, 3]


def test_resolve_returns_direct_embed(engine_offline):
    res = engine_offline.resolve("naruto", 2)
    assert res["url"] == "https://lpayer.embed4me.com/#z9j18"
    assert res["type"] == "embed"
    assert res["host"] == "lpayer.embed4me.com"


def test_hosts(engine_offline):
    hosts = engine_offline.hosts("naruto")
    assert hosts == {
        "lpayer.embed4me.com": ["eps1"],
        "ansembed.net": ["eps2"],
    }


def test_search(engine_offline):
    results = engine_offline.search("naruto")
    assert [r["slug"] for r in results] == ["naruto", "naruto-shippuden"]
    assert all(r["source"] == "anime-sama" for r in results)
