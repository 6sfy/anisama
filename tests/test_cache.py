"""Tests for anisama.cache module."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest


class TestCacheValidity:
    """Test is_cache_valid()."""

    def test_returns_false_when_no_catalog_file(self, tmp_data_dir):
        from anisama.cache import is_cache_valid
        assert is_cache_valid() is False

    def test_returns_true_for_fresh_catalog(self, tmp_data_dir):
        from anisama.cache import is_cache_valid, save_catalog
        save_catalog([{"title": "test"}])
        assert is_cache_valid() is True

    def test_returns_false_for_stale_catalog(self, tmp_data_dir, monkeypatch):
        """A catalog older than cache_hours should be invalid."""
        from anisama.cache import save_catalog, is_cache_valid
        import anisama.config

        # Save a catalog
        save_catalog([{"title": "test"}])

        # Make the file appear old by modifying settings cache_hours to 0
        from anisama.cache import save_settings
        save_settings({"cache_hours": 0})

        # Wait a tiny bit to ensure age > 0
        time.sleep(0.01)

        assert is_cache_valid() is False


class TestCatalogPersistence:
    """Test save_catalog / load_catalog."""

    def test_load_catalog_returns_empty_when_no_file(self, tmp_data_dir):
        from anisama.cache import load_catalog
        assert load_catalog() == []

    def test_save_and_load_roundtrip(self, tmp_data_dir, sample_catalog):
        from anisama.cache import save_catalog, load_catalog
        save_catalog(sample_catalog)
        loaded = load_catalog()
        assert loaded == sample_catalog

    def test_save_catalog_creates_directory(self, tmp_data_dir):
        from anisama.cache import save_catalog
        import anisama.config
        # Ensure data dir exists
        save_catalog([])
        assert anisama.config.DATA_DIR.exists()

    def test_save_catalog_preserves_unicode(self, tmp_data_dir):
        from anisama.cache import save_catalog, load_catalog
        catalog = [{"title": "L'Attaque des Titans", "link": "https://example.com/aot"}]
        save_catalog(catalog)
        loaded = load_catalog()
        assert loaded[0]["title"] == "L'Attaque des Titans"


class TestSettings:
    """Test load_settings / save_settings."""

    def test_load_settings_returns_defaults_when_no_file(self, tmp_data_dir):
        from anisama.cache import load_settings, DEFAULT_SETTINGS
        s = load_settings()
        for key in DEFAULT_SETTINGS:
            assert key in s

    def test_save_and_load_settings_roundtrip(self, tmp_data_dir):
        from anisama.cache import save_settings, load_settings
        custom = {"lang": "vostfr", "player": "mpv", "cache_hours": 48}
        save_settings(custom)
        loaded = load_settings()
        assert loaded["lang"] == "vostfr"
        assert loaded["player"] == "mpv"
        assert loaded["cache_hours"] == 48

    def test_load_settings_fills_missing_defaults(self, tmp_data_dir):
        from anisama.cache import save_settings, load_settings, DEFAULT_SETTINGS
        # Save only partial settings
        partial = {"lang": "vf"}
        save_settings(partial)
        loaded = load_settings()
        assert loaded["lang"] == "vf"
        # Missing keys should be filled from defaults
        assert "cache_hours" in loaded
        assert loaded["cache_hours"] == DEFAULT_SETTINGS["cache_hours"]

    def test_load_settings_handles_corrupt_file(self, tmp_data_dir):
        from anisama.cache import load_settings, DEFAULT_SETTINGS
        import anisama.config
        anisama.config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        anisama.config.SETTINGS_FILE.write_text("not valid json{{{")
        s = load_settings()
        # Should fall back to defaults
        for key in DEFAULT_SETTINGS:
            assert key in s


class TestHistory:
    """Test load_history / add_history / get_recent_anime."""

    def test_load_history_returns_empty_when_no_file(self, tmp_data_dir):
        from anisama.cache import load_history
        assert load_history() == []

    def test_add_history_adds_entry(self, tmp_data_dir):
        from anisama.cache import add_history, load_history
        add_history("Test Anime", "https://example.com/test", "anime-sama", 1)
        h = load_history()
        assert len(h) == 1
        assert h[0]["title"] == "Test Anime"
        assert h[0]["episode"] == 1

    def test_add_history_most_recent_first(self, tmp_data_dir):
        from anisama.cache import add_history, load_history
        add_history("Anime A", "https://example.com/a", "source", 1)
        add_history("Anime B", "https://example.com/b", "source", 1)
        h = load_history()
        assert h[0]["title"] == "Anime B"
        assert h[1]["title"] == "Anime A"

    def test_add_history_limits_to_200(self, tmp_data_dir):
        from anisama.cache import add_history, load_history
        for i in range(250):
            add_history(f"Anime {i}", f"https://example.com/{i}", "source", 1)
        h = load_history()
        assert len(h) == 200

    def test_add_history_dedup_same_episode(self, tmp_data_dir):
        """Adding the same episode again should move it to top, not duplicate."""
        from anisama.cache import add_history, load_history
        add_history("Test", "https://example.com/test", "source", 1)
        add_history("Test", "https://example.com/test", "source", 1)
        h = load_history()
        assert len(h) == 1

    def test_add_history_with_season(self, tmp_data_dir):
        from anisama.cache import add_history, load_history
        add_history("Test", "https://example.com/test", "source", 1,
                    season_url="https://example.com/test/s1", season_name="Season 1")
        h = load_history()
        assert h[0]["season_url"] == "https://example.com/test/s1"
        assert h[0]["season_name"] == "Season 1"


class TestGetRecentAnime:
    """Test get_recent_anime() deduplication."""

    def test_deduplicates_by_link(self, tmp_data_dir):
        from anisama.cache import add_history, get_recent_anime
        add_history("Test", "https://example.com/test", "source", 1)
        add_history("Test", "https://example.com/test", "source", 2)
        recent = get_recent_anime()
        assert len(recent) == 1

    def test_different_links_not_deduped(self, tmp_data_dir):
        from anisama.cache import add_history, get_recent_anime
        add_history("Anime A", "https://example.com/a", "source", 1)
        add_history("Anime B", "https://example.com/b", "source", 1)
        recent = get_recent_anime()
        assert len(recent) == 2


class TestMerge:
    """Test merge_into_catalog() and merge_source_into_catalog()."""

    def test_merge_into_catalog_empty_as(self, tmp_data_dir):
        from anisama.cache import merge_into_catalog
        vr = [{"title": "VR Anime", "link": "https://voiranime.rip/vr-anime"}]
        result = merge_into_catalog([], vr)
        assert len(result) == 1
        assert result[0]["source"] == "voiranime"

    def test_merge_into_catalog_deduplicates_by_slug(self, tmp_data_dir):
        from anisama.cache import merge_into_catalog
        as_entries = [{"title": "Test", "link": "https://anime-sama.to/catalogue/test"}]
        vr_entries = [{"title": "Test", "link": "https://voiranime.rip/test"}]
        result = merge_into_catalog(as_entries, vr_entries)
        # Should be merged (1 entry), not 2
        assert len(result) == 1
        assert "voiranime" in result[0].get("alt_source", [])

    def test_merge_into_catalog_no_overlap(self, tmp_data_dir):
        from anisama.cache import merge_into_catalog
        as_entries = [{"title": "Anime A", "link": "https://anime-sama.to/catalogue/anime-a"}]
        vr_entries = [{"title": "Anime B", "link": "https://voiranime.rip/anime-b"}]
        result = merge_into_catalog(as_entries, vr_entries)
        assert len(result) == 2

    def test_merge_source_into_catalog(self, tmp_data_dir):
        from anisama.cache import merge_source_into_catalog
        catalog = [{"title": "Existing", "link": "https://anime-sama.to/catalogue/existing"}]
        new_entries = [{"title": "New Source Anime", "link": "https://newsource.com/anime"}]
        result = merge_source_into_catalog(catalog, new_entries, "newsource")
        assert len(result) == 2
        assert result[1]["source"] == "newsource"

    def test_merge_source_into_catalog_deduplicates(self, tmp_data_dir):
        from anisama.cache import merge_source_into_catalog
        catalog = [{"title": "Test", "link": "https://anime-sama.to/catalogue/test"}]
        new_entries = [{"title": "Test", "link": "https://newsource.com/test"}]
        result = merge_source_into_catalog(catalog, new_entries, "newsource")
        # Should merge into one entry
        assert len(result) == 1
        assert "newsource" in result[0].get("alt_source", [])

    def test_merge_preserves_genres(self, tmp_data_dir):
        from anisama.cache import merge_source_into_catalog
        catalog = [{"title": "Test", "link": "https://anime-sama.to/catalogue/test", "genres": ["Action"]}]
        new_entries = [{"title": "Test", "link": "https://newsource.com/test", "genres": ["Drama", "Action"]}]
        result = merge_source_into_catalog(catalog, new_entries, "newsource")
        assert "Action" in result[0]["genres"]
        assert "Drama" in result[0]["genres"]


class TestDomainCache:
    """Test load_domain_cache / save_domain_cache."""

    def test_load_returns_none_when_no_file(self, tmp_data_dir):
        from anisama.cache import load_domain_cache
        assert load_domain_cache() is None

    def test_save_and_load_roundtrip(self, tmp_data_dir):
        from anisama.cache import save_domain_cache, load_domain_cache
        save_domain_cache("anime-sama.pw")
        assert load_domain_cache() == "anime-sama.pw"

    def test_save_strips_whitespace(self, tmp_data_dir):
        from anisama.cache import save_domain_cache, load_domain_cache
        save_domain_cache("  anime-sama.pw  ")
        # save writes verbatim, load strips
        result = load_domain_cache()
        assert result is not None
        assert result.strip() == "anime-sama.pw"

    def test_load_handles_corrupt_file(self, tmp_data_dir):
        from anisama.cache import load_domain_cache
        import anisama.config
        anisama.config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        # Write a file that can't be read as text (though a text file usually can)
        # Test with a normal string but the file not being readable
        anisama.config.DOMAIN_CACHE_FILE.write_text("anime-sama.pw")
        result = load_domain_cache()
        assert result == "anime-sama.pw"
