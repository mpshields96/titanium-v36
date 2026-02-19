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
from datetime import datetime, timezone
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


def _extract_open_prices(game: dict) -> dict[str, float]:
    """
    Extract {"home": price, "away": price} from a raw game dict.

    Tries books in PREFERRED_BOOKS order, uses the first h2h market found.
    Returns {} if no usable h2h prices are found.
    """
    home_price: Optional[float] = None
    away_price: Optional[float] = None

    bookmakers = game.get("bookmakers", [])
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
        return {"home": home_price, "away": away_price}
    return {}


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

        prices = _extract_open_prices(game)
        if prices:
            _OPEN_PRICE_CACHE[event_id] = prices
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


# ---------------------------------------------------------------------------
# Passive RLM detection (zero additional API calls)
# ---------------------------------------------------------------------------
#
# Reverse Line Movement (RLM): price moves AGAINST public betting direction.
# If the public is on Team A but the line moves in favour of Team A's opponent,
# sharp money is pushing it back. That's a sharp signal worth +25 pts.
#
# Algorithm:
#   1. Open price is the baseline (frozen at first fetch via cache_open_prices).
#   2. On each refresh, compute current implied probability from the h2h price.
#   3. If implied prob shifted ≥ RLM_THRESHOLD against the public's side → RLM.
#
# public_on_side heuristic (Phase 1 — no public % data from Odds API):
#   Assume public bets favorites. Price < -105 → public_on_side = True.
#   Threshold: -105 is the approximate line where casual bettors stop fading
#   and start backing the favourite. This is a heuristic; upgrade when
#   a public % data source is wired in.
#
# RLM_THRESHOLD: 3% implied probability shift.
#   At -110, 5 cents is only ~1.1% shift — market noise.
#   3% implied shift ≈ 3–4 cents at typical prices: material, not noise.
#   R&D validated Feb 2026.
#
# Returns: dict[event_id → bool]
#   True  = RLM confirmed for this event (pass as rlm_data to rank_bets()).
#   False = no RLM detected or insufficient data.
# ---------------------------------------------------------------------------

RLM_THRESHOLD = 0.03   # 3% implied probability shift = material sharp signal
_PUBLIC_FAVORITE_THRESHOLD = -105   # prices shorter than this → assume public side


def _american_to_implied(american: float) -> float:
    """
    Convert American odds to implied probability (vig included).
    Inline to avoid circular import with edge_calculator.
    """
    if american < 0:
        return (-american) / (-american + 100)
    else:
        return 100 / (american + 100)


def compute_rlm(games: list[dict]) -> dict[str, bool]:
    """
    Detect Reverse Line Movement for a list of games by comparing current
    h2h prices against cached opening prices.

    Call AFTER cache_open_prices() has been called at least once this session.
    Safe to call with an empty cache — returns all False.

    Args:
        games: Current raw game dicts from fetch_game_lines() / fetch_batch_odds().
               Each game must have: id, home_team, away_team, bookmakers.

    Returns:
        Dict mapping event_id → bool.
        True  = RLM confirmed (sharp money moving line against public side).
        False = no RLM, or not enough data (open price not cached).

    Example:
        raw = fetch_game_lines("basketball_nba")
        cache_open_prices(raw)   # first fetch — freeze open prices
        # ... later in same session after prices update ...
        raw2 = fetch_game_lines("basketball_nba")
        rlm_data = compute_rlm(raw2)
        ranked = rank_bets(candidates, rlm_data=rlm_data)
    """
    result: dict[str, bool] = {}

    for game in games:
        event_id = game.get("id")
        if not event_id:
            continue

        open_entry = _OPEN_PRICE_CACHE.get(event_id)
        if open_entry is None:
            result[event_id] = False   # no baseline — skip
            continue

        # Get current h2h price from preferred book
        bookmakers = game.get("bookmakers", [])
        home_team = game.get("home_team", "")
        away_team = game.get("away_team", "")

        current_home: Optional[float] = None
        current_away: Optional[float] = None

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
                            if name == home_team:
                                current_home = float(price)
                            elif name == away_team:
                                current_away = float(price)
                        break
                if current_home is not None:
                    break

        if current_home is None or current_away is None:
            result[event_id] = False
            continue

        open_home = open_entry["home"]
        open_away = open_entry["away"]

        # Implied probability at open and now (vig-inclusive — directional signal only)
        open_home_prob  = _american_to_implied(open_home)
        open_away_prob  = _american_to_implied(open_away)
        curr_home_prob  = _american_to_implied(current_home)
        curr_away_prob  = _american_to_implied(current_away)

        # Public side heuristic: public backs the favourite (price < _PUBLIC_FAVORITE_THRESHOLD)
        # If home is the favourite, public_on_home = True; RLM fires if line moves TOWARD away.
        home_is_fav = open_home < _PUBLIC_FAVORITE_THRESHOLD
        away_is_fav = open_away < _PUBLIC_FAVORITE_THRESHOLD

        rlm_detected = False

        if home_is_fav:
            # Public on home. RLM = away's implied prob increased ≥ threshold
            # (line moved toward away despite public money on home).
            shift = curr_away_prob - open_away_prob
            if shift >= RLM_THRESHOLD:
                rlm_detected = True
                logger.debug(
                    "RLM: %s — public on home, away prob +%.1f%% (open %.0f → curr %.0f)",
                    event_id, shift * 100, open_away, current_away,
                )
        elif away_is_fav:
            # Public on away. RLM = home's implied prob increased ≥ threshold.
            shift = curr_home_prob - open_home_prob
            if shift >= RLM_THRESHOLD:
                rlm_detected = True
                logger.debug(
                    "RLM: %s — public on away, home prob +%.1f%% (open %.0f → curr %.0f)",
                    event_id, shift * 100, open_home, current_home,
                )
        # else: neither team is a clear favourite — no RLM signal (pick'em games are noise)

        result[event_id] = rlm_detected

    rlm_count = sum(1 for v in result.values() if v)
    logger.info("compute_rlm: %d/%d events show RLM", rlm_count, len(result))
    return result


# ---------------------------------------------------------------------------
# Schedule-derived rest days (zero additional API calls)
# ---------------------------------------------------------------------------
#
# The Odds API returns commence_time (ISO 8601) on every game.
# By diffing consecutive game times per team across the full raw_games list,
# we can compute real rest days without any extra API call.
#
# Usage:
#   raw_games = fetch_game_lines("basketball_nba")
#   schedule_rest = compute_rest_days_from_schedule(raw_games)
#   # Pass to _apply_nba_kill() for live rest data instead of stubs.
#
# Return value: dict[team_name, int | None]
#   int  = days of rest before the NEXT game in the window (≥0, 0 = B2B)
#   None = team appears only once in window; caller falls back to stub
# ---------------------------------------------------------------------------


def compute_rest_days_from_schedule(
    raw_games: list[dict],
) -> dict[str, Optional[int]]:
    """
    Derive rest days for every team from commence_time diffs in raw_games.

    Logic:
      1. Build a list of game commence_times for each team (home + away).
      2. Sort each team's games chronologically.
      3. For teams with >= 2 games: rest_days = diff between game[0] and game[1]
         rounded down to whole days (0 = B2B / same day, 1 = one day rest, etc.).
      4. For teams with exactly 1 game in the window: return None → caller uses
         kill_switch_feed stub value instead.

    Args:
        raw_games: Raw game list from fetch_game_lines() for a single sport.
                   Each game must have: home_team, away_team, commence_time (ISO 8601).

    Returns:
        Dict mapping team name → rest_days (int) or None.
        rest_days=0 means back-to-back (played yesterday or today).
        rest_days=None means only one game found — use stub fallback.
    """
    # team → sorted list of commence_time datetimes
    team_times: dict[str, list[datetime]] = {}

    for game in raw_games:
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        ct_str = game.get("commence_time", "")
        if not ct_str:
            continue

        try:
            # Parse ISO 8601 — handles "2026-02-18T23:00:00Z" and "+00:00" variants
            ct_str_clean = ct_str.replace("Z", "+00:00")
            ct = datetime.fromisoformat(ct_str_clean)
            if ct.tzinfo is None:
                ct = ct.replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            logger.warning("compute_rest_days: could not parse commence_time %r", ct_str)
            continue

        for team in (home, away):
            if team:
                team_times.setdefault(team, []).append(ct)

    result: dict[str, Optional[int]] = {}
    for team, times in team_times.items():
        times.sort()
        if len(times) < 2:
            result[team] = None  # only one game in window → use stub
            continue

        # Diff between the two nearest consecutive games
        delta = times[1] - times[0]
        rest_days = max(0, int(delta.total_seconds() // 86400))
        result[team] = rest_days

    logger.info(
        "compute_rest_days: %d teams resolved (%d None/stub fallback)",
        sum(1 for v in result.values() if v is not None),
        sum(1 for v in result.values() if v is None),
    )
    return result
