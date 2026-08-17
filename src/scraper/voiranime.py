"""Voiranime scraper: seasons, episodes, and catalog."""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..config import VOIRANIME_DOMAIN, VOIRANIME_HEADERS, REQUEST_TIMEOUT
from ..http_client import get_client
from ..cache import download_voiranime_catalog


def voiranime_get_seasons(url):
    """Scrape the list of seasons from a Voiranime anime page."""
    client = get_client()
    r = client.get(url, headers=VOIRANIME_HEADERS)
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    seasons = []
    section = soup.find("section", id="seasons")
    if not section:
        return seasons
    for card in section.find_all("a", class_="season-card"):
        href = card.get("href", "")
        title_el = card.find("h3", class_="season-title")
        meta = card.find("div", class_="season-meta")
        langs = set()
        if meta:
            for badge in meta.find_all("span", class_="lang-badge"):
                langs.add(badge.get_text(strip=True).lower())
        name = title_el.get_text(strip=True) if title_el else ""
        if not name or not href:
            continue
        if not href.startswith("http"):
            href = urljoin(url, href)
        seasons.append({"name": name, "url": href, "langs": langs})
    return seasons


def voiranime_get_episodes(season_url, lang=None):
    """Scrape the list of episodes from a Voiranime season page."""
    client = get_client()
    r = client.get(season_url, headers=VOIRANIME_HEADERS)
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    eps = []
    grid = soup.find("div", class_="episodes-grid")
    if not grid:
        return eps
    for card in grid.find_all("a", class_="episode-card"):
        href = card.get("href", "")
        num_el = card.find("div", class_="episode-number")
        num = num_el.get_text(strip=True) if num_el else ""
        m = re.search(r"(\d+)", num)
        ep_num = int(m.group(1)) if m else 0
        langs_raw = card.get("data-langs", "")
        ep_langs = set(langs_raw.split()) if langs_raw else set()

        if lang and lang not in ep_langs:
            continue

        if not href.startswith("http"):
            href = urljoin(season_url, href)

        eps.append({"number": ep_num, "url": href, "langs": ep_langs})
    return eps


def voiranime_catalog(skip_slugs=None):
    """Download the Voiranime catalog. Thin wrapper around cache.download_voiranime_catalog."""
    return download_voiranime_catalog(skip_slugs=skip_slugs)
