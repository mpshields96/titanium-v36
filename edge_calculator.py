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

import math
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BetCandidate:
    """A single bet candidate produced by parse_game_markets()."""
    sport: str
    matchup: str            # "Away @ Home"
    market_type: str        # "spread", "total", "moneyline", "prop"
    target: str             # e.g. "Duke Blue Devils -4.5" or "Over 148.5"
    line: float             # Numeric line value (0.0 for moneylines)
    price: int              # American odds (best price found)
    edge_pct: float         # consensus_prob - implied(best_price)
    win_prob: float         # Model's estimated win probability (consensus)
    market_implied: float   # Market implied probability (vig-inclusive)
    fair_implied: float     # Vig-free consensus probability
    kelly_size: float       # Fractional Kelly bet size in units
    signal: str = ""        # Human-readable tier label (set by bet_ranker)
    event_id: str = ""
    commence_time: str = ""
    book: str = ""          # Source book + n-books note
    # Set by bet_ranker after scoring
    sharp_score: float = 0.0
    sharp_breakdown: dict = field(default_factory=dict)
    nemesis: dict = field(default_factory=dict)
    simulation: object = None   # Optional SimulationResult from originator_engine


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
# Kill switches — Session 6
# ---------------------------------------------------------------------------
#
# All four return (killed: bool, reason: str).
# killed=True = abort bet. killed=False = safe (reason="" or a FLAG string).
# FLAG reasons are non-fatal — surface in output but do not drop the bet.
# KILL / FORCE_UNDER reasons are fatal — bet_ranker must drop or override.
#
# Inputs are provided by data/kill_switch_feed.py (same pattern as efficiency_feed).
# Wire-in pattern:
#   inputs = get_nba_kill_inputs(bet_team, opp_team, bet.line, bet.market_type)
#   killed, reason = nba_kill_switch(**{k: v for k, v in inputs.items() if k != 'data_live'})
#   if killed: continue
# ---------------------------------------------------------------------------


def nba_kill_switch(
    rest_disadvantage: bool,
    spread: float,
    star_absent: bool = False,
    avg_margin: float = 5.0,
    b2b: bool = False,
    pace_std_dev: float = 0.0,
    market_type: str = "spread",
) -> tuple[bool, str]:
    """
    NBA kill switch per V36.1 spec.

    Spec rule: rest_disadvantage AND spread inside -4 AND market_type=spread → KILL.
    Extended: star absent inside avg margin, B2B flag, high pace variance on totals.

    Args:
        rest_disadvantage: Bet team is on shorter rest than opponent.
        spread:            Market spread line (negative = favourite).
        star_absent:       Primary star player confirmed out.
        avg_margin:        Team's average winning/losing margin (default 5.0).
        b2b:               Bet team playing second game of back-to-back.
        pace_std_dev:      Std dev of pace across last N games (high = volatile).
        market_type:       "spread", "moneyline", "total", "prop".

    Returns:
        (killed, reason) — killed=True means abort.
    """
    if rest_disadvantage and market_type == "spread" and abs(spread) < 4:
        return True, "KILL: Rest disadvantage with spread inside -4 — abort spread"

    if star_absent and abs(spread) < avg_margin:
        return True, "KILL: Star absence with spread inside average margin"

    if b2b:
        return False, "FLAG: B2B — reduce Kelly by 50%"

    if pace_std_dev > 4 and market_type == "total":
        return True, "KILL: High pace variance — skip total"

    return False, ""


def nfl_kill_switch(
    wind_mph: float,
    total: float,
    backup_qb: bool = False,
    market_type: str = "total",
) -> tuple[bool, str]:
    """
    NFL kill switch per V36.1 spec.

    Spec rule: wind > 15mph AND total > 42 AND market_type=total → FORCE_UNDER or PASS.
    Extended: backup QB start, extreme wind >20mph.

    Args:
        wind_mph:    Forecasted wind speed at game time in mph.
        total:       Over/under market line.
        backup_qb:   Starting QB confirmed out, backup starting.
        market_type: "spread", "moneyline", "total", "prop".

    Returns:
        (killed, reason) — killed=True means abort (or force under per reason string).
        FORCE_UNDER in reason: if betting over, kill it; under is still valid.
    """
    if backup_qb:
        return True, "KILL: Backup QB — require 10%+ edge to proceed"

    if wind_mph > 20:
        return True, "KILL: Wind >20mph — skip all totals"

    if wind_mph > 15 and total > 42 and market_type == "total":
        return True, "FORCE_UNDER: Wind >15mph with high total — take under or pass"

    return False, ""


def ncaab_kill_switch(
    three_point_reliance: float,
    is_away: bool,
    tempo_diff: float = 0.0,
    conference_tournament: bool = False,
    market_type: str = "spread",
) -> tuple[bool, str]:
    """
    NCAAB kill switch per V36.1 spec.

    Spec rule: 3P reliance > 40% AND away game → FADE.
    Extended: tempo mismatch > 10 possessions on totals, tournament pressure flag.

    Args:
        three_point_reliance: Fraction of offense from 3-pointers (0.0–1.0).
        is_away:              Bet team is the away team.
        tempo_diff:           Possession difference per 40 min between teams.
        conference_tournament: Game is a conference tournament game.
        market_type:          "spread", "moneyline", "total", "prop".

    Returns:
        (killed, reason) — killed=True means abort.
    """
    if three_point_reliance > 0.40 and is_away:
        return True, f"KILL: 3PT reliance {three_point_reliance:.0%} on road — fade"

    if tempo_diff > 10 and market_type == "total":
        return True, f"KILL: Tempo diff {tempo_diff:.1f} possessions — skip total"

    if conference_tournament:
        return False, "FLAG: Conference tournament — require 8%+ edge"

    return False, ""


def soccer_kill_switch(
    market_drift_pct: float,
    dead_rubber: bool = False,
    key_creator_out: bool = False,
    market_type: str = "moneyline",
) -> tuple[bool, str]:
    """
    Soccer kill switch per V36.1 spec.

    Spec rule: market drift > 10% against position → ABORT.
    Extended: dead rubber games, key creator confirmed absent.

    Args:
        market_drift_pct: Fraction the line moved against position since open
                          (e.g. 0.12 = 12% drift). Computed in kill_switch_feed.
        dead_rubber:      Game has no meaningful stakes.
        key_creator_out:  Primary chance-creator confirmed absent.
        market_type:      "moneyline", "total", "spread", "prop".

    Returns:
        (killed, reason) — killed=True means abort.
    """
    if market_drift_pct > 0.10:
        return True, f"KILL: Market drifted {market_drift_pct:.1%} against position — abort"

    if dead_rubber:
        return True, "KILL: Dead rubber — skip"

    if key_creator_out:
        return False, "FLAG: Key creator out — downgrade significantly"

    return False, ""


# ---------------------------------------------------------------------------
# Sharp Score (Session 4 — ported from R&D)
# ---------------------------------------------------------------------------

def calculate_sharp_score(
    edge_pct: float,
    rlm_confirmed: bool,
    efficiency_gap: float,
    rest_edge: float = 0.0,
    injury_leverage: float = 0.0,
    motivation: float = 0.0,
    matchup_score: float = 0.0,
) -> tuple[float, dict]:
    """
    Sharp Score: unified 0-100 composite ranking.

    Components (V36.1 spec):
      EDGE (40 pts):        (edge% / 10%) × 40, capped at 40
      RLM (25 pts):         25 if reverse line movement confirmed, else 0
      EFFICIENCY (20 pts):  caller-provided 0-20 scaled gap (KenPom/Barttorvik)
      SITUATIONAL (15 pts): rest + injury + motivation + matchup, capped at 15

    NOTE: RLM always 0 until line movement tracking is implemented (known gap).
    NOTE: efficiency_gap defaults to 8.0 in bet_ranker (moderate) when no data.

    Returns:
        (sharp_score, breakdown_dict)
    """
    edge_pts = min(40.0, (edge_pct / 0.10) * 40)
    rlm_pts = 25.0 if rlm_confirmed else 0.0
    eff_pts = max(0.0, min(20.0, efficiency_gap))

    sit_pts = min(5.0, rest_edge) + min(5.0, injury_leverage) + \
              min(3.0, motivation) + min(2.0, matchup_score)
    sit_pts = min(15.0, sit_pts)

    total = edge_pts + rlm_pts + eff_pts + sit_pts

    breakdown = {
        "edge": round(edge_pts, 1),
        "rlm": round(rlm_pts, 1),
        "efficiency": round(eff_pts, 1),
        "situational": round(sit_pts, 1),
    }

    return round(total, 1), breakdown


def sharp_to_size(sharp_score: float, is_prop: bool = False) -> str:
    """
    Map Sharp Score to bet tier label.

    Thresholds (V36.1 — temporary until efficiency/situational data wired):
      >= 90 → NUCLEAR_2.0U
      >= 80 → STANDARD_1.0U
      else  → LEAN_0.5U   (all bets that survived pipeline get at least LEAN)

    NOTE: PASS is never returned here — bets that didn't survive are simply
    not in the list. This function only labels surviving bets.
    """
    if sharp_score >= 90:
        return "NUCLEAR_2.0U"
    if sharp_score >= 80:
        return "STANDARD_1.0U"
    return "LEAN_0.5U"


def run_nemesis(bet: BetCandidate, sport: str) -> dict:
    """
    Generate adversarial counter-thesis for a bet.

    Cases are tagged by applicable market_type. Selects the highest-probability
    case relevant to this bet's market_type. Falls back to all cases if no
    market-specific match.

    Returns dict with: counter, probability, adjustment, remove.
    remove=True means nemesis counter prob > 40% — drop the bet entirely.
    """
    # Each entry: (counter_text, probability, adjustment, applicable_market_types)
    nemesis_cases = {
        "NBA": [
            ("Line movement suggests sharp money on other side",
             0.30, -15, {"spread", "moneyline"}),
            ("Team relies on 3PT shooting, opponent defends arc well",
             0.25, -15, {"spread", "moneyline"}),
            ("Total variance high — pace mismatch creates unpredictable scoring",
             0.25, -15, {"total"}),
            ("B2B fatigue not fully captured in ratings",
             0.20, -10, {"any"}),
            ("Road team in hostile environment, young roster",
             0.20, -10, {"spread", "moneyline"}),
            ("Player workload managed — prop line may not reflect rest decision",
             0.25, -15, {"prop"}),
        ],
        "NCAAB": [
            ("Road favorite in hostile environment, pressure on young team",
             0.30, -15, {"spread", "moneyline"}),
            ("3PT variance could eliminate efficiency edge",
             0.25, -15, {"spread", "moneyline", "total"}),
            ("Underdog at home often outperforms ratings",
             0.20, -10, {"spread", "moneyline"}),
            ("Tempo mismatch makes total unreliable",
             0.25, -15, {"total"}),
        ],
        "NFL": [
            ("Line through key number (3, 7, 10) — extra caution",
             0.25, -15, {"spread"}),
            ("Weather variance not fully modeled",
             0.25, -15, {"total"}),
            ("Injury report could change within 24 hours",
             0.20, -10, {"any"}),
            ("Moneyline juice on favorite often overpriced",
             0.20, -10, {"moneyline"}),
        ],
        "NHL": [
            ("Goalie variance is the dominant factor",
             0.30, -15, {"moneyline", "spread"}),
            ("PDO regression — hot team due for correction",
             0.25, -15, {"moneyline", "spread"}),
            ("Shot quality vs quantity mismatch clouds total",
             0.25, -15, {"total"}),
        ],
        "SOCCER": [
            ("High draw probability (~28%) not fully priced in",
             0.25, -15, {"moneyline"}),
            ("Must-attack team vulnerable on counter",
             0.30, -15, {"spread", "moneyline"}),
            ("Low xG variance inflates total uncertainty",
             0.25, -10, {"total"}),
            ("Lineup not confirmed — key player status unknown",
             0.20, -10, {"any"}),
        ],
    }

    cases = nemesis_cases.get(sport.upper(), nemesis_cases.get("NBA", []))
    if not cases:
        return {"counter": "No standard nemesis for this sport",
                "probability": 0.10, "adjustment": 0, "remove": False}

    market = bet.market_type
    relevant = [c for c in cases if market in c[3] or "any" in c[3]]
    if not relevant:
        relevant = cases  # fallback

    best = max(relevant, key=lambda x: x[1])
    counter, prob, adj, _ = best

    return {
        "counter": counter,
        "probability": prob,
        "adjustment": adj if prob >= 0.30 else (adj // 2 if prob >= 0.20 else 0),
        "remove": prob > 0.40,
    }


# ---------------------------------------------------------------------------
# Multi-book consensus edge detection (Session 3 — proven in R&D)
# ---------------------------------------------------------------------------

def _consensus_fair_prob(
    team_name: str,
    market_key: str,
    side: str,
    bookmakers: list,
) -> tuple[float, float, int]:
    """
    Build consensus vig-free probability across all books for one side.

    Method:
      - For each book that has BOTH sides of the market, compute the
        vig-free probability via no_vig_probability().
      - Return (mean_fair_prob, std_dev, n_books).

    This is the core edge signal: the consensus mean is the model probability.
    When the best available price implies a lower probability than the consensus,
    that book has mispriced the market → edge exists.

    Args:
        team_name:  Team name for spreads/h2h, ignored for totals.
        market_key: "spreads", "h2h", or "totals".
        side:       "Over" or "Under" for totals; ignored for spreads/h2h.
        bookmakers: Raw bookmakers list from Odds API game dict.

    Returns:
        (mean_fair_prob, std_dev, n_books) — n_books=0 means no data.
    """
    fair_probs = []

    for book in bookmakers:
        market_map = {m["key"]: m for m in book.get("markets", [])}
        if market_key not in market_map:
            continue

        outcomes = market_map[market_key].get("outcomes", [])

        if market_key in ("spreads", "h2h"):
            if len(outcomes) != 2:
                continue
            target_odds = None
            opp_odds = None
            for o in outcomes:
                if o.get("name") == team_name:
                    target_odds = o.get("price")
                else:
                    opp_odds = o.get("price")

            if target_odds and opp_odds:
                try:
                    fp, _ = no_vig_probability(target_odds, opp_odds)
                    fair_probs.append(fp)
                except (ZeroDivisionError, ValueError):
                    pass

        elif market_key == "totals":
            if len(outcomes) != 2:
                continue
            over_o = next((o for o in outcomes if o.get("name") == "Over"), None)
            under_o = next((o for o in outcomes if o.get("name") == "Under"), None)
            if over_o and under_o:
                try:
                    over_p, under_p = no_vig_probability(
                        over_o.get("price", 0), under_o.get("price", 0)
                    )
                    fp = over_p if side == "Over" else under_p
                    fair_probs.append(fp)
                except (ZeroDivisionError, ValueError):
                    pass

    if not fair_probs:
        return 0.5, 0.0, 0

    n = len(fair_probs)
    mean = sum(fair_probs) / n
    variance = sum((p - mean) ** 2 for p in fair_probs) / n if n > 1 else 0.0
    std = math.sqrt(variance)

    return mean, std, n


def parse_game_markets(game: dict, sport: str = "NCAAB") -> list[BetCandidate]:
    """
    Parse a raw game dict from odds_fetcher into BetCandidate objects.

    Edge detection method: multi-book consensus (proven in R&D).
      Step 1: Collect vig-free probability from each book (both sides required).
      Step 2: Average them → consensus model probability.
      Step 3: Find the best available price at any single book.
      Step 4: Edge = consensus_prob - implied_probability(best_price).

    Minimum edge threshold: 3.5% (V36.1 non-negotiable rule).
    Minimum books required: 2 (single-book consensus is not reliable).

    Args:
        game:  Raw game dict from fetch_game_lines() / fetch_sport().
        sport: Sport key for BetCandidate (e.g. "NCAAB", "NBA").

    Returns:
        List of BetCandidate objects passing collar AND minimum edge filter.
        Empty list if insufficient data or no edges found.
    """
    from odds_fetcher import all_books as _all_books

    candidates = []
    home = game.get("home_team", "")
    away = game.get("away_team", "")
    matchup = f"{away} @ {home}"
    event_id = game.get("id", "")
    commence_time = game.get("commence_time", "")
    bookmakers = game.get("bookmakers", [])

    if not bookmakers:
        return []

    all_bks = _all_books(bookmakers)

    # --- Spreads ---
    for team_name in [home, away]:
        consensus_prob, std_dev, n_books = _consensus_fair_prob(
            team_name, "spreads", "team", bookmakers
        )
        if n_books < 2:
            continue

        # Best available price for this team across all books
        best_price = None
        best_line = None
        best_book_name = ""
        for book in all_bks:
            mmap = {m["key"]: m for m in book.get("markets", [])}
            if "spreads" not in mmap:
                continue
            for o in mmap["spreads"].get("outcomes", []):
                if o.get("name") == team_name:
                    price = o.get("price", 0)
                    line = o.get("point", 0.0)
                    if best_price is None or price > best_price:
                        best_price = price
                        best_line = line
                        best_book_name = book.get("title", book.get("key", ""))

        if best_price is None or not passes_collar(best_price):
            continue

        edge = consensus_prob - _implied_probability(best_price)
        if edge >= 0.035:
            kelly = fractional_kelly(consensus_prob, best_price)
            candidates.append(BetCandidate(
                sport=sport,
                matchup=matchup,
                market_type="spread",
                target=f"{team_name} {best_line:+.1f}",
                line=best_line or 0.0,
                price=best_price,
                edge_pct=edge,
                win_prob=consensus_prob,
                market_implied=_implied_probability(best_price),
                fair_implied=consensus_prob,
                kelly_size=kelly,
                event_id=event_id,
                commence_time=commence_time,
                book=f"Best: {best_book_name} ({n_books} books)",
            ))

    # --- Moneylines ---
    for team_name in [home, away]:
        consensus_prob, std_dev, n_books = _consensus_fair_prob(
            team_name, "h2h", "team", bookmakers
        )
        if n_books < 2:
            continue

        best_price = None
        best_book_name = ""
        for book in all_bks:
            mmap = {m["key"]: m for m in book.get("markets", [])}
            if "h2h" not in mmap:
                continue
            for o in mmap["h2h"].get("outcomes", []):
                if o.get("name") == team_name:
                    price = o.get("price", 0)
                    if best_price is None or price > best_price:
                        best_price = price
                        best_book_name = book.get("title", book.get("key", ""))

        if best_price is None or not passes_collar(best_price):
            continue

        edge = consensus_prob - _implied_probability(best_price)
        if edge >= 0.035:
            kelly = fractional_kelly(consensus_prob, best_price)
            candidates.append(BetCandidate(
                sport=sport,
                matchup=matchup,
                market_type="moneyline",
                target=f"{team_name} ML",
                line=0.0,
                price=best_price,
                edge_pct=edge,
                win_prob=consensus_prob,
                market_implied=_implied_probability(best_price),
                fair_implied=consensus_prob,
                kelly_size=kelly,
                event_id=event_id,
                commence_time=commence_time,
                book=f"Best: {best_book_name} ({n_books} books)",
            ))

    # --- Totals ---
    for side in ["Over", "Under"]:
        consensus_prob, std_dev, n_books = _consensus_fair_prob(
            "", "totals", side, bookmakers
        )
        if n_books < 2:
            continue

        best_price = None
        best_line = None
        best_book_name = ""
        for book in all_bks:
            mmap = {m["key"]: m for m in book.get("markets", [])}
            if "totals" not in mmap:
                continue
            for o in mmap["totals"].get("outcomes", []):
                if o.get("name") == side:
                    price = o.get("price", 0)
                    line = o.get("point", 0.0)
                    if best_price is None or price > best_price:
                        best_price = price
                        best_line = line
                        best_book_name = book.get("title", book.get("key", ""))

        if best_price is None or not passes_collar(best_price):
            continue

        edge = consensus_prob - _implied_probability(best_price)
        if edge >= 0.035:
            kelly = fractional_kelly(consensus_prob, best_price)
            candidates.append(BetCandidate(
                sport=sport,
                matchup=matchup,
                market_type="total",
                target=f"{side} {best_line}",
                line=best_line or 0.0,
                price=best_price,
                edge_pct=edge,
                win_prob=consensus_prob,
                market_implied=_implied_probability(best_price),
                fair_implied=consensus_prob,
                kelly_size=kelly,
                event_id=event_id,
                commence_time=commence_time,
                book=f"Best: {best_book_name} ({n_books} books)",
            ))

    return candidates
