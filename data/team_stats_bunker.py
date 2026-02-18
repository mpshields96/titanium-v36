"""
data/team_stats_bunker.py — TITANIUM V36.1
============================================
Static fallback stats used when live scraping fails.
Loaded automatically by edge_calculator.py if scraping returns empty data.

Contents:
- NBA team NetRtg and Pace (updated manually each week)
- NFL team EPA/play (updated manually each week)

IMPORTANT: These are fallback values only. Live data always takes priority.
Update these values weekly if live scraping remains broken.

Last manual update: February 2026
"""

# ---------------------------------------------------------------------------
# NBA — Net Rating and Pace
# Format: "TEAM_ABBR": {"net_rtg": float, "pace": float}
# Source: NBA.com/stats Hollinger Team Statistics
# ---------------------------------------------------------------------------
NBA_TEAM_STATS: dict = {
    # TODO: Populate with current season values before first live use
    # Example format:
    # "BOS": {"net_rtg": 8.4, "pace": 99.2},
    # "GSW": {"net_rtg": 3.1, "pace": 101.8},
}

# ---------------------------------------------------------------------------
# NFL — EPA per Play (offense and defense)
# Format: "TEAM_ABBR": {"off_epa": float, "def_epa": float}
# Source: nflfastR / ESPN Stats
# ---------------------------------------------------------------------------
NFL_TEAM_STATS: dict = {
    # TODO: Populate with current season values before first live use
    # Example format:
    # "KC":  {"off_epa": 0.18, "def_epa": -0.12},
    # "NE":  {"off_epa": -0.04, "def_epa": 0.03},
}
