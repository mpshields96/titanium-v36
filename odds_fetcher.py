"""
odds_fetcher.py — TITANIUM V36.1
==================================
All Odds API calls live here. No math, no UI.

Responsibilities:
- Authenticate with The Odds API (key from environment)
- Fetch odds for each sport using the correct market strings
- Return raw data as Python dicts/lists for edge_calculator to consume

API base URL: https://api.the-odds-api.com/v4/sports
Regions: us
Format: american
Book preference: DraftKings first, fallback to first available

DO NOT add betting math or Streamlit calls to this file.
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.the-odds-api.com/v4/sports"

# Market strings per sport key (used in all fetch functions).
# NOTE: player props (player_points, player_pass_yds, etc.) are NOT supported
# on the current API tier — confirmed 422 error Feb 2026. Removed from all keys.
MARKETS = {
    "basketball_nba":          "h2h,spreads,totals",
    "americanfootball_nfl":    "h2h,spreads,totals",
    "basketball_ncaab":        "h2h,spreads,totals",
    "icehockey_nhl":           "h2h,spreads,totals",
    "soccer_epl":              "h2h,spreads,totals",
}

# Preferred bookmaker key (DraftKings)
DRAFTKINGS_KEY = "draftkings"


def fetch_batch_odds(sport_key: str, api_key: str) -> list:
    """
    Fetch odds for NHL, NCAAB, or Soccer in a single API call.
    Use this for sports that don't need per-game prop calls (cheaper).

    Endpoint: GET /v4/sports/{sport_key}/odds
    Params:   regions=us, oddsFormat=american, markets=<per-sport string>

    Args:
        sport_key: Odds API sport key string, e.g. "icehockey_nhl".
        api_key:   Your Odds API key.

    Returns:
        List of game dicts from the API (raw JSON), or empty list on any failure.
        Each game dict contains: id, sport_key, commence_time, home_team,
        away_team, bookmakers (list of bookmaker dicts with markets inside).
    """
    markets = MARKETS.get(sport_key)
    if markets is None:
        logger.error("fetch_batch_odds: unknown sport_key '%s'", sport_key)
        return []

    url = f"{BASE_URL}/{sport_key}/odds"
    params = {
        "apiKey":      api_key,
        "regions":     "us",
        "markets":     markets,
        "oddsFormat":  "american",
    }

    try:
        response = requests.get(url, params=params, timeout=10)

        # 401 = bad API key, 422 = bad parameters, 429 = quota exceeded
        if response.status_code == 401:
            logger.error("fetch_batch_odds: invalid API key (401)")
            return []
        if response.status_code == 422:
            logger.error("fetch_batch_odds: bad request parameters (422): %s", response.text)
            return []
        if response.status_code == 429:
            logger.error("fetch_batch_odds: API quota exceeded (429)")
            return []

        response.raise_for_status()  # catch any other 4xx/5xx codes

        games = response.json()

        # Log remaining quota so we can track API usage (it's in the response headers)
        remaining = response.headers.get("x-requests-remaining", "unknown")
        used = response.headers.get("x-requests-used", "unknown")
        logger.info(
            "fetch_batch_odds: fetched %d games for %s | quota used=%s remaining=%s",
            len(games), sport_key, used, remaining,
        )

        return games

    except requests.exceptions.Timeout:
        logger.error("fetch_batch_odds: request timed out for sport_key '%s'", sport_key)
        return []
    except requests.exceptions.ConnectionError:
        logger.error("fetch_batch_odds: no network connection for sport_key '%s'", sport_key)
        return []
    except requests.exceptions.RequestException as exc:
        logger.error("fetch_batch_odds: unexpected request error: %s", exc)
        return []
    except ValueError:
        # requests raises ValueError if .json() fails to parse
        logger.error("fetch_batch_odds: API returned non-JSON response")
        return []


def fetch_events(sport: str) -> list:
    """
    Fetch the list of upcoming events for NBA or NFL.
    Used as the first step before fetching per-game props.

    Args:
        sport: "NBA" or "NFL"

    Returns:
        List of event dicts containing event IDs, teams, and commence times.
    """
    # TODO Session 2: Implement API call
    pass


def fetch_game_props(sport: str, event_id: str) -> dict:
    """
    Fetch player prop odds for a single game (NBA/NFL only).
    Expensive call — minimize usage. Call only for games that pass collar.

    Args:
        sport: "NBA" or "NFL"
        event_id: Event ID string returned by fetch_events()

    Returns:
        Dict of prop odds for the specified game.
    """
    # TODO Session 2: Implement API call
    pass


def _preferred_book(bookmakers: list) -> dict | None:
    """
    Return DraftKings odds if available, otherwise the first bookmaker.
    Internal helper — called by edge_calculator when parsing raw game dicts.

    Args:
        bookmakers: List of bookmaker dicts from the API response.
            Each dict has keys: key (str), title (str), markets (list).

    Returns:
        Single bookmaker dict, or None if the list is empty.
    """
    if not bookmakers:
        return None
    for book in bookmakers:
        if book.get("key") == DRAFTKINGS_KEY:
            return book
    return bookmakers[0]
