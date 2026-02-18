"""
edge_calculator.py — TITANIUM V36.1
======================================
All betting math lives here. No API calls, no UI.

Responsibilities:
- Apply odds collar (-180 to +150) to filter raw odds
- Calculate edge % for each market (Titanium True Price vs market price)
- Apply sport-specific kill switches
- Calculate fractional Kelly bet sizing
- Return a list of bet candidates for bet_ranker to consume

NON-NEGOTIABLE RULES ENFORCED HERE:
1. Odds collar: -180 <= american_odds <= +150
2. Minimum edge: >= 3.5% to pass
3. Kill switches: NBA rest, NFL wind, NCAAB 3P, Soccer drift
4. Kelly fraction: 0.25x, max 2.0 units

DO NOT add API calls or Streamlit calls to this file.
"""


# ---------------------------------------------------------------------------
# Collar check
# ---------------------------------------------------------------------------

def passes_collar(american_odds: int) -> bool:
    """
    Return True if odds are within the -180 to +150 collar.
    Any odds outside this range are rejected immediately.

    Args:
        american_odds: Odds in American format (e.g., -110, +130).

    Returns:
        True if within collar, False if not.
    """
    return -180 <= american_odds <= 150


# ---------------------------------------------------------------------------
# Edge calculation
# ---------------------------------------------------------------------------

def calculate_edges(raw_odds: list, sport: str) -> list:
    """
    Main entry point called by app.py.
    Filters raw odds through collar, calculates edge for each market,
    applies kill switches, and returns passing bets.

    Args:
        raw_odds: Output from odds_fetcher.fetch_batch_odds() or fetch_events().
        sport: One of "NBA", "NFL", "NCAAB", "NHL", "Soccer".

    Returns:
        List of bet candidate dicts, each containing:
        {matchup, type, target, line, price, edge_pct, win_prob, kelly_size, signal}
    """
    # TODO Session 3: Implement per-sport routing
    pass


def _implied_probability(american_odds: int) -> float:
    """
    Convert American odds to implied win probability (0.0 to 1.0).
    This is the raw (vig-inclusive) probability. Use no_vig_probability()
    to get the fair price with juice removed.

    Formula:
        Negative odds (favorites): |odds| / (|odds| + 100)
        Positive odds (underdogs): 100 / (odds + 100)

    Args:
        american_odds: Odds in American format (e.g., -110, +150).

    Returns:
        Implied probability as a decimal (e.g., 0.5238 for -110).
    """
    if american_odds < 0:
        return abs(american_odds) / (abs(american_odds) + 100)
    else:
        return 100 / (american_odds + 100)


def no_vig_probability(odds_side_a: int, odds_side_b: int) -> tuple[float, float]:
    """
    Remove bookmaker vig from a two-outcome market and return fair probabilities.
    Both sides of the market are required to compute the overround (juice).

    Method: Convert each side to implied probability, sum them (overround > 1.0),
    then normalise each side by dividing by the overround.

    Example: -110 / -110 market
        raw_a = 0.5238, raw_b = 0.5238, overround = 1.0476
        fair_a = 0.5238 / 1.0476 = 0.5000 (exactly 50/50 as expected)

    Args:
        odds_side_a: American odds for side A.
        odds_side_b: American odds for side B.

    Returns:
        Tuple of (fair_prob_a, fair_prob_b) — decimals that sum to 1.0.
    """
    raw_a = _implied_probability(odds_side_a)
    raw_b = _implied_probability(odds_side_b)
    overround = raw_a + raw_b
    return raw_a / overround, raw_b / overround


def calculate_edge(titanium_win_prob: float, market_odds: int) -> float:
    """
    Calculate the edge percentage between Titanium's true price and the market.
    Positive edge means Titanium thinks we win more often than the market implies.

    Formula: edge = titanium_win_prob - implied_probability(market_odds)

    Args:
        titanium_win_prob: Titanium's estimated win probability (0.0 to 1.0).
        market_odds: Market odds in American format.

    Returns:
        Edge as a decimal (e.g., 0.0262 = 2.62% edge).
        Positive = we have an advantage. Negative = market has the edge.
    """
    return titanium_win_prob - _implied_probability(market_odds)


def calculate_profit(stake: float, american_odds: int) -> float:
    """
    Calculate profit (not including returned stake) for a winning bet.

    Formula:
        Positive odds: profit = stake × (odds / 100)
        Negative odds: profit = stake × (100 / |odds|)

    Args:
        stake: Amount wagered in dollars.
        american_odds: Odds in American format.

    Returns:
        Profit in dollars (excluding the returned stake).
    """
    if american_odds > 0:
        return stake * (american_odds / 100)
    else:
        return stake * (100 / abs(american_odds))


# ---------------------------------------------------------------------------
# Kelly sizing
# ---------------------------------------------------------------------------

def fractional_kelly(win_prob: float, american_odds: int, fraction: float = 0.25) -> float:
    """
    Calculate 0.25x fractional Kelly bet size in units.
    Hard caps: 2.0 units max (nuclear), 1.0 units (standard), 0.5 units (lean).

    Args:
        win_prob: Estimated win probability (0.0 to 1.0).
        american_odds: Odds in American format.
        fraction: Kelly fraction to apply (default 0.25 per V36.1 rules).

    Returns:
        Recommended bet size in units, capped per V36.1 rules.
    """
    # Convert American odds to decimal
    if american_odds > 0:
        decimal_odds = (american_odds / 100) + 1
    else:
        decimal_odds = (100 / abs(american_odds)) + 1

    # Full Kelly formula
    b = decimal_odds - 1
    q = 1 - win_prob
    full_kelly = (b * win_prob - q) / b

    # Apply fraction
    bet_size = full_kelly * fraction

    # V36.1 caps — enforced here, not negotiable
    if win_prob > 0.60:
        return min(bet_size, 2.0)
    elif win_prob > 0.54:
        return min(bet_size, 1.0)
    else:
        return min(bet_size, 0.5)


# ---------------------------------------------------------------------------
# Kill switches
# ---------------------------------------------------------------------------

def nba_kill_switch(rest_disadvantage: bool, spread: float) -> bool:
    """
    NBA kill switch: abort if team has rest disadvantage AND spread < -4.

    Args:
        rest_disadvantage: True if the favored team played more recently.
        spread: Market spread for the favored team (negative = favorite).

    Returns:
        True if bet should be aborted, False if safe to proceed.
    """
    # TODO Session 3: Implement
    pass


def nfl_kill_switch(wind_mph: float, total: float) -> str:
    """
    NFL kill switch: if wind > 15mph AND total > 42, force Under or Pass.

    Args:
        wind_mph: Wind speed at game location in mph.
        total: Market total (over/under line).

    Returns:
        "UNDER" to force under bet, "PASS" to skip entirely, "OK" if no kill.
    """
    # TODO Session 3: Implement
    pass


def ncaab_kill_switch(three_point_reliance: float, is_away: bool) -> bool:
    """
    NCAAB kill switch: fade if team's 3P reliance > 40% AND they're away.

    Args:
        three_point_reliance: Fraction of offense from 3-pointers (0.0 to 1.0).
        is_away: True if this team is the away team.

    Returns:
        True if bet should be faded (aborted), False if safe to proceed.
    """
    # TODO Session 3: Implement
    pass


def soccer_kill_switch(market_drift_pct: float) -> bool:
    """
    Soccer kill switch: abort if market has drifted > 10% against our position.

    Args:
        market_drift_pct: Percentage the market has moved against our position.

    Returns:
        True if bet should be aborted, False if safe to proceed.
    """
    # TODO Session 3: Implement
    pass
