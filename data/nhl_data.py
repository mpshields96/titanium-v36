"""
data/nhl_data.py — NHL real-time goalie starter detection
==========================================================
Polls the free NHL Stats API to detect backup goalies before puck drop.

Endpoint used:
  api-web.nhle.com/v1/gamecenter/{gameId}/boxscore
  Response: playerByGameStats.{awayTeam|homeTeam}.goalies[n].starter (bool)

Constraints:
- ZERO quota cost — completely independent of Odds API
- Starter field only populates once game state moves from FUT to loading (~T-60min)
- Returns None when starter not yet confirmed (FUT state) — caller handles gracefully
- No API key required — public NHL endpoint

Architecture rule: NO imports from edge_calculator, odds_fetcher, or app.
This module is data-only; nhl_kill_switch() in edge_calculator.py is the gate that acts on it.

Usage in app.py run_pipeline():
    from data.nhl_data import get_starters_for_odds_game, cache_goalie_status
    result = get_starters_for_odds_game(game_id)
    if result is not None:
        away_backup = not result["away"]["starter_confirmed"]
        home_backup = not result["home"]["starter_confirmed"]
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level goalie cache — keyed by Odds API event_id
# Scheduler writes this; parse_game_markets() reads it via get_cached_goalie_status()
# ---------------------------------------------------------------------------
_goalie_cache: dict[str, dict] = {}


def cache_goalie_status(event_id: str, status: dict) -> None:
    """Store goalie starter status for an NHL event."""
    _goalie_cache[event_id] = status


def get_cached_goalie_status(event_id: str) -> Optional[dict]:
    """
    Retrieve cached goalie starter status for an event.
    Returns None if not yet polled or not an NHL game.
    """
    return _goalie_cache.get(event_id)


def clear_goalie_cache() -> None:
    """Clear the goalie cache. Used for testing."""
    _goalie_cache.clear()


def goalie_cache_size() -> int:
    """Return number of events in the goalie cache."""
    return len(_goalie_cache)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NHL_BOXSCORE_URL = "https://api-web.nhle.com/v1/gamecenter/{game_id}/boxscore"
_NHL_SCHEDULE_URL = "https://api-web.nhle.com/v1/schedule/{date}"
_REQUEST_TIMEOUT = 10  # seconds

# Odds API team name → NHL short-form lookup for name matching
# Source: standard NHL API "abbrev" values mapped to common Odds API variations
_TEAM_NAME_MAP: dict[str, str] = {
    # Eastern Conference
    "Boston Bruins": "BOS",
    "Buffalo Sabres": "BUF",
    "Detroit Red Wings": "DET",
    "Florida Panthers": "FLA",
    "Montreal Canadiens": "MTL",
    "Ottawa Senators": "OTT",
    "Tampa Bay Lightning": "TBL",
    "Toronto Maple Leafs": "TOR",
    "Carolina Hurricanes": "CAR",
    "Columbus Blue Jackets": "CBJ",
    "New Jersey Devils": "NJD",
    "New York Islanders": "NYI",
    "New York Rangers": "NYR",
    "Philadelphia Flyers": "PHI",
    "Pittsburgh Penguins": "PIT",
    "Washington Capitals": "WSH",
    # Western Conference
    "Winnipeg Jets": "WPG",
    "Colorado Avalanche": "COL",
    "Dallas Stars": "DAL",
    "Minnesota Wild": "MIN",
    "Nashville Predators": "NSH",
    "St. Louis Blues": "STL",
    "Utah Hockey Club": "UTA",
    "Anaheim Ducks": "ANA",
    "Calgary Flames": "CGY",
    "Edmonton Oilers": "EDM",
    "Los Angeles Kings": "LAK",
    "San Jose Sharks": "SJS",
    "Seattle Kraken": "SEA",
    "Vancouver Canucks": "VAN",
    "Vegas Golden Knights": "VGK",
    "Chicago Blackhawks": "CHI",
}

# Inverse: NHL abbrev → canonical full name
_ABBREV_TO_FULL: dict[str, str] = {v: k for k, v in _TEAM_NAME_MAP.items()}


# ---------------------------------------------------------------------------
# Team name normalization
# ---------------------------------------------------------------------------

def normalize_team_name(name: str) -> Optional[str]:
    """
    Normalize a team name string to a canonical NHL abbreviation.

    Handles:
    - Full name: "Boston Bruins" → "BOS"
    - Abbrev pass-through: "BOS" → "BOS"
    - Partial match on last word (city-only or name-only): "Bruins" → "BOS"
    - Case-insensitive

    Returns None if no match found.

    >>> normalize_team_name("Boston Bruins")
    'BOS'
    >>> normalize_team_name("bruins")
    'BOS'
    >>> normalize_team_name("NYR")
    'NYR'
    >>> normalize_team_name("Unknown FC")
    """
    if not name:
        return None

    cleaned = name.strip()

    # Exact abbrev match (e.g. "BOS")
    upper = cleaned.upper()
    if upper in _ABBREV_TO_FULL:
        return upper

    # Exact full name match (case-insensitive)
    for full, abbrev in _TEAM_NAME_MAP.items():
        if full.lower() == cleaned.lower():
            return abbrev

    # Partial: last word of name (e.g. "Bruins", "Rangers")
    last_word = cleaned.split()[-1].lower()
    for full, abbrev in _TEAM_NAME_MAP.items():
        if full.split()[-1].lower() == last_word:
            return abbrev

    # Partial: any word in the canonical name
    cleaned_lower = cleaned.lower()
    for full, abbrev in _TEAM_NAME_MAP.items():
        if cleaned_lower in full.lower():
            return abbrev

    logger.debug("normalize_team_name: no match for %r", name)
    return None


# ---------------------------------------------------------------------------
# NHL Schedule — get game IDs for today
# ---------------------------------------------------------------------------

def get_nhl_game_ids_for_date(
    date_str: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> list[dict]:
    """
    Fetch NHL schedule for a given date and return list of game dicts.

    Each dict has keys:
        game_id (int), away_team (str abbrev), home_team (str abbrev),
        game_start_utc (datetime), game_state (str)

    Args:
        date_str: "YYYY-MM-DD". Defaults to today UTC.
        session: Optional requests.Session for test injection.

    Returns:
        List of game dicts. Empty list on error or no games.
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    url = _NHL_SCHEDULE_URL.format(date=date_str)
    requester = session or requests

    try:
        resp = requester.get(url, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("get_nhl_game_ids_for_date error: %s", exc)
        return []

    games = []
    # Schedule endpoint: data["gameWeek"][0]["games"] when date matches
    for week_day in data.get("gameWeek", []):
        if week_day.get("date") == date_str:
            for g in week_day.get("games", []):
                game_id = g.get("id")
                away_abbrev = g.get("awayTeam", {}).get("abbrev", "")
                home_abbrev = g.get("homeTeam", {}).get("abbrev", "")
                start_str = g.get("startTimeUTC", "")
                game_state = g.get("gameState", "FUT")

                try:
                    start_utc = datetime.fromisoformat(
                        start_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    start_utc = None

                if game_id:
                    games.append({
                        "game_id": game_id,
                        "away_team": away_abbrev,
                        "home_team": home_abbrev,
                        "game_start_utc": start_utc,
                        "game_state": game_state,
                    })
    return games


# ---------------------------------------------------------------------------
# Boxscore — extract starting goalies
# ---------------------------------------------------------------------------

def get_nhl_starters_for_game(
    game_id: int,
    session: Optional[requests.Session] = None,
) -> Optional[dict]:
    """
    Fetch boxscore for a specific game and extract confirmed starting goalies.

    Returns None when:
    - Game is still in FUT state (rosters not finalized)
    - API error
    - No goalies found in response

    Returns dict when starters confirmed:
        {
            "game_id": int,
            "away": {
                "starter_confirmed": bool,
                "starter_name": str | None,   # e.g. "S. Knight"
                "backup_name": str | None,
            },
            "home": {
                "starter_confirmed": bool,
                "starter_name": str | None,
                "backup_name": str | None,
            },
        }

    Args:
        game_id: NHL game ID (from schedule endpoint).
        session: Optional requests.Session for test injection.
    """
    url = _NHL_BOXSCORE_URL.format(game_id=game_id)
    requester = session or requests

    try:
        resp = requester.get(url, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("get_nhl_starters_for_game(%s) error: %s", game_id, exc)
        return None

    player_stats = data.get("playerByGameStats")
    if not player_stats:
        # FUT state — playerByGameStats is absent or null
        logger.debug("game %s: playerByGameStats absent (FUT state)", game_id)
        return None

    result = {"game_id": game_id}

    for side in ("awayTeam", "homeTeam"):
        side_key = "away" if side == "awayTeam" else "home"
        goalies = player_stats.get(side, {}).get("goalies", [])

        if not goalies:
            # No goalie data yet — return None to signal not-ready
            return None

        starter_name = None
        backup_name = None
        starter_confirmed = False

        for g in goalies:
            name = g.get("name", {}).get("default", "")
            is_starter = g.get("starter", False)
            if is_starter:
                starter_name = name
                starter_confirmed = True
            else:
                if backup_name is None:
                    backup_name = name

        result[side_key] = {
            "starter_confirmed": starter_confirmed,
            "starter_name": starter_name,
            "backup_name": backup_name,
        }

    # Must have both sides populated
    if "away" not in result or "home" not in result:
        return None

    return result


# ---------------------------------------------------------------------------
# High-level: match Odds API team names to NHL game + fetch starters
# ---------------------------------------------------------------------------

def get_starters_for_odds_game(
    away_team_name: str,
    home_team_name: str,
    game_start_utc: Optional[datetime] = None,
    session: Optional[requests.Session] = None,
) -> Optional[dict]:
    """
    Given Odds API team names and scheduled start time, fetch starter info.

    Strategy:
    1. Normalize team names to NHL abbrevs
    2. Find matching game in today's NHL schedule
    3. If game_start_utc provided and >90 min away → return None (too early, FUT)
    4. Otherwise fetch boxscore and return starter data

    Args:
        away_team_name: Odds API away team name (e.g. "Boston Bruins", "Bruins")
        home_team_name: Odds API home team name
        game_start_utc: Optional game start time (UTC) for timing gate
        session: Optional requests.Session for test injection.

    Returns:
        get_nhl_starters_for_game() result or None
    """
    # Timing gate: don't poll boxscore if game is >90 min away
    if game_start_utc is not None:
        now = datetime.now(timezone.utc)
        minutes_to_start = (game_start_utc - now).total_seconds() / 60
        if minutes_to_start > 90:
            logger.debug(
                "Too early to poll boxscore for %s @ %s (%.0f min to start)",
                away_team_name, home_team_name, minutes_to_start
            )
            return None

    away_abbrev = normalize_team_name(away_team_name)
    home_abbrev = normalize_team_name(home_team_name)

    if not away_abbrev or not home_abbrev:
        logger.warning(
            "get_starters_for_odds_game: could not normalize '%s' or '%s'",
            away_team_name, home_team_name
        )
        return None

    # Fetch today's schedule to find the matching game ID
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    scheduled_games = get_nhl_game_ids_for_date(today_str, session=session)

    game_id = None
    for g in scheduled_games:
        if g["away_team"] == away_abbrev and g["home_team"] == home_abbrev:
            game_id = g["game_id"]
            break

    if game_id is None:
        logger.debug(
            "get_starters_for_odds_game: no game found for %s @ %s on %s",
            away_abbrev, home_abbrev, today_str
        )
        return None

    return get_nhl_starters_for_game(game_id, session=session)
