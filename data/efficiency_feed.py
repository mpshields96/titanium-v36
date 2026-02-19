"""
efficiency_feed.py — TITANIUM V36.1
=====================================
Mock efficiency data layer for NBA (NetRtg), NCAAB (KenPom/Barttorvik), and NHL (GF60-GA60).
No live scraping. Static snapshot calibrated to ~2024-25 season.

Promoted from R&D (titanium-experimental/core/data/efficiency_feed.py) — Session 5.
Updated Session 9: all 30 NBA franchises added. league field on every entry.
Updated Session 10: NCAAB expanded 24 → 80 teams (ACC, Big 12, Big Ten, SEC, Big East, WCC/MWC/A-10).
Fix applied: added "Texas Southern Tigers" alias before Session 5 promotion.
Updated Session 17: all 32 NHL franchises added (GF60-GA60 × 10 AdjEM proxy).

Provides:
    get_efficiency_gap(home_team, away_team) -> float
        Returns a 0-20 scaled score representing the strength differential
        between two teams. Works for NBA, NCAAB, and NHL — all use the same
        adj_em field and the same scaling math.

    get_team_data(team_name) -> dict | None
        Returns raw efficiency data for a single team.

    list_teams(league=None) -> list[str]
        Returns all canonical team names. Pass league="NBA", "NCAAB", or "NHL" to filter.

    build_efficiency_data(games) -> dict[str, float]
        Maps event_id → efficiency_gap for use as rank_bets(efficiency_data=...).

Scaling (identical for NBA, NCAAB, and NHL):
    AdjEM differential = home_adj_em - away_adj_em
    Clamped to [-30, +30], scaled to [0, 20]:
        gap = (differential + 30) / 60 * 20
    Gap 10.0 = evenly matched. >10 = home advantage. <10 = away advantage.

NBA data source: Net Rating (NetRtg) used as AdjEM equivalent.
    NetRtg range: elite ~+12 to +8, average ~0, poor ~-8 to -12.
    Recalibrated to AdjEM scale (*2.2 multiplier) so NBA and NCAAB gaps
    are comparable within the 0-20 output range.

NCAAB data source: KenPom/Barttorvik AdjEM.
    Range: elite ~+30, average ~0, poor ~-15.

NHL data source: GF60-GA60 goal differential × 10.
    GF60-GA60 range: elite ~+1.2 to +1.5, average ~0, poor ~-1.0 to -1.5.
    Multiplied by 10 → adj_em range ±12–15 — fits within ±30 clamp, stays comparable.
    tempo: 0.0 — not meaningful for hockey (field required by schema).

Teams included:
    NBA:   All 30 franchises (~2024-25 NetRtg calibrated)
    NCAAB: 80 programs — ACC, Big 12, Big Ten, SEC, Big East, WCC/MWC/A-10, low-major
    NHL:   All 32 franchises (~2024-25 GF60-GA60 calibrated)

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

    # =========================================================================
    # NBA — NetRtg converted to AdjEM-equivalent scale (* 2.2 multiplier)
    # NetRtg snapshot ~2024-25. adj_em = net_rtg * 2.2 (keeps 0-20 gap meaningful)
    # Tempo: possessions per 48 min (NBA), normalised to per-40 equivalent
    # =========================================================================

    # --- NBA Elite tier (adj_em 18-28) ---
    "Oklahoma City Thunder": {
        "adj_o": 120.1, "adj_d": 107.4, "adj_em": 28.0, "tempo": 98.2, "league": "NBA",
    },
    "Boston Celtics": {
        "adj_o": 122.3, "adj_d": 109.8, "adj_em": 27.5, "tempo": 97.1, "league": "NBA",
    },
    "Cleveland Cavaliers": {
        "adj_o": 118.4, "adj_d": 107.2, "adj_em": 24.6, "tempo": 95.8, "league": "NBA",
    },
    "Minnesota Timberwolves": {
        "adj_o": 116.9, "adj_d": 107.1, "adj_em": 21.6, "tempo": 96.4, "league": "NBA",
    },
    "Denver Nuggets": {
        "adj_o": 118.7, "adj_d": 110.1, "adj_em": 19.0, "tempo": 95.2, "league": "NBA",
    },
    "Houston Rockets": {
        "adj_o": 114.8, "adj_d": 108.4, "adj_em": 14.3, "tempo": 97.8, "league": "NBA",
    },

    # --- NBA Strong tier (adj_em 8-18) ---
    "Golden State Warriors": {
        "adj_o": 116.2, "adj_d": 109.8, "adj_em": 14.1, "tempo": 99.3, "league": "NBA",
    },
    "Los Angeles Lakers": {
        "adj_o": 115.9, "adj_d": 110.2, "adj_em": 12.5, "tempo": 96.7, "league": "NBA",
    },
    "Dallas Mavericks": {
        "adj_o": 118.1, "adj_d": 112.4, "adj_em": 12.5, "tempo": 96.1, "league": "NBA",
    },
    "Memphis Grizzlies": {
        "adj_o": 114.3, "adj_d": 109.1, "adj_em": 11.4, "tempo": 100.2, "league": "NBA",
    },
    "Indiana Pacers": {
        "adj_o": 119.6, "adj_d": 114.8, "adj_em": 10.6, "tempo": 103.4, "league": "NBA",
    },
    "Milwaukee Bucks": {
        "adj_o": 116.8, "adj_d": 112.7, "adj_em": 9.0,  "tempo": 97.6, "league": "NBA",
    },
    "New York Knicks": {
        "adj_o": 114.4, "adj_d": 110.8, "adj_em": 7.9,  "tempo": 94.3, "league": "NBA",
    },
    "Los Angeles Clippers": {
        "adj_o": 113.9, "adj_d": 110.6, "adj_em": 7.3,  "tempo": 95.9, "league": "NBA",
    },
    "Sacramento Kings": {
        "adj_o": 117.2, "adj_d": 114.3, "adj_em": 6.6,  "tempo": 101.1, "league": "NBA",
    },
    "San Antonio Spurs": {
        "adj_o": 114.1, "adj_d": 111.6, "adj_em": 5.5,  "tempo": 98.4, "league": "NBA",
    },

    # --- NBA Mid tier (adj_em -2 to 8) ---
    "Miami Heat": {
        "adj_o": 112.3, "adj_d": 110.4, "adj_em": 4.2,  "tempo": 95.1, "league": "NBA",
    },
    "Philadelphia 76ers": {
        "adj_o": 113.7, "adj_d": 112.1, "adj_em": 3.5,  "tempo": 96.3, "league": "NBA",
    },
    "Phoenix Suns": {
        "adj_o": 113.4, "adj_d": 112.2, "adj_em": 2.6,  "tempo": 100.7, "league": "NBA",
    },
    "New Orleans Pelicans": {
        "adj_o": 111.8, "adj_d": 111.1, "adj_em": 1.5,  "tempo": 97.2, "league": "NBA",
    },
    "Orlando Magic": {
        "adj_o": 110.9, "adj_d": 110.4, "adj_em": 1.1,  "tempo": 95.6, "league": "NBA",
    },
    "Chicago Bulls": {
        "adj_o": 111.2, "adj_d": 111.4, "adj_em": -0.4, "tempo": 97.3, "league": "NBA",
    },
    "Atlanta Hawks": {
        "adj_o": 114.3, "adj_d": 115.2, "adj_em": -2.0, "tempo": 99.8, "league": "NBA",
    },
    "Toronto Raptors": {
        "adj_o": 110.4, "adj_d": 112.7, "adj_em": -5.1, "tempo": 96.1, "league": "NBA",
    },

    # --- NBA Lower tier (adj_em < -5) ---
    "Brooklyn Nets": {
        "adj_o": 109.8, "adj_d": 116.3, "adj_em": -14.3, "tempo": 97.4, "league": "NBA",
    },
    "Detroit Pistons": {
        "adj_o": 108.6, "adj_d": 114.8, "adj_em": -13.6, "tempo": 98.2, "league": "NBA",
    },
    "Utah Jazz": {
        "adj_o": 108.2, "adj_d": 114.1, "adj_em": -13.0, "tempo": 98.7, "league": "NBA",
    },
    "Portland Trail Blazers": {
        "adj_o": 108.9, "adj_d": 115.4, "adj_em": -14.3, "tempo": 99.6, "league": "NBA",
    },
    "Charlotte Hornets": {
        "adj_o": 109.1, "adj_d": 115.9, "adj_em": -14.9, "tempo": 100.1, "league": "NBA",
    },
    "Washington Wizards": {
        "adj_o": 107.4, "adj_d": 117.2, "adj_em": -21.6, "tempo": 98.9, "league": "NBA",
    },

    # =========================================================================
    # NCAAB — KenPom/Barttorvik AdjEM (~2024-25)
    # Organized by conference for maintainability.
    # AdjEM ranges: elite 25-35, strong 15-25, mid 5-15, lower -5 to 5, rebuild < -5
    # =========================================================================

    # ----- ACC -----
    "Duke": {
        "adj_o": 121.4, "adj_d": 88.6,  "adj_em": 32.8, "tempo": 70.2, "league": "NCAAB",
    },
    "UConn": {
        "adj_o": 117.7, "adj_d": 91.0,  "adj_em": 26.7, "tempo": 65.8, "league": "NCAAB",
    },
    "Creighton": {
        "adj_o": 115.7, "adj_d": 99.8,  "adj_em": 15.9, "tempo": 68.4, "league": "NCAAB",
    },
    "Marquette": {
        "adj_o": 116.8, "adj_d": 97.4,  "adj_em": 19.4, "tempo": 69.8, "league": "NCAAB",
    },
    "Virginia": {
        "adj_o": 106.8, "adj_d": 100.5, "adj_em": 6.3,  "tempo": 58.1, "league": "NCAAB",
    },
    "Miami FL": {
        "adj_o": 108.2, "adj_d": 103.1, "adj_em": 5.1,  "tempo": 66.3, "league": "NCAAB",
    },
    "NC State": {
        "adj_o": 113.1, "adj_d": 100.8, "adj_em": 12.3, "tempo": 68.7, "league": "NCAAB",
    },
    "Pitt": {
        "adj_o": 112.4, "adj_d": 101.6, "adj_em": 10.8, "tempo": 67.3, "league": "NCAAB",
    },
    "Notre Dame": {
        "adj_o": 110.9, "adj_d": 102.4, "adj_em": 8.5,  "tempo": 65.8, "league": "NCAAB",
    },
    "Syracuse": {
        "adj_o": 109.3, "adj_d": 103.7, "adj_em": 5.6,  "tempo": 64.2, "league": "NCAAB",
    },
    "Wake Forest": {
        "adj_o": 108.6, "adj_d": 104.1, "adj_em": 4.5,  "tempo": 67.9, "league": "NCAAB",
    },
    "Georgia Tech": {
        "adj_o": 107.8, "adj_d": 105.3, "adj_em": 2.5,  "tempo": 69.4, "league": "NCAAB",
    },
    "Louisville": {
        "adj_o": 107.2, "adj_d": 105.8, "adj_em": 1.4,  "tempo": 66.1, "league": "NCAAB",
    },
    "Clemson": {
        "adj_o": 108.1, "adj_d": 107.2, "adj_em": 0.9,  "tempo": 65.6, "league": "NCAAB",
    },
    "Boston College": {
        "adj_o": 104.3, "adj_d": 107.9, "adj_em": -3.6, "tempo": 68.3, "league": "NCAAB",
    },
    "Stanford": {
        "adj_o": 105.8, "adj_d": 108.4, "adj_em": -2.6, "tempo": 66.9, "league": "NCAAB",
    },
    "California": {
        "adj_o": 103.1, "adj_d": 109.7, "adj_em": -6.6, "tempo": 67.2, "league": "NCAAB",
    },

    # ----- Big 12 -----
    "Kansas": {
        "adj_o": 119.8, "adj_d": 90.1,  "adj_em": 29.7, "tempo": 68.9, "league": "NCAAB",
    },
    "Houston": {
        "adj_o": 116.2, "adj_d": 89.8,  "adj_em": 26.4, "tempo": 64.1, "league": "NCAAB",
    },
    "Baylor": {
        "adj_o": 111.8, "adj_d": 100.7, "adj_em": 11.1, "tempo": 66.8, "league": "NCAAB",
    },
    "Texas": {
        "adj_o": 113.9, "adj_d": 96.2,  "adj_em": 17.7, "tempo": 65.3, "league": "NCAAB",
    },
    "Texas Tech": {
        "adj_o": 112.6, "adj_d": 98.3,  "adj_em": 14.3, "tempo": 63.8, "league": "NCAAB",
    },
    "Iowa St": {
        "adj_o": 113.4, "adj_d": 99.7,  "adj_em": 13.7, "tempo": 66.2, "league": "NCAAB",
    },
    "Kansas St": {
        "adj_o": 111.2, "adj_d": 100.9, "adj_em": 10.3, "tempo": 65.7, "league": "NCAAB",
    },
    "BYU": {
        "adj_o": 112.1, "adj_d": 102.4, "adj_em": 9.7,  "tempo": 67.4, "league": "NCAAB",
    },
    "Oklahoma St": {
        "adj_o": 110.3, "adj_d": 102.8, "adj_em": 7.5,  "tempo": 66.9, "league": "NCAAB",
    },
    "TCU": {
        "adj_o": 109.7, "adj_d": 103.6, "adj_em": 6.1,  "tempo": 65.4, "league": "NCAAB",
    },
    "UCF": {
        "adj_o": 108.9, "adj_d": 104.2, "adj_em": 4.7,  "tempo": 68.1, "league": "NCAAB",
    },
    "West Virginia": {
        "adj_o": 108.1, "adj_d": 104.9, "adj_em": 3.2,  "tempo": 64.8, "league": "NCAAB",
    },
    "Cincinnati": {
        "adj_o": 107.4, "adj_d": 105.7, "adj_em": 1.7,  "tempo": 67.3, "league": "NCAAB",
    },

    # ----- Big Ten -----
    "Purdue": {
        "adj_o": 117.2, "adj_d": 98.3,  "adj_em": 18.9, "tempo": 63.2, "league": "NCAAB",
    },
    "Michigan St": {
        "adj_o": 115.3, "adj_d": 95.1,  "adj_em": 20.2, "tempo": 66.5, "league": "NCAAB",
    },
    "Illinois": {
        "adj_o": 112.3, "adj_d": 100.1, "adj_em": 12.2, "tempo": 67.1, "league": "NCAAB",
    },
    "Indiana": {
        "adj_o": 110.4, "adj_d": 101.9, "adj_em": 8.5,  "tempo": 68.2, "league": "NCAAB",
    },
    "Nebraska": {
        "adj_o": 106.1, "adj_d": 104.8, "adj_em": 1.3,  "tempo": 67.4, "league": "NCAAB",
    },
    "Wisconsin": {
        "adj_o": 110.8, "adj_d": 100.3, "adj_em": 10.5, "tempo": 61.4, "league": "NCAAB",
    },
    "Michigan": {
        "adj_o": 109.6, "adj_d": 101.7, "adj_em": 7.9,  "tempo": 64.9, "league": "NCAAB",
    },
    "Ohio St": {
        "adj_o": 111.4, "adj_d": 103.8, "adj_em": 7.6,  "tempo": 66.3, "league": "NCAAB",
    },
    "Maryland": {
        "adj_o": 110.1, "adj_d": 103.2, "adj_em": 6.9,  "tempo": 68.7, "league": "NCAAB",
    },
    "Iowa": {
        "adj_o": 113.2, "adj_d": 107.1, "adj_em": 6.1,  "tempo": 69.3, "league": "NCAAB",
    },
    "Minnesota": {
        "adj_o": 107.9, "adj_d": 105.8, "adj_em": 2.1,  "tempo": 66.8, "league": "NCAAB",
    },
    "Penn St": {
        "adj_o": 107.3, "adj_d": 106.4, "adj_em": 0.9,  "tempo": 65.2, "league": "NCAAB",
    },
    "Northwestern": {
        "adj_o": 105.8, "adj_d": 107.3, "adj_em": -1.5, "tempo": 63.7, "league": "NCAAB",
    },
    "Rutgers": {
        "adj_o": 104.6, "adj_d": 107.1, "adj_em": -2.5, "tempo": 64.4, "league": "NCAAB",
    },

    # ----- SEC -----
    "Auburn": {
        "adj_o": 118.1, "adj_d": 92.4,  "adj_em": 25.7, "tempo": 71.3, "league": "NCAAB",
    },
    "Kentucky": {
        "adj_o": 118.5, "adj_d": 91.3,  "adj_em": 27.2, "tempo": 67.4, "league": "NCAAB",
    },
    "Tennessee": {
        "adj_o": 114.1, "adj_d": 95.7,  "adj_em": 18.4, "tempo": 64.7, "league": "NCAAB",
    },
    "Ole Miss": {
        "adj_o": 109.7, "adj_d": 102.8, "adj_em": 6.9,  "tempo": 65.9, "league": "NCAAB",
    },
    "Alabama": {
        "adj_o": 116.3, "adj_d": 97.4,  "adj_em": 18.9, "tempo": 72.4, "league": "NCAAB",
    },
    "Florida": {
        "adj_o": 112.8, "adj_d": 99.6,  "adj_em": 13.2, "tempo": 68.1, "league": "NCAAB",
    },
    "Arkansas": {
        "adj_o": 111.4, "adj_d": 100.3, "adj_em": 11.1, "tempo": 69.8, "league": "NCAAB",
    },
    "Missouri": {
        "adj_o": 110.7, "adj_d": 101.2, "adj_em": 9.5,  "tempo": 66.4, "league": "NCAAB",
    },
    "Texas A&M": {
        "adj_o": 109.8, "adj_d": 102.1, "adj_em": 7.7,  "tempo": 64.3, "league": "NCAAB",
    },
    "LSU": {
        "adj_o": 110.3, "adj_d": 103.4, "adj_em": 6.9,  "tempo": 70.6, "league": "NCAAB",
    },
    "Mississippi St": {
        "adj_o": 108.4, "adj_d": 104.6, "adj_em": 3.8,  "tempo": 67.2, "league": "NCAAB",
    },
    "Georgia": {
        "adj_o": 107.6, "adj_d": 105.3, "adj_em": 2.3,  "tempo": 66.9, "league": "NCAAB",
    },
    "South Carolina": {
        "adj_o": 106.9, "adj_d": 106.1, "adj_em": 0.8,  "tempo": 65.8, "league": "NCAAB",
    },
    "Vanderbilt": {
        "adj_o": 105.3, "adj_d": 108.7, "adj_em": -3.4, "tempo": 67.1, "league": "NCAAB",
    },

    # ----- Big East -----
    "DePaul": {
        "adj_o": 103.4, "adj_d": 106.2, "adj_em": -2.8, "tempo": 69.1, "league": "NCAAB",
    },
    "St. John's": {
        "adj_o": 114.2, "adj_d": 98.6,  "adj_em": 15.6, "tempo": 70.3, "league": "NCAAB",
    },
    "Providence": {
        "adj_o": 110.1, "adj_d": 102.8, "adj_em": 7.3,  "tempo": 64.6, "league": "NCAAB",
    },
    "Xavier": {
        "adj_o": 109.4, "adj_d": 103.7, "adj_em": 5.7,  "tempo": 67.8, "league": "NCAAB",
    },
    "Villanova": {
        "adj_o": 108.8, "adj_d": 104.4, "adj_em": 4.4,  "tempo": 63.1, "league": "NCAAB",
    },
    "Georgetown": {
        "adj_o": 102.1, "adj_d": 109.8, "adj_em": -7.7, "tempo": 68.4, "league": "NCAAB",
    },
    "Butler": {
        "adj_o": 105.4, "adj_d": 107.6, "adj_em": -2.2, "tempo": 65.9, "league": "NCAAB",
    },
    "Seton Hall": {
        "adj_o": 107.1, "adj_d": 105.9, "adj_em": 1.2,  "tempo": 66.7, "league": "NCAAB",
    },

    # ----- WCC / Mountain West / A-10 (top mid-majors) -----
    "Gonzaga": {
        "adj_o": 118.4, "adj_d": 101.2, "adj_em": 17.2, "tempo": 72.1, "league": "NCAAB",
    },
    "Saint Mary's": {
        "adj_o": 112.1, "adj_d": 101.4, "adj_em": 10.7, "tempo": 61.8, "league": "NCAAB",
    },
    "San Diego St": {
        "adj_o": 108.3, "adj_d": 99.7,  "adj_em": 8.6,  "tempo": 62.4, "league": "NCAAB",
    },
    "Utah St": {
        "adj_o": 111.7, "adj_d": 103.2, "adj_em": 8.5,  "tempo": 66.1, "league": "NCAAB",
    },
    "Dayton": {
        "adj_o": 113.2, "adj_d": 104.8, "adj_em": 8.4,  "tempo": 67.4, "league": "NCAAB",
    },
    "VCU": {
        "adj_o": 108.9, "adj_d": 102.1, "adj_em": 6.8,  "tempo": 68.9, "league": "NCAAB",
    },
    "UNLV": {
        "adj_o": 109.4, "adj_d": 103.7, "adj_em": 5.7,  "tempo": 69.2, "league": "NCAAB",
    },
    "New Mexico": {
        "adj_o": 109.1, "adj_d": 104.3, "adj_em": 4.8,  "tempo": 70.1, "league": "NCAAB",
    },
    "Drake": {
        "adj_o": 109.8, "adj_d": 105.6, "adj_em": 4.2,  "tempo": 64.7, "league": "NCAAB",
    },
    "Richmond": {
        "adj_o": 107.3, "adj_d": 105.4, "adj_em": 1.9,  "tempo": 65.3, "league": "NCAAB",
    },
    "Davidson": {
        "adj_o": 108.1, "adj_d": 106.4, "adj_em": 1.7,  "tempo": 68.6, "league": "NCAAB",
    },

    # ----- Low-major / rebuild -----
    "Bryant": {
        "adj_o": 101.2, "adj_d": 110.4, "adj_em": -9.2,  "tempo": 70.8, "league": "NCAAB",
    },
    "Alabama St": {
        "adj_o": 98.7,  "adj_d": 113.1, "adj_em": -14.4, "tempo": 66.7, "league": "NCAAB",
    },
    "Texas Southern": {
        "adj_o": 97.3,  "adj_d": 114.8, "adj_em": -17.5, "tempo": 68.9, "league": "NCAAB",
    },

    # =========================================================================
    # NHL — GF60-GA60 × 10 as AdjEM proxy (~2024-25 season)
    # GF60 = goals for per 60 min (5v5). GA60 = goals against per 60 min.
    # adj_em = (GF60 - GA60) × 10 — fits within ±30 clamp, stays comparable.
    # adj_o = GF60 × 10 (attack proxy). adj_d = GA60 × 10 (defence proxy, lower = better).
    # tempo: 0.0 — not meaningful for hockey; field required by schema.
    # =========================================================================

    # --- NHL Elite tier (adj_em 10-15) ---
    "Florida Panthers": {
        "adj_o": 28.4, "adj_d": 14.8, "adj_em": 13.6, "tempo": 0.0, "league": "NHL",
    },
    "Vancouver Canucks": {
        "adj_o": 27.1, "adj_d": 14.3, "adj_em": 12.8, "tempo": 0.0, "league": "NHL",
    },
    "Colorado Avalanche": {
        "adj_o": 29.3, "adj_d": 17.0, "adj_em": 12.3, "tempo": 0.0, "league": "NHL",
    },
    "Dallas Stars": {
        "adj_o": 27.8, "adj_d": 15.8, "adj_em": 12.0, "tempo": 0.0, "league": "NHL",
    },
    "New York Rangers": {
        "adj_o": 27.4, "adj_d": 15.7, "adj_em": 11.7, "tempo": 0.0, "league": "NHL",
    },
    "Winnipeg Jets": {
        "adj_o": 27.9, "adj_d": 16.5, "adj_em": 11.4, "tempo": 0.0, "league": "NHL",
    },
    "Boston Bruins": {
        "adj_o": 27.2, "adj_d": 16.3, "adj_em": 10.9, "tempo": 0.0, "league": "NHL",
    },
    "Carolina Hurricanes": {
        "adj_o": 26.8, "adj_d": 15.9, "adj_em": 10.9, "tempo": 0.0, "league": "NHL",
    },

    # --- NHL Strong tier (adj_em 4-10) ---
    "Edmonton Oilers": {
        "adj_o": 29.6, "adj_d": 20.4, "adj_em": 9.2,  "tempo": 0.0, "league": "NHL",
    },
    "Vegas Golden Knights": {
        "adj_o": 27.3, "adj_d": 18.4, "adj_em": 8.9,  "tempo": 0.0, "league": "NHL",
    },
    "New Jersey Devils": {
        "adj_o": 26.7, "adj_d": 18.1, "adj_em": 8.6,  "tempo": 0.0, "league": "NHL",
    },
    "Tampa Bay Lightning": {
        "adj_o": 27.1, "adj_d": 18.8, "adj_em": 8.3,  "tempo": 0.0, "league": "NHL",
    },
    "Nashville Predators": {
        "adj_o": 25.8, "adj_d": 18.1, "adj_em": 7.7,  "tempo": 0.0, "league": "NHL",
    },
    "Toronto Maple Leafs": {
        "adj_o": 28.2, "adj_d": 21.1, "adj_em": 7.1,  "tempo": 0.0, "league": "NHL",
    },
    "Minnesota Wild": {
        "adj_o": 25.9, "adj_d": 19.1, "adj_em": 6.8,  "tempo": 0.0, "league": "NHL",
    },
    "Ottawa Senators": {
        "adj_o": 26.4, "adj_d": 20.0, "adj_em": 6.4,  "tempo": 0.0, "league": "NHL",
    },
    "Los Angeles Kings": {
        "adj_o": 25.7, "adj_d": 19.5, "adj_em": 6.2,  "tempo": 0.0, "league": "NHL",
    },

    # --- NHL Mid tier (adj_em -2 to 4) ---
    "Pittsburgh Penguins": {
        "adj_o": 25.6, "adj_d": 21.8, "adj_em": 3.8,  "tempo": 0.0, "league": "NHL",
    },
    "Seattle Kraken": {
        "adj_o": 25.3, "adj_d": 21.6, "adj_em": 3.7,  "tempo": 0.0, "league": "NHL",
    },
    "New York Islanders": {
        "adj_o": 24.8, "adj_d": 21.3, "adj_em": 3.5,  "tempo": 0.0, "league": "NHL",
    },
    "Calgary Flames": {
        "adj_o": 25.1, "adj_d": 21.8, "adj_em": 3.3,  "tempo": 0.0, "league": "NHL",
    },
    "St. Louis Blues": {
        "adj_o": 25.4, "adj_d": 22.2, "adj_em": 3.2,  "tempo": 0.0, "league": "NHL",
    },
    "Detroit Red Wings": {
        "adj_o": 25.2, "adj_d": 22.4, "adj_em": 2.8,  "tempo": 0.0, "league": "NHL",
    },
    "Philadelphia Flyers": {
        "adj_o": 24.9, "adj_d": 22.4, "adj_em": 2.5,  "tempo": 0.0, "league": "NHL",
    },
    "Washington Capitals": {
        "adj_o": 26.1, "adj_d": 24.1, "adj_em": 2.0,  "tempo": 0.0, "league": "NHL",
    },
    "Buffalo Sabres": {
        "adj_o": 25.6, "adj_d": 24.0, "adj_em": 1.6,  "tempo": 0.0, "league": "NHL",
    },
    "Anaheim Ducks": {
        "adj_o": 24.3, "adj_d": 23.1, "adj_em": 1.2,  "tempo": 0.0, "league": "NHL",
    },
    "Montreal Canadiens": {
        "adj_o": 24.6, "adj_d": 23.5, "adj_em": 1.1,  "tempo": 0.0, "league": "NHL",
    },

    # --- NHL Lower tier (adj_em < -2) ---
    "Columbus Blue Jackets": {
        "adj_o": 23.8, "adj_d": 25.3, "adj_em": -1.5, "tempo": 0.0, "league": "NHL",
    },
    "Chicago Blackhawks": {
        "adj_o": 23.1, "adj_d": 26.2, "adj_em": -3.1, "tempo": 0.0, "league": "NHL",
    },
    "San Jose Sharks": {
        "adj_o": 22.4, "adj_d": 26.8, "adj_em": -4.4, "tempo": 0.0, "league": "NHL",
    },
    "Utah Hockey Club": {
        "adj_o": 24.7, "adj_d": 22.6, "adj_em": 2.1,  "tempo": 0.0, "league": "NHL",
    },
}

# Aliases for common name variations from Odds API
# (partial match fallback is also tried after these)
_ALIASES: dict[str, str] = {
    # --- NBA aliases (Odds API uses full city+nickname) ---
    "OKC Thunder":               "Oklahoma City Thunder",
    "OKC":                       "Oklahoma City Thunder",
    "Celtics":                   "Boston Celtics",
    "Cavs":                      "Cleveland Cavaliers",
    "Wolves":                    "Minnesota Timberwolves",
    "Nuggets":                   "Denver Nuggets",
    "Rockets":                   "Houston Rockets",
    "Warriors":                  "Golden State Warriors",
    "GSW":                       "Golden State Warriors",
    "Lakers":                    "Los Angeles Lakers",
    "LAL":                       "Los Angeles Lakers",
    "Mavs":                      "Dallas Mavericks",
    "Grizzlies":                 "Memphis Grizzlies",
    "Pacers":                    "Indiana Pacers",
    "Bucks":                     "Milwaukee Bucks",
    "Knicks":                    "New York Knicks",
    "Clippers":                  "Los Angeles Clippers",
    "LAC":                       "Los Angeles Clippers",
    "Kings":                     "Sacramento Kings",
    "Spurs":                     "San Antonio Spurs",
    "Heat":                      "Miami Heat",
    "Sixers":                    "Philadelphia 76ers",
    "76ers":                     "Philadelphia 76ers",
    "Suns":                      "Phoenix Suns",
    "Pelicans":                  "New Orleans Pelicans",
    "Magic":                     "Orlando Magic",
    "Bulls":                     "Chicago Bulls",
    "Hawks":                     "Atlanta Hawks",
    "Raptors":                   "Toronto Raptors",
    "Nets":                      "Brooklyn Nets",
    "Pistons":                   "Detroit Pistons",
    "Jazz":                      "Utah Jazz",
    "Blazers":                   "Portland Trail Blazers",
    "Trail Blazers":             "Portland Trail Blazers",
    "Hornets":                   "Charlotte Hornets",
    "Wizards":                   "Washington Wizards",

    # --- NCAAB aliases (full mascot names + common variants the Odds API may return) ---
    # ACC
    "Michigan State":            "Michigan St",
    "UConn Huskies":             "UConn",
    "Connecticut":               "UConn",
    "Duke Blue Devils":          "Duke",
    "Virginia Cavaliers":        "Virginia",
    "Miami Hurricanes":          "Miami FL",
    "Miami":                     "Miami FL",
    "Miami (FL)":                "Miami FL",
    "NC State Wolfpack":         "NC State",
    "North Carolina State":      "NC State",
    "Pittsburgh Panthers":       "Pitt",
    "Notre Dame Fighting Irish": "Notre Dame",
    "Syracuse Orange":           "Syracuse",
    "Wake Forest Demon Deacons": "Wake Forest",
    "Georgia Tech Yellow Jackets": "Georgia Tech",
    "Louisville Cardinals":      "Louisville",
    "Clemson Tigers":            "Clemson",
    "Boston College Eagles":     "Boston College",
    "Stanford Cardinal":         "Stanford",
    # Big 12
    "Kansas Jayhawks":           "Kansas",
    "Houston Cougars":           "Houston",
    "Baylor Bears":              "Baylor",
    "Texas Longhorns":           "Texas",
    "Texas Tech Red Raiders":    "Texas Tech",
    "Iowa State Cyclones":       "Iowa St",
    "Iowa State":                "Iowa St",
    "Kansas State Wildcats":     "Kansas St",
    "Kansas State":              "Kansas St",
    "BYU Cougars":               "BYU",
    "Oklahoma State Cowboys":    "Oklahoma St",
    "Oklahoma State":            "Oklahoma St",
    "TCU Horned Frogs":          "TCU",
    "UCF Knights":               "UCF",
    "West Virginia Mountaineers": "West Virginia",
    "Cincinnati Bearcats":       "Cincinnati",
    # Big Ten
    "Purdue Boilermakers":       "Purdue",
    "Michigan State Spartans":   "Michigan St",
    "Illinois Fighting Illini":  "Illinois",
    "Indiana Hoosiers":          "Indiana",
    "Nebraska Cornhuskers":      "Nebraska",
    "Wisconsin Badgers":         "Wisconsin",
    "Michigan Wolverines":       "Michigan",
    "Ohio State Buckeyes":       "Ohio St",
    "Ohio State":                "Ohio St",
    "Maryland Terrapins":        "Maryland",
    "Iowa Hawkeyes":             "Iowa",
    "Minnesota Golden Gophers":  "Minnesota",
    "Penn State Nittany Lions":  "Penn St",
    "Penn State":                "Penn St",
    "Northwestern Wildcats":     "Northwestern",
    "Rutgers Scarlet Knights":   "Rutgers",
    # SEC
    "Auburn Tigers":             "Auburn",
    "Kentucky Wildcats":         "Kentucky",
    "Tennessee Volunteers":      "Tennessee",
    "Ole Miss Rebels":           "Ole Miss",
    "Alabama Crimson Tide":      "Alabama",
    "Florida Gators":            "Florida",
    "Arkansas Razorbacks":       "Arkansas",
    "Missouri Tigers":           "Missouri",
    "Texas A&M Aggies":          "Texas A&M",
    "LSU Tigers":                "LSU",
    "Mississippi State Bulldogs": "Mississippi St",
    "Mississippi State":         "Mississippi St",
    "Georgia Bulldogs":          "Georgia",
    "South Carolina Gamecocks":  "South Carolina",
    "Vanderbilt Commodores":     "Vanderbilt",
    # Big East
    "St. John's Red Storm":      "St. John's",
    "Saint John's":              "St. John's",
    "St John's":                 "St. John's",
    "Providence Friars":         "Providence",
    "Xavier Musketeers":         "Xavier",
    "Villanova Wildcats":        "Villanova",
    "Georgetown Hoyas":          "Georgetown",
    "Butler Bulldogs":           "Butler",
    "Seton Hall Pirates":        "Seton Hall",
    "Marquette Golden Eagles":   "Marquette",
    "Creighton Bluejays":        "Creighton",
    # WCC / Mountain West / A-10
    "Gonzaga Bulldogs":          "Gonzaga",
    "Saint Mary's Gaels":        "Saint Mary's",
    "San Diego State Aztecs":    "San Diego St",
    "San Diego State":           "San Diego St",
    "Utah State Aggies":         "Utah St",
    "Utah State":                "Utah St",
    "Dayton Flyers":             "Dayton",
    "VCU Rams":                  "VCU",
    "Virginia Commonwealth":     "VCU",
    "UNLV Runnin Rebels":        "UNLV",
    "New Mexico Lobos":          "New Mexico",
    "Drake Bulldogs":            "Drake",
    "Richmond Spiders":          "Richmond",
    "Davidson Wildcats":         "Davidson",
    # Low-major
    "Texas Southern Tigers":     "Texas Southern",   # explicit alias — prevents Texas partial match

    # --- NHL aliases (Odds API uses full city+nickname) ---
    # Collision risk: NY Rangers vs NY Islanders — both need explicit aliases.
    # Partial match on "New York" would return whichever comes first in dict order.
    "Rangers":                   "New York Rangers",
    "New York Rangers Hockey":   "New York Rangers",
    "NY Rangers":                "New York Rangers",
    "Islanders":                 "New York Islanders",
    "New York Islanders Hockey": "New York Islanders",
    "NY Islanders":              "New York Islanders",
    # Vegas name variant — Odds API may return either form
    "Las Vegas Golden Knights":  "Vegas Golden Knights",
    "Golden Knights":            "Vegas Golden Knights",
    # Other common short-form variants
    "Panthers":                  "Florida Panthers",
    "Canucks":                   "Vancouver Canucks",
    "Avalanche":                 "Colorado Avalanche",
    "Stars":                     "Dallas Stars",
    "Jets":                      "Winnipeg Jets",
    "Bruins":                    "Boston Bruins",
    "Hurricanes":                "Carolina Hurricanes",
    "Canes":                     "Carolina Hurricanes",
    "Oilers":                    "Edmonton Oilers",
    "Devils":                    "New Jersey Devils",
    "Lightning":                 "Tampa Bay Lightning",
    "Bolts":                     "Tampa Bay Lightning",
    "Predators":                 "Nashville Predators",
    "Preds":                     "Nashville Predators",
    "Maple Leafs":               "Toronto Maple Leafs",
    "Leafs":                     "Toronto Maple Leafs",
    "Wild":                      "Minnesota Wild",
    "Senators":                  "Ottawa Senators",
    "Sens":                      "Ottawa Senators",
    "LA Kings":                  "Los Angeles Kings",
    "LAK":                       "Los Angeles Kings",
    "Penguins":                  "Pittsburgh Penguins",
    "Pens":                      "Pittsburgh Penguins",
    "Kraken":                    "Seattle Kraken",
    "Flames":                    "Calgary Flames",
    "Blues":                     "St. Louis Blues",
    "Red Wings":                 "Detroit Red Wings",
    "Flyers":                    "Philadelphia Flyers",
    "Capitals":                  "Washington Capitals",
    "Caps":                      "Washington Capitals",
    "Sabres":                    "Buffalo Sabres",
    "Ducks":                     "Anaheim Ducks",
    "Canadiens":                 "Montreal Canadiens",
    "Habs":                      "Montreal Canadiens",
    "Blue Jackets":              "Columbus Blue Jackets",
    "Blackhawks":                "Chicago Blackhawks",
    "Hawks":                     "Chicago Blackhawks",
    "Sharks":                    "San Jose Sharks",
    "Utah HC":                   "Utah Hockey Club",
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
    Return a 0-20 scaled efficiency gap between two teams (NBA or NCAAB).

    A score of 10.0 means teams are evenly matched.
    Score > 10: home team has an efficiency advantage.
    Score < 10: away team has an efficiency advantage.

    Covers all 30 NBA franchises (NetRtg-derived adj_em) and 80 NCAAB programs
    (KenPom/Barttorvik adj_em). Both use the same scaling so the gap is
    comparable across leagues within the 0-20 output range.

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


def list_teams(league: Optional[str] = None) -> list[str]:
    """
    Return all canonical team names in the dataset.

    Args:
        league: Optional filter — "NBA" or "NCAAB". None returns all teams.
    """
    if league is None:
        return sorted(_TEAM_DATA.keys())
    league_upper = league.upper()
    return sorted(k for k, v in _TEAM_DATA.items() if v.get("league") == league_upper)


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
