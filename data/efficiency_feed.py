"""
efficiency_feed.py — TITANIUM V36.1
=====================================
KenPom/Barttorvik mock data layer for NCAAB efficiency gaps.
No live scraping. Static snapshot calibrated to ~2024-25 season.

Promoted from R&D (titanium-experimental/core/data/efficiency_feed.py) — Session 5.
Fix applied: added "Texas Southern Tigers" alias before promotion (partial-match false positive).

Provides:
    get_efficiency_gap(home_team, away_team) -> float
        Returns a 0-20 scaled score representing the strength differential
        between two teams based on Adjusted Efficiency Margin (AdjEM).

    get_team_data(team_name) -> dict | None
        Returns raw efficiency data for a single team.

    list_teams() -> list[str]
        Returns all team names in the dataset.

    build_efficiency_data(games) -> dict[str, float]
        Maps event_id → efficiency_gap for use as rank_bets(efficiency_data=...).

Scaling:
    AdjEM differential is computed as:
        home_adj_em - away_adj_em
    Then clamped to [-30, +30] and scaled to [0, 20]:
        gap = (differential + 30) / 60 * 20
    A gap of 10.0 = teams are evenly matched (0 differential).
    Gap > 10 = home team has efficiency advantage.
    Gap < 10 = away team has efficiency advantage.

Teams included (~25 programs spanning power-5, mid-major, and rebuild levels):
    Elite: Duke, Kansas, Kentucky, Houston, UConn, Auburn
    Strong: Michigan St, Marquette, Purdue, Tennessee, Texas, Gonzaga, Creighton
    Mid: Illinois, Baylor, Miami FL, Indiana, Ole Miss, Virginia
    Lower: Nebraska, DePaul
    Rebuild: Bryant, Alabama St, Texas Southern

DO NOT add API calls, Streamlit calls, or betting math to this file.
"""

from typing import Optional


# ---------------------------------------------------------------------------
# Static efficiency data — AdjEM snapshot (~2024-25 season)
# Values are synthetic but calibrated to realistic KenPom ranges.
# AdjO: Points scored per 100 possessions (adjusted)
# AdjD: Points allowed per 100 possessions (adjusted) — lower is better
# AdjEM = AdjO - AdjD  (higher = better team)
# Tempo: Adjusted possessions per 40 minutes
# ---------------------------------------------------------------------------

_TEAM_DATA: dict[str, dict] = {
    # --- Elite tier (AdjEM 25-35) ---
    "Duke": {
        "adj_o": 121.4, "adj_d": 88.6,  "adj_em": 32.8, "tempo": 70.2,
    },
    "Kansas": {
        "adj_o": 119.8, "adj_d": 90.1,  "adj_em": 29.7, "tempo": 68.9,
    },
    "Kentucky": {
        "adj_o": 118.5, "adj_d": 91.3,  "adj_em": 27.2, "tempo": 67.4,
    },
    "Houston": {
        "adj_o": 116.2, "adj_d": 89.8,  "adj_em": 26.4, "tempo": 64.1,
    },
    "UConn": {
        "adj_o": 117.7, "adj_d": 91.0,  "adj_em": 26.7, "tempo": 65.8,
    },
    "Auburn": {
        "adj_o": 118.1, "adj_d": 92.4,  "adj_em": 25.7, "tempo": 71.3,
    },

    # --- Strong tier (AdjEM 15-25) ---
    "Michigan St": {
        "adj_o": 115.3, "adj_d": 95.1,  "adj_em": 20.2, "tempo": 66.5,
    },
    "Marquette": {
        "adj_o": 116.8, "adj_d": 97.4,  "adj_em": 19.4, "tempo": 69.8,
    },
    "Purdue": {
        "adj_o": 117.2, "adj_d": 98.3,  "adj_em": 18.9, "tempo": 63.2,
    },
    "Tennessee": {
        "adj_o": 114.1, "adj_d": 95.7,  "adj_em": 18.4, "tempo": 64.7,
    },
    "Texas": {
        "adj_o": 113.9, "adj_d": 96.2,  "adj_em": 17.7, "tempo": 65.3,
    },
    "Gonzaga": {
        "adj_o": 118.4, "adj_d": 101.2, "adj_em": 17.2, "tempo": 72.1,
    },
    "Creighton": {
        "adj_o": 115.7, "adj_d": 99.8,  "adj_em": 15.9, "tempo": 68.4,
    },

    # --- Mid tier (AdjEM 5-15) ---
    "Illinois": {
        "adj_o": 112.3, "adj_d": 100.1, "adj_em": 12.2, "tempo": 67.1,
    },
    "Baylor": {
        "adj_o": 111.8, "adj_d": 100.7, "adj_em": 11.1, "tempo": 66.8,
    },
    "Indiana": {
        "adj_o": 110.4, "adj_d": 101.9, "adj_em": 8.5,  "tempo": 68.2,
    },
    "Ole Miss": {
        "adj_o": 109.7, "adj_d": 102.8, "adj_em": 6.9,  "tempo": 65.9,
    },
    "Virginia": {
        "adj_o": 106.8, "adj_d": 100.5, "adj_em": 6.3,  "tempo": 58.1,
    },
    "Miami FL": {
        "adj_o": 108.2, "adj_d": 103.1, "adj_em": 5.1,  "tempo": 66.3,
    },

    # --- Lower tier (AdjEM -5 to 5) ---
    "Nebraska": {
        "adj_o": 106.1, "adj_d": 104.8, "adj_em": 1.3,  "tempo": 67.4,
    },
    "DePaul": {
        "adj_o": 103.4, "adj_d": 106.2, "adj_em": -2.8, "tempo": 69.1,
    },

    # --- Rebuild / low-major tier (AdjEM < -10) ---
    "Bryant": {
        "adj_o": 101.2, "adj_d": 110.4, "adj_em": -9.2, "tempo": 70.8,
    },
    "Alabama St": {
        "adj_o": 98.7,  "adj_d": 113.1, "adj_em": -14.4, "tempo": 66.7,
    },
    "Texas Southern": {
        "adj_o": 97.3,  "adj_d": 114.8, "adj_em": -17.5, "tempo": 68.9,
    },
}

# Aliases for common name variations from Odds API
# (partial match fallback is also tried after these)
_ALIASES: dict[str, str] = {
    "Michigan State":           "Michigan St",
    "UConn Huskies":            "UConn",
    "Connecticut":              "UConn",
    "Duke Blue Devils":         "Duke",
    "Kansas Jayhawks":          "Kansas",
    "Kentucky Wildcats":        "Kentucky",
    "Houston Cougars":          "Houston",
    "Auburn Tigers":            "Auburn",
    "Marquette Golden Eagles":  "Marquette",
    "Purdue Boilermakers":      "Purdue",
    "Tennessee Volunteers":     "Tennessee",
    "Texas Longhorns":          "Texas",
    "Gonzaga Bulldogs":         "Gonzaga",
    "Illinois Fighting Illini": "Illinois",
    "Baylor Bears":             "Baylor",
    "Indiana Hoosiers":         "Indiana",
    "Virginia Cavaliers":       "Virginia",
    "Nebraska Cornhuskers":     "Nebraska",
    "Creighton Bluejays":       "Creighton",
    "Ole Miss Rebels":          "Ole Miss",
    "Texas Southern Tigers":    "Texas Southern",   # explicit alias — prevents Texas partial match
    "Miami":                    "Miami FL",
    "Miami (FL)":               "Miami FL",
}

# Scaling constants
_EM_CLAMP = 30.0      # differential clamped to [-30, +30]
_SCALE_MAX = 20.0     # output range max
_NEUTRAL_GAP = 10.0   # gap returned when both teams are equal (0 differential)
_DEFAULT_GAP = 8.0    # returned when either team is unknown (matches rank_bets default)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_name(team: str) -> Optional[str]:
    """
    Resolve a team name to a canonical key in _TEAM_DATA.

    Tries in order:
    1. Exact match
    2. Alias lookup
    3. Case-insensitive exact match
    4. Partial match (team name contains or is contained in a known key)

    Returns None if no match found.
    """
    if team in _TEAM_DATA:
        return team

    if team in _ALIASES:
        canonical = _ALIASES[team]
        if canonical in _TEAM_DATA:
            return canonical

    lower = team.lower()
    for key in _TEAM_DATA:
        if key.lower() == lower:
            return key

    # Partial match — handles residual variants not covered by aliases
    # NOTE: insertion order of _TEAM_DATA is load-bearing here.
    # Teams with short names that are substrings of longer names (e.g. "Texas"
    # vs "Texas Southern") MUST have explicit aliases above to avoid false matches.
    for key in _TEAM_DATA:
        if key.lower() in lower or lower in key.lower():
            return key

    return None


def _em_to_gap(differential: float) -> float:
    """
    Convert raw AdjEM differential to 0-20 scaled gap.

    differential > 0: home team better → gap > 10
    differential = 0: even match → gap = 10
    differential < 0: away team better → gap < 10
    """
    clamped = max(-_EM_CLAMP, min(_EM_CLAMP, differential))
    return (clamped + _EM_CLAMP) / (2 * _EM_CLAMP) * _SCALE_MAX


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_efficiency_gap(home_team: str, away_team: str) -> float:
    """
    Return a 0-20 scaled efficiency gap between two NCAAB teams.

    A score of 10.0 means teams are evenly matched.
    Score > 10: home team has an efficiency advantage.
    Score < 10: away team has an efficiency advantage.

    Falls back to _DEFAULT_GAP (8.0) if either team is not in the dataset.
    This matches the default moderate gap used in rank_bets() so the fallback
    is neutral rather than extreme.

    Args:
        home_team: Home team name (partial match attempted on unknown names).
        away_team: Away team name (partial match attempted on unknown names).

    Returns:
        Float in [0, 20].
    """
    home_key = _resolve_name(home_team)
    away_key = _resolve_name(away_team)

    if home_key is None or away_key is None:
        return _DEFAULT_GAP

    home_em = _TEAM_DATA[home_key]["adj_em"]
    away_em = _TEAM_DATA[away_key]["adj_em"]

    return _em_to_gap(home_em - away_em)


def get_team_data(team_name: str) -> Optional[dict]:
    """
    Return raw efficiency data for a single team.

    Returns:
        Dict with keys: adj_o, adj_d, adj_em, tempo — or None if not found.
    """
    key = _resolve_name(team_name)
    if key is None:
        return None
    return dict(_TEAM_DATA[key])


def list_teams() -> list[str]:
    """Return all canonical team names in the dataset."""
    return sorted(_TEAM_DATA.keys())


# ---------------------------------------------------------------------------
# Batch helper — build efficiency_data dict for rank_bets()
# ---------------------------------------------------------------------------

def build_efficiency_data(games: list[dict]) -> dict[str, float]:
    """
    Build the efficiency_data dict expected by rank_bets() from a list of game dicts.

    Accepts both raw Odds API game dicts (key="id") and parsed dicts (key="event_id").
    The "event_id" key takes priority if both are present.

    Args:
        games: List of game dicts with home_team, away_team, and id or event_id.

    Returns:
        Dict mapping event_id → efficiency_gap float.
        Games with unknown teams get _DEFAULT_GAP (8.0).
        Games with no event_id are silently skipped.
    """
    result = {}
    for game in games:
        event_id = game.get("event_id") or game.get("id")
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        if event_id:
            result[event_id] = get_efficiency_gap(home, away)
    return result
