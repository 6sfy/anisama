"""Tests for anisama.sources module."""

from __future__ import annotations

import pytest


class TestSourcesDict:
    """Test SOURCES registry."""

    def test_sources_has_7_entries(self):
        from anisama.sources import SOURCES
        assert len(SOURCES) == 7

    def test_sources_has_expected_names(self):
        from anisama.sources import SOURCES
        expected = {"anime-sama", "voiranime", "myfluneo", "animesultra", "frenchanime", "animoflix", "franime"}
        assert set(SOURCES.keys()) == expected


class TestSourceAttributes:
    """Test each source has required attributes."""

    def test_source_has_required_attrs(self):
        from anisama.sources import SOURCES
        for name, anisama in SOURCES.items():
            assert hasattr(anisama, "name"), f"{name} missing name"
            assert hasattr(anisama, "catalog"), f"{name} missing catalog"
            assert hasattr(anisama, "search"), f"{name} missing search"
            assert hasattr(anisama, "episodes"), f"{name} missing episodes"
            assert hasattr(anisama, "resolve"), f"{name} missing resolve"
            assert callable(anisama.catalog), f"{name} catalog not callable"
            assert callable(anisama.search), f"{name} search not callable"
            assert callable(anisama.episodes), f"{name} episodes not callable"
            assert callable(anisama.resolve), f"{name} resolve not callable"

    def test_source_has_optional_attrs(self):
        from anisama.sources import SOURCES
        for name, anisama in SOURCES.items():
            assert hasattr(anisama, "needs_playwright"), f"{name} missing needs_playwright"
            assert hasattr(anisama, "description"), f"{name} missing description"

    def test_source_names_match_keys(self):
        from anisama.sources import SOURCES
        for key, anisama in SOURCES.items():
            assert anisama.name == key

    def test_playwright_sources(self):
        from anisama.sources import SOURCES
        pw_sources = [name for name, anisama in SOURCES.items() if anisama.needs_playwright]
        assert "myfluneo" in pw_sources
        assert "animoflix" in pw_sources
        assert "anime-sama" not in pw_sources

    def test_descriptions_non_empty(self):
        from anisama.sources import SOURCES
        for name, anisama in SOURCES.items():
            assert anisama.description, f"{name} has empty description"


class TestGetSources:
    """Test get_sources() filtering."""

    def test_get_sources_all(self):
        from anisama.sources import get_sources
        all_sources = get_sources()
        assert len(all_sources) == 7

    def test_get_sources_playwright_only(self):
        from anisama.sources import get_sources
        pw_sources = get_sources(needs_playwright=True)
        assert len(pw_sources) == 2
        for s in pw_sources:
            assert s.needs_playwright is True

    def test_get_sources_non_playwright(self):
        from anisama.sources import get_sources
        non_pw = get_sources(needs_playwright=False)
        assert len(non_pw) == 5
        for s in non_pw:
            assert s.needs_playwright is False

    def test_get_sources_returns_list(self):
        from anisama.sources import get_sources
        result = get_sources()
        assert isinstance(result, list)
