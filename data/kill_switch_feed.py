"""
kill_switch_feed.py — TITANIUM V36.1
======================================
Stub data layer for kill switch live inputs.
No live scraping. Returns mock/default values until real sources are wired.

Promoted from R&D (titanium-experimental/core/data/kill_switch_feed.py) — Session 6.
Updated Session 9: full 30-team NBA coverage + full 32-team NFL stadium wind map.

Provides inputs for:
    nba_kill_switch()    — rest days, B2B schedule, pace std dev
    nfl_kill_switch()    — weather/wind, QB status
    ncaab_kill_switch()  — 3PT reliance, tempo data
    soccer_kill_switch() — market drift, lineup status

Real sources (future wiring):
    - Wind:          Weather API (OpenWeather or similar) keyed to stadium + game time
    - Rest/B2B:      Schedule data derived from Odds API commence_time diffs
    - 3PT reliance:  Basketball Reference / Barttorvik team stats
    - Market drift:  Computed from line open vs current in odds_fetcher
    - Lineup:        RotowWire / injury feed

Wire-in pattern:
    from data.kill_switch_feed import get_nba_kill_inputs
    from edge_calculator import nba_kill_switch

    inputs = get_nba_kill_inputs(bet_team, opp_team, bet.line, bet.market_type)
    killed, reason = nba_kill_switch(**{k: v for k, v in inputs.items() if k != 'data_live'})
    if killed:
        continue  # drop from candidates

DO NOT add API calls, Streamlit calls, or betting math to this file.
"""

from typing import Optional


# ---------------------------------------------------------------------------
# NBA stubs
# ---------------------------------------------------------------------------

# Static rest data — days of rest per team since last game.
# 0 = B2B (played yesterday), 1 = one day rest, 2+ = well rested.
# Stub snapshot: replace with schedule-derived data when available.
# Full 30-team coverage — unknown team falls back to _DEFAULT_NBA_REST (1).
_NBA_REST_DAYS: dict[str, int] = {
    # Atlantic
    "Boston Celtics":           2,
    "Brooklyn Nets":            1,
    "New York Knicks":          0,   # B2B
    "Philadelphia 76ers":       2,
    "Toronto Raptors":          1,
    # Central
    "Chicago Bulls":            2,
    "Cleveland Cavaliers":      1,
    "Detroit Pistons":          2,
    "Indiana Pacers":           1,
    "Milwaukee Bucks":          1,
    # Southeast
    "Atlanta Hawks":            1,
    "Charlotte Hornets":        2,
    "Miami Heat":               0,   # B2B
    "Orlando Magic":            2,
    "Washington Wizards":       2,
    # Northwest
    "Denver Nuggets":           2,
    "Minnesota Timberwolves":   1,
    "Oklahoma City Thunder":    1,
    "Portland Trail Blazers":   2,
    "Utah Jazz":                1,
    # Pacific
    "Golden State Warriors":    1,
    "Los Angeles Clippers":     2,
    "Los Angeles Lakers":       2,
    "Phoenix Suns":             2,
    "Sacramento Kings":         1,
    # Southwest
    "Dallas Mavericks":         2,
    "Houston Rockets":          1,
    "Memphis Grizzlies":        1,
    "New Orleans Pelicans":     2,
    "San Antonio Spurs":        2,
}

# Pace standard deviation — volatility of possessions per game.
# High std_dev (>4) on totals triggers kill switch.
# Source: last 15 games pace variance (synthetic stub ~2024-25).
_NBA_PACE_STD_DEV: dict[str, float] = {
    # Atlantic
    "Boston Celtics":           2.8,
    "Brooklyn Nets":            3.6,
    "New York Knicks":          2.7,
    "Philadelphia 76ers":       2.3,
    "Toronto Raptors":          3.1,
    # Central
    "Chicago Bulls":            3.0,
    "Cleveland Cavaliers":      2.5,
    "Detroit Pistons":          3.4,
    "Indiana Pacers":           4.2,   # high — run-and-gun
    "Milwaukee Bucks":          2.4,
    # Southeast
    "Atlanta Hawks":            3.7,
    "Charlotte Hornets":        3.9,
    "Miami Heat":               3.5,
    "Orlando Magic":            2.9,
    "Washington Wizards":       3.1,
    # Northwest
    "Denver Nuggets":           2.9,
    "Minnesota Timberwolves":   2.6,
    "Oklahoma City Thunder":    3.0,
    "Portland Trail Blazers":   3.8,
    "Utah Jazz":                3.5,
    # Pacific
    "Golden State Warriors":    3.9,
    "Los Angeles Clippers":     2.8,
    "Los Angeles Lakers":       2.6,
    "Phoenix Suns":             4.1,   # high — up-tempo
    "Sacramento Kings":         4.0,   # high — fast pace
    # Southwest
    "Dallas Mavericks":         3.2,
    "Houston Rockets":          3.3,
    "Memphis Grizzlies":        3.6,
    "New Orleans Pelicans":     3.1,
    "San Antonio Spurs":        3.4,
}

_DEFAULT_NBA_REST = 1
_DEFAULT_PACE_STD_DEV = 3.0


def get_nba_rest_days(team: str) -> tuple[int, bool]:
    """Return (rest_days, is_live). rest_days=0 means B2B. is_live=False = stub data."""
    val = _NBA_REST_DAYS.get(team, _DEFAULT_NBA_REST)
    is_live = team in _NBA_REST_DAYS
    return val, is_live


def get_nba_pace_std_dev(team: str) -> tuple[float, bool]:
    """Return (pace_std_dev, is_live) for an NBA team."""
    val = _NBA_PACE_STD_DEV.get(team, _DEFAULT_PACE_STD_DEV)
    is_live = team in _NBA_PACE_STD_DEV
    return val, is_live


def get_nba_kill_inputs(
    bet_team: str,
    opp_team: str,
    spread: float,
    market_type: str = "spread",
    star_absent: bool = False,
) -> dict:
    """
    Build the full input dict for nba_kill_switch() from stub data.

    Returns dict with keys matching nba_kill_switch() params, plus
    'data_live' bool indicating whether inputs are real or stubbed.
    """
    bet_rest, bet_live = get_nba_rest_days(bet_team)
    opp_rest, opp_live = get_nba_rest_days(opp_team)
    pace_std, pace_live = get_nba_pace_std_dev(bet_team)

    rest_disadvantage = bet_rest < opp_rest
    b2b = bet_rest == 0

    return {
        "rest_disadvantage": rest_disadvantage,
        "spread": spread,
        "star_absent": star_absent,
        "b2b": b2b,
        "pace_std_dev": pace_std,
        "market_type": market_type,
        "data_live": bet_live and opp_live and pace_live,
    }


# ---------------------------------------------------------------------------
# NFL stubs
# ---------------------------------------------------------------------------

# Wind forecasts by home team — mph at game time (stub averages by stadium type/location).
# In production: replace with weather API keyed to stadium GPS + game commence_time.
#
# Indoor / retractable-roof stadiums: 0-3 mph (controlled environment).
# Outdoor cold-weather: 8-14 mph average.
# Outdoor warm/mild: 4-8 mph average.
# Coastal/lakefront: 7-12 mph average.
#
# All 32 NFL teams covered. Unknown home team falls back to _DEFAULT_WIND_MPH (5.0).
# Stubs intentionally below 15mph threshold — kill fires on real weather data, not stubs.
_NFL_WIND_FORECAST: dict[str, float] = {
    # AFC East
    "Buffalo Bills":            13.0,  # outdoor, western NY — windiest in NFL
    "Miami Dolphins":            6.0,  # outdoor, South Florida — mild
    "New England Patriots":      9.0,  # outdoor, New England — cold/wind
    "New York Jets":             7.0,  # outdoor, NJ — variable
    # AFC North
    "Baltimore Ravens":          7.0,  # outdoor, mid-Atlantic
    "Cincinnati Bengals":        6.0,  # outdoor, Ohio River valley
    "Cleveland Browns":         11.0,  # outdoor, Lake Erie — very wind-prone
    "Pittsburgh Steelers":       8.0,  # outdoor, river valley
    # AFC South
    "Houston Texans":            2.0,  # indoor (NRG Stadium — retractable, usually closed)
    "Indianapolis Colts":        2.0,  # indoor (Lucas Oil)
    "Jacksonville Jaguars":      6.0,  # outdoor, coastal Florida
    "Tennessee Titans":          5.0,  # outdoor, Nashville — moderate
    # AFC West
    "Denver Broncos":            9.0,  # outdoor, altitude/wind — variable
    "Kansas City Chiefs":        7.0,  # outdoor, Midwest plains
    "Las Vegas Raiders":         2.0,  # indoor (Allegiant Stadium)
    "Los Angeles Chargers":      4.0,  # indoor (SoFi — open but sheltered)
    # NFC East
    "Dallas Cowboys":            2.0,  # indoor (AT&T Stadium)
    "New York Giants":           7.0,  # outdoor, NJ — variable
    "Philadelphia Eagles":       8.0,  # outdoor, mid-Atlantic
    "Washington Commanders":     6.0,  # outdoor, mid-Atlantic
    # NFC North
    "Chicago Bears":             9.0,  # outdoor, lakefront — wind-prone
    "Detroit Lions":             2.0,  # indoor (Ford Field)
    "Green Bay Packers":        12.0,  # outdoor, Wisconsin — most wind-exposed
    "Minnesota Vikings":         2.0,  # indoor (US Bank Stadium)
    # NFC South
    "Atlanta Falcons":           2.0,  # indoor (Mercedes-Benz)
    "Carolina Panthers":         5.0,  # outdoor, Charlotte — mild
    "New Orleans Saints":        2.0,  # indoor (Caesars Superdome)
    "Tampa Bay Buccaneers":      5.0,  # outdoor, Florida Gulf — mild
    # NFC West
    "Arizona Cardinals":         2.0,  # indoor (State Farm — retractable, usually closed)
    "Los Angeles Rams":          4.0,  # indoor (SoFi — open but sheltered)
    "San Francisco 49ers":       8.0,  # outdoor, Bay Area — afternoon wind
    "Seattle Seahawks":          7.0,  # outdoor, Pacific Northwest
}

_DEFAULT_WIND_MPH = 5.0


def get_nfl_wind_mph(home_team: str) -> tuple[float, bool]:
    """Return (wind_mph, is_live) for an NFL home team's stadium."""
    val = _NFL_WIND_FORECAST.get(home_team, _DEFAULT_WIND_MPH)
    is_live = home_team in _NFL_WIND_FORECAST
    return val, is_live


def get_nfl_kill_inputs(
    home_team: str,
    total: float,
    backup_qb: bool = False,
    market_type: str = "total",
) -> dict:
    """Build full input dict for nfl_kill_switch()."""
    wind, wind_live = get_nfl_wind_mph(home_team)
    return {
        "wind_mph": wind,
        "total": total,
        "backup_qb": backup_qb,
        "market_type": market_type,
        "data_live": wind_live,
    }


# ---------------------------------------------------------------------------
# NCAAB stubs
# ---------------------------------------------------------------------------

# Fraction of team's offense derived from 3-point shooting.
# Source in production: Barttorvik 3PA rate * 3 / team_ppg approximation.
_NCAAB_THREE_POINT_RELIANCE: dict[str, float] = {
    "Gonzaga":        0.31,
    "Duke":           0.35,
    "Kansas":         0.33,
    "Kentucky":       0.30,
    "Houston":        0.28,   # paint-heavy
    "UConn":          0.32,
    "Auburn":         0.38,
    "Michigan St":    0.29,
    "Marquette":      0.36,
    "Purdue":         0.27,   # post-heavy
    "Tennessee":      0.30,
    "Texas":          0.34,
    "Illinois":       0.33,
    "Baylor":         0.37,
    "Indiana":        0.38,
    "Ole Miss":       0.36,
    "Virginia":       0.31,
    "Miami FL":       0.39,
    "Nebraska":       0.40,   # right at threshold
    "DePaul":         0.43,   # over threshold
    "Bryant":         0.45,   # over threshold
    "Alabama St":     0.41,
    "Texas Southern": 0.42,
    "Creighton":      0.44,   # over threshold
}

# Adjusted tempo (possessions per 40 min) — mirrors efficiency_feed data
_NCAAB_TEMPO: dict[str, float] = {
    "Gonzaga":        72.1,
    "Duke":           70.2,
    "Kansas":         68.9,
    "Kentucky":       67.4,
    "Houston":        64.1,
    "UConn":          65.8,
    "Auburn":         71.3,
    "Michigan St":    66.5,
    "Marquette":      69.8,
    "Purdue":         63.2,
    "Tennessee":      64.7,
    "Texas":          65.3,
    "Illinois":       67.1,
    "Baylor":         66.8,
    "Indiana":        68.2,
    "Ole Miss":       65.9,
    "Virginia":       58.1,   # slowest in dataset
    "Miami FL":       66.3,
    "Nebraska":       67.4,
    "DePaul":         69.1,
    "Bryant":         70.8,
    "Alabama St":     66.7,
    "Texas Southern": 68.9,
    "Creighton":      68.4,
}

_DEFAULT_THREE_POINT_RELIANCE = 0.33   # NCAA average
_DEFAULT_TEMPO = 67.0


def get_ncaab_three_point_reliance(team: str) -> tuple[float, bool]:
    """Return (three_point_reliance, is_live) for an NCAAB team."""
    val = _NCAAB_THREE_POINT_RELIANCE.get(team, _DEFAULT_THREE_POINT_RELIANCE)
    is_live = team in _NCAAB_THREE_POINT_RELIANCE
    return val, is_live


def get_ncaab_tempo(team: str) -> tuple[float, bool]:
    """Return (tempo, is_live) for an NCAAB team."""
    val = _NCAAB_TEMPO.get(team, _DEFAULT_TEMPO)
    is_live = team in _NCAAB_TEMPO
    return val, is_live


def get_ncaab_kill_inputs(
    bet_team: str,
    opp_team: str,
    is_away: bool,
    conference_tournament: bool = False,
    market_type: str = "spread",
) -> dict:
    """Build full input dict for ncaab_kill_switch()."""
    tpr, tpr_live = get_ncaab_three_point_reliance(bet_team)
    bet_tempo, bt_live = get_ncaab_tempo(bet_team)
    opp_tempo, ot_live = get_ncaab_tempo(opp_team)
    tempo_diff = abs(bet_tempo - opp_tempo)

    return {
        "three_point_reliance": tpr,
        "is_away": is_away,
        "tempo_diff": tempo_diff,
        "conference_tournament": conference_tournament,
        "market_type": market_type,
        "data_live": tpr_live and bt_live and ot_live,
    }


# ---------------------------------------------------------------------------
# Soccer stubs
# ---------------------------------------------------------------------------

# Market drift is computed at runtime from line open vs current.
# Falls back to 0.0 (no drift detected) when no open line is available.
_DEFAULT_MARKET_DRIFT = 0.0


def get_soccer_kill_inputs(
    open_price: Optional[float],
    current_price: float,
    dead_rubber: bool = False,
    key_creator_out: bool = False,
    market_type: str = "moneyline",
) -> dict:
    """
    Build full input dict for soccer_kill_switch().

    market_drift_pct is computed from open vs current implied probability
    when open_price is available. Falls back to 0.0 when not.

    Args:
        open_price:       American odds at line open. None if unavailable.
        current_price:    Current American odds.
        dead_rubber:      Game is meaningless (both teams eliminated, etc).
        key_creator_out:  Primary attacking player confirmed absent.
        market_type:      Market being evaluated.
    """
    if open_price is not None and open_price != 0 and current_price != 0:
        def _implied(american: float) -> float:
            if american >= 0:
                return 100 / (american + 100)
            return abs(american) / (abs(american) + 100)

        open_impl = _implied(open_price)
        curr_impl = _implied(current_price)
        drift = abs(curr_impl - open_impl)
        data_live = True
    else:
        drift = _DEFAULT_MARKET_DRIFT
        data_live = False

    return {
        "market_drift_pct": drift,
        "dead_rubber": dead_rubber,
        "key_creator_out": key_creator_out,
        "market_type": market_type,
        "data_live": data_live,
    }
