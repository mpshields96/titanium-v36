"""
odds_fetcher.py — TITANIUM V36.1
==================================
All Odds API calls live here. No math, no UI.

Responsibilities:
- Authenticate with The Odds API (key from environment or secrets.toml)
- Fetch game lines for all sports in a single call per sport
- Return raw data as Python dicts/lists for edge_calculator to consume
- Track API quota across the session

API base URL: https://api.the-odds-api.com/v4/sports
Regions: us | Format: american
Book preference: DraftKings → FanDuel → BetMGM → BetRivers → Caesars → first available

DO NOT add betting math or Streamlit calls to this file.
"""

import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.the-odds-api.com/v4/sports"

# Book preference order — DraftKings first, then fallbacks
PREFERRED_BOOKS = ["draftkings", "fanduel", "betmgm", "betrivers", "caesars"]

# Market strings per sport key.
# NOTE: player props NOT supported on bulk endpoint — confirmed 422 Feb 2026.
# Soccer: spreads cause 422 on bulk endpoint — h2h,totals only.
MARKETS = {
    "basketball_nba":               "h2h,spreads,totals",
    "americanfootball_nfl":         "h2h,spreads,totals",
    "basketball_ncaab":             "h2h,spreads,totals",
    "icehockey_nhl":                "h2h,spreads,totals",
    "soccer_epl":                   "h2h,totals",
    "soccer_france_ligue_one":      "h2h,totals",
    "soccer_germany_bundesliga":    "h2h,totals",
    "soccer_italy_serie_a":         "h2h,totals",
    "soccer_spain_la_liga":         "h2h,totals",
    "soccer_usa_mls":               "h2h,totals",
}

# Friendly sport name → API sport key
SPORT_KEYS = {
    "NBA":          "basketball_nba",
    "NFL":          "americanfootball_nfl",
    "NCAAB":        "basketball_ncaab",
    "NHL":          "icehockey_nhl",
    "EPL":          "soccer_epl",
    "LIGUE1":       "soccer_france_ligue_one",
    "BUNDESLIGA":   "soccer_germany_bundesliga",
    "SERIE_A":      "soccer_italy_serie_a",
    "LA_LIGA":      "soccer_spain_la_liga",
    "MLS":          "soccer_usa_mls",
}


# ---------------------------------------------------------------------------
# Quota tracker — shared across all calls in a session
# ---------------------------------------------------------------------------

class QuotaTracker:
    """Track API usage across the session so we don't blow the quota."""

    def __init__(self):
        self.used: int = 0
        self.remaining: Optional[int] = None
        self.last_cost: int = 0

    def update(self, headers: dict) -> None:
        try:
            self.remaining = int(headers.get("x-requests-remaining", self.remaining or 0))
            self.used = int(headers.get("x-requests-used", self.used))
            self.last_cost = int(headers.get("x-requests-last", 0))
        except (ValueError, TypeError):
            pass

    def report(self) -> str:
        return (
            f"API quota | used={self.used} "
            f"remaining={self.remaining} "
            f"last_call_cost={self.last_cost}"
        )


# Module-level tracker — imported by app.py for display
quota = QuotaTracker()


# ---------------------------------------------------------------------------
# API key loader
# ---------------------------------------------------------------------------

def _get_api_key() -> str:
    """
    Load API key from environment variable or .streamlit/secrets.toml.
    Never hardcode the key in source files.
    """
    # 1. Environment variable (CI, production)
    key = os.environ.get("ODDS_API_KEY", "")
    if key:
        return key

    # 2. Streamlit secrets.toml (local dev)
    secrets_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        ".streamlit", "secrets.toml"
    )
    if os.path.exists(secrets_path):
        with open(secrets_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("ODDS_API_KEY"):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if key:
                        return key

    raise ValueError(
        "ODDS_API_KEY not found. Add it to .streamlit/secrets.toml or "
        "set it as an environment variable."
    )


# ---------------------------------------------------------------------------
# Shared GET with retry and quota tracking
# ---------------------------------------------------------------------------

def _get(url: str, params: dict, retries: int = 2) -> Optional[list | dict]:
    """
    Shared HTTP GET with error handling, quota tracking, and retry on timeout.
    Injects API key automatically — never pass the key in params directly.

    Returns parsed JSON (list or dict) on success, None on any failure.
    """
    try:
        api_key = _get_api_key()
    except ValueError as exc:
        logger.error("_get: %s", exc)
        return None

    params = dict(params)  # don't mutate caller's dict
    params["apiKey"] = api_key

    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=15)
            quota.update(resp.headers)

            if resp.status_code == 401:
                logger.error("Invalid API key (401)")
                return None
            if resp.status_code == 422:
                logger.error(
                    "Bad request parameters (422): %s — url=%s",
                    resp.text, url
                )
                return None
            if resp.status_code == 429:
                logger.error("Quota exceeded (429). %s", quota.report())
                return None
            if resp.status_code == 404:
                logger.warning("Not found (404): %s", url)
                return None

            resp.raise_for_status()
            logger.debug("%s | %s", quota.report(), url)
            return resp.json()

        except requests.exceptions.Timeout:
            logger.warning(
                "Timeout on attempt %d/%d: %s", attempt + 1, retries + 1, url
            )
            if attempt < retries:
                time.sleep(2)

        except requests.exceptions.ConnectionError:
            logger.error("Connection error: %s", url)
            return None

        except requests.exceptions.RequestException as exc:
            logger.error("Request error: %s", exc)
            return None

        except ValueError:
            logger.error("Non-JSON response from: %s", url)
            return None

    return None


# ---------------------------------------------------------------------------
# Book selection helpers
# ---------------------------------------------------------------------------

def preferred_book(bookmakers: list) -> Optional[dict]:
    """
    Return the highest-preference bookmaker available.
    Priority: DraftKings → FanDuel → BetMGM → BetRivers → Caesars → first available.

    Args:
        bookmakers: List of bookmaker dicts from the API response.

    Returns:
        Single bookmaker dict, or None if list is empty.
    """
    if not bookmakers:
        return None
    book_map = {b["key"]: b for b in bookmakers}
    for key in PREFERRED_BOOKS:
        if key in book_map:
            return book_map[key]
    return bookmakers[0]


def all_books(bookmakers: list) -> list:
    """
    Return all bookmakers sorted by preference order.
    Preferred books come first; any remaining books appended after.
    Used by the consensus edge calculator which needs ALL books.

    Args:
        bookmakers: List of bookmaker dicts from the API response.

    Returns:
        Sorted list of bookmaker dicts.
    """
    if not bookmakers:
        return []
    book_map = {b["key"]: b for b in bookmakers}
    result = []
    seen = set()
    for key in PREFERRED_BOOKS:
        if key in book_map:
            result.append(book_map[key])
            seen.add(key)
    for b in bookmakers:
        if b["key"] not in seen:
            result.append(b)
    return result


# ---------------------------------------------------------------------------
# Game lines — bulk fetch (1 API call per sport)
# ---------------------------------------------------------------------------

def fetch_game_lines(sport_key: str) -> list:
    """
    Fetch h2h / spreads / totals for all upcoming games in one sport.
    This is the primary fetch function — use for all sports.

    Cost: 1 API request.

    Args:
        sport_key: Odds API key string (e.g. "basketball_ncaab").
                   Use SPORT_KEYS dict to convert friendly names.

    Returns:
        List of game dicts, each containing:
        { id, sport_key, commence_time, home_team, away_team, bookmakers }
        Returns empty list on any failure.
    """
    markets = MARKETS.get(sport_key)
    if not markets:
        logger.error("fetch_game_lines: unknown sport_key '%s'", sport_key)
        return []

    url = f"{BASE_URL}/{sport_key}/odds"
    params = {
        "regions":    "us",
        "markets":    markets,
        "oddsFormat": "american",
    }

    data = _get(url, params)
    if not isinstance(data, list):
        return []

    logger.info(
        "fetch_game_lines: %d games for %s | %s",
        len(data), sport_key, quota.report()
    )
    return data


def fetch_batch_odds(sport_key: str, api_key: str) -> list:
    """
    Legacy wrapper kept for backwards compatibility with Session 2 tests.
    Calls fetch_game_lines() internally.
    New code should call fetch_game_lines() directly.

    Args:
        sport_key: Odds API sport key string.
        api_key:   API key (injected into environment for this call).

    Returns:
        List of game dicts, or empty list on failure.
    """
    os.environ["ODDS_API_KEY"] = api_key
    return fetch_game_lines(sport_key)


# ---------------------------------------------------------------------------
# Convenience: fetch by friendly sport name
# ---------------------------------------------------------------------------

def fetch_sport(sport: str) -> list:
    """
    Fetch game lines using a friendly sport name (e.g. "NCAAB", "NHL").

    Args:
        sport: Friendly sport name — must be a key in SPORT_KEYS.

    Returns:
        List of game dicts, or empty list on failure or unknown sport.
    """
    key = SPORT_KEYS.get(sport.upper())
    if not key:
        logger.error("fetch_sport: unknown sport '%s'. Valid: %s",
                     sport, list(SPORT_KEYS.keys()))
        return []
    return fetch_game_lines(key)


# ---------------------------------------------------------------------------
# Quota status (called by app.py for display)
# ---------------------------------------------------------------------------

def get_quota_status() -> str:
    """Return current API quota status as a human-readable string."""
    return quota.report()


# ---------------------------------------------------------------------------
# Soccer open-price cache (drift detection — zero API cost)
# ---------------------------------------------------------------------------
#
# The Odds API has no `open_price` field. Drift must be detected passively
# by caching prices at session start and diffing on refresh.
#
# Usage pattern:
#   1. Call cache_open_prices(games) once at session start (first fetch).
#   2. On refresh, get_open_price(event_id, outcome) returns the cached price.
#   3. Pass open_price to get_soccer_kill_inputs() for drift computation.
#
# The cache lives for the session only (module-level dict, no persistence).
# Zero API calls — uses data already fetched by fetch_game_lines().
# ---------------------------------------------------------------------------

_OPEN_PRICE_CACHE: dict[str, dict[str, float]] = {}
# Structure: { event_id: { "home": american_odds, "away": american_odds } }


def cache_open_prices(games: list[dict]) -> int:
    """
    Cache opening prices for a list of games. Only stores prices that are
    not already in the cache (i.e. the first call wins — open price is frozen).

    Call once per session at first fetch, before any refresh.

    Args:
        games: Raw game dicts from fetch_game_lines() / fetch_batch_odds().
               Each game must have: id, home_team, away_team, bookmakers.

    Returns:
        Number of new events cached (0 if all already present).
    """
    new_count = 0
    for game in games:
        event_id = game.get("id")
        if not event_id or event_id in _OPEN_PRICE_CACHE:
            continue  # already cached — open price frozen

        bookmakers = game.get("bookmakers", [])
        home_price: Optional[float] = None
        away_price: Optional[float] = None

        # Try preferred books in order, then fall back to first available
        book_map = {b["key"]: b for b in bookmakers if "markets" in b}
        for book_key in PREFERRED_BOOKS:
            if book_key in book_map:
                for market in book_map[book_key].get("markets", []):
                    if market.get("key") == "h2h":
                        for outcome in market.get("outcomes", []):
                            name = outcome.get("name", "")
                            price = outcome.get("price")
                            if price is None:
                                continue
                            if name == game.get("home_team"):
                                home_price = float(price)
                            elif name == game.get("away_team"):
                                away_price = float(price)
                        break
                if home_price is not None:
                    break

        if home_price is not None and away_price is not None:
            _OPEN_PRICE_CACHE[event_id] = {
                "home": home_price,
                "away": away_price,
            }
            new_count += 1

    logger.info("cache_open_prices: %d new events cached (total: %d)",
                new_count, len(_OPEN_PRICE_CACHE))
    return new_count


def get_open_price(event_id: str, side: str = "home") -> Optional[float]:
    """
    Return the cached opening price for an event.

    Args:
        event_id: Game event ID from the Odds API.
        side:     "home" or "away".

    Returns:
        American odds float, or None if event not in cache.
    """
    entry = _OPEN_PRICE_CACHE.get(event_id)
    if entry is None:
        return None
    return entry.get(side)


def clear_open_price_cache() -> None:
    """Clear all cached open prices. Call at session start if needed."""
    _OPEN_PRICE_CACHE.clear()
    logger.info("cache_open_prices: cache cleared")
