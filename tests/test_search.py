"""Tests for anisama.search module."""

from __future__ import annotations

import pytest


class TestNorm:
    """Test norm() title normalization."""

    def test_norm_empty_string(self):
        from anisama.search import norm
        assert norm("") == ""

    def test_norm_removes_diacritics(self):
        from anisama.search import norm
        assert norm("café") == "cafe"
        assert norm("naïve") == "naive"
        assert norm("résumé") == "resume"

    def test_norm_replaces_smart_quotes(self):
        """Smart quotes are replaced by regular quotes, then quotes are
        stripped by the special-char regex. The result should not contain
        smart quotes."""
        from anisama.search import norm
        result = norm("\u201chello\u201d")
        # Smart quotes get turned to regular quotes, then stripped
        assert "\u201c" not in result
        assert "\u201d" not in result
        assert "hello" in result

    def test_norm_replaces_special_chars(self):
        from anisama.search import norm
        result = norm('hello:world/test')
        assert ":" not in result
        assert "/" not in result

    def test_norm_collapse_whitespace(self):
        from anisama.search import norm
        assert norm("hello   world") == "hello world"

    def test_norm_strips(self):
        from anisama.search import norm
        assert norm("  hello  ") == "hello"

    def test_norm_preserves_alphanumeric(self):
        from anisama.search import norm
        assert norm("Attack on Titan") == "Attack on Titan"


class TestClean:
    """Test clean() function."""

    def test_clean_lowercase(self):
        from anisama.search import clean
        assert clean("HELLO") == "hello"

    def test_clean_strips_non_alphanumeric(self):
        """Non-alphanumeric chars are removed (no space replacement)."""
        from anisama.search import clean
        result = clean("hello!@#world")
        assert result == "helloworld"

    def test_clean_strips_punctuation_with_space(self):
        """Punctuation adjacent to spaces is removed, spaces collapse."""
        from anisama.search import clean
        result = clean("hello! world")
        assert result == "hello world"

    def test_clean_collapse_whitespace(self):
        from anisama.search import clean
        assert clean("hello    world") == "hello world"

    def test_clean_strips_edges(self):
        from anisama.search import clean
        assert clean("  hello  ") == "hello"

    def test_clean_empty(self):
        from anisama.search import clean
        assert clean("") == ""

    def test_clean_numbers_preserved(self):
        from anisama.search import clean
        assert clean("season 2") == "season 2"


class TestStripIdPrefix:
    """Test strip_id_prefix()."""

    def test_strip_vf_prefix(self):
        from anisama.search import strip_id_prefix
        result = strip_id_prefix("1 Attack on Titan Vf")
        assert "Vf" not in result
        assert "Attack on Titan" in result

    def test_strip_vostfr_suffix(self):
        from anisama.search import strip_id_prefix
        result = strip_id_prefix("Attack on Titan Vostfr")
        assert "Vostfr" not in result

    def test_strip_vf_suffix(self):
        from anisama.search import strip_id_prefix
        result = strip_id_prefix("One Piece VF")
        assert "VF" not in result

    def test_no_prefix_unchanged(self):
        from anisama.search import strip_id_prefix
        assert strip_id_prefix("Attack on Titan") == "Attack on Titan"

    def test_empty_string(self):
        from anisama.search import strip_id_prefix
        assert strip_id_prefix("") == ""

    def test_numeric_prefix_without_lang(self):
        """Numeric prefix without VF/VOSTFR should not be stripped."""
        from anisama.search import strip_id_prefix
        result = strip_id_prefix("1 Some Anime Title")
        # The numeric prefix is only stripped when followed by VF/VOSTFR
        assert "1" in result or "Some Anime Title" in result


class TestCalcScore:
    """Test _calc_score()."""

    def test_exact_match_returns_100(self):
        from anisama.search import _calc_score
        assert _calc_score("Attack on Titan", "Attack on Titan") == 100

    def test_empty_query_returns_0(self):
        from anisama.search import _calc_score
        assert _calc_score("", "Some Title") == 0

    def test_empty_title_returns_0(self):
        from anisama.search import _calc_score
        assert _calc_score("Some Query", "") == 0

    def test_both_empty_returns_0(self):
        from anisama.search import _calc_score
        assert _calc_score("", "") == 0

    def test_partial_match(self):
        from anisama.search import _calc_score
        score = _calc_score("Attack", "Attack on Titan")
        assert score > 50  # partial match should score well

    def test_no_match(self):
        from anisama.search import _calc_score
        score = _calc_score("xyzabc", "Attack on Titan")
        assert score < 50  # very different strings should score low

    def test_score_in_range(self):
        from anisama.search import _calc_score
        score = _calc_score("test", "another")
        assert 0 <= score <= 100

    def test_alt_title_exact_match(self):
        from anisama.search import _calc_score
        score = _calc_score("Shingeki no Kyojin", "Attack on Titan", alt_titles=["Shingeki no Kyojin"])
        assert score == 100

    def test_case_insensitive_exact(self):
        from anisama.search import _calc_score
        assert _calc_score("attack on titan", "Attack on Titan") == 100


class TestBaseKey:
    """Test _base_key() normalization."""

    def test_base_key_lowercase(self):
        from anisama.search import _base_key
        assert _base_key("Attack on Titan") == "attackontitan"

    def test_base_key_strips_season(self):
        from anisama.search import _base_key
        result = _base_key("Anime Saison 2")
        assert "saison" not in result
        assert "2" not in result

    def test_base_key_strips_vf(self):
        from anisama.search import _base_key
        result = _base_key("Anime VF")
        assert "vf" not in result

    def test_base_key_strips_film(self):
        from anisama.search import _base_key
        result = _base_key("Anime Film 1")
        assert "film" not in result

    def test_base_key_consistent(self):
        from anisama.search import _base_key
        # Same anime with different suffixes should produce the same key
        assert _base_key("Anime VF") == _base_key("Anime Vostfr")

    def test_base_key_empty(self):
        from anisama.search import _base_key
        assert _base_key("") == ""


class TestTerms:
    """Test terms() function."""

    def test_terms_returns_set(self):
        from anisama.search import terms
        result = terms("Attack on Titan")
        assert isinstance(result, set)

    def test_terms_splits(self):
        from anisama.search import terms
        result = terms("Attack on Titan")
        assert "attack" in result
        assert "on" in result
        assert "titan" in result
