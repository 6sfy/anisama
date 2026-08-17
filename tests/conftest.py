"""Shared fixtures for anisama tests."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def tmp_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temp directory and set ANISAMA_DATA_DIR to it.

    Also re-import anisama.config so that module-level path constants
    pick up the new env var value.
    """
    monkeypatch.setenv("ANISAMA_DATA_DIR", str(tmp_path))

    # Force re-evaluation of config module paths by reimporting
    import anisama.config
    import importlib
    importlib.reload(anisama.config)

    # Also reload cache so it picks up the new config paths
    import anisama.cache
    importlib.reload(anisama.cache)

    return tmp_path


@pytest.fixture()
def sample_catalog() -> list[dict]:
    """Return a sample catalog JSON list."""
    return [
        {
            "title": "Attack on Titan",
            "link": "https://anime-sama.to/catalogue/attack-on-titan",
            "alt_titles": ["Shingeki no Kyojin", "AoT"],
            "genres": ["Action", "Drama", "Fantasy"],
        },
        {
            "title": "One Piece",
            "link": "https://anime-sama.to/catalogue/one-piece",
            "alt_titles": [],
            "genres": ["Action", "Adventure", "Comedy"],
        },
        {
            "title": "Demon Slayer",
            "link": "https://anime-sama.to/catalogue/demon-slayer",
            "alt_titles": ["Kimetsu no Yaiba"],
            "genres": ["Action", "Supernatural"],
        },
    ]


@pytest.fixture()
def mock_httpx_client():
    """Mock httpx.Client so unit tests never make real HTTP calls."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = ""
    mock_response.content = b""
    mock_response.json.return_value = []
    mock_client.get.return_value = mock_response
    mock_client.post.return_value = mock_response
    with patch("anisama.http_client.get_client", return_value=mock_client):
        yield mock_client
