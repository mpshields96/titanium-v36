"""
soccer_consensus.py — TITANIUM V36.1
======================================
Correct 3-outcome vig removal for soccer h2h markets.

Background (GAP 4 — confirmed material R&D Session 26):
  _consensus_fair_prob() in edge_calculator.py uses no_vig_probability(odds_a, odds_b)
  — a 2-outcome vig removal. Soccer h2h is a 3-outcome market (home / draw / away).
  The draw outcome is excluded from the denominator, inflating home and away fair
  probabilities by +10 to +19pp (live EPL probe, 2026-02-19, 198 book-game pairs,
  avg home inflation +13.46pp, avg away inflation +10.42pp).

Fix:
  fair_x = imp_x / (imp_home + imp_draw + imp_away)   — 3-way normalization per book.

v36 integration:
  - Called from parse_game_markets() in edge_calculator.py for soccer h2h only.
  - Detect soccer by sport key: sport_key.startswith("soccer_")
  - All non-soccer sports continue using existing 2-outcome no_vig_probability() — correct.
  - Draw: fair_draw returned but no BetCandidate generated (draw betting not in scope).

Promoted from R&D core/soccer_consensus.py (Session 27 — 6/6 smoke tests pass).
Import path change on promotion: `from core.soccer_consensus` → `from data.soccer_consensus`.

DO NOT add API calls, Streamlit calls, or match logic to this file.
"""

import math


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def american_to_implied(american: int) -> float:
    """
    Convert American odds to raw implied probability (includes vig).

    Examples:
      -110 → 0.5238 (52.38%)
      +150 → 0.4000 (40.00%)
      -200 → 0.6667 (66.67%)
    """
    if american > 0:
        return 100 / (american + 100)
    else:
        return abs(american) / (abs(american) + 100)


def _fair_3way(imp_home: float, imp_draw: float, imp_away: float) -> tuple[float, float, float]:
    """
    3-outcome vig removal for a single book.

    Correct denominator includes all three outcomes:
      total = imp_home + imp_draw + imp_away   (> 1.0 due to vig)
      fair_x = imp_x / total

    Returns (fair_home, fair_draw, fair_away). All three sum to 1.0.
    """
    total = imp_home + imp_draw + imp_away
    if total <= 0:
        return 0.0, 0.0, 0.0
    return imp_home / total, imp_draw / total, imp_away / total


def _std_dev(values: list[float]) -> float:
    """Sample standard deviation. Returns 0.0 for n <= 1."""
    n = len(values)
    if n <= 1:
        return 0.0
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return math.sqrt(variance)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def consensus_fair_prob_3way(
    home_prices: list[int],
    draw_prices: list[int],
    away_prices: list[int],
) -> dict:
    """
    Compute consensus fair probability for a soccer 3-outcome market.

    For each book: convert American odds to implied probs, apply 3-way vig removal,
    then average across all books.

    Args:
        home_prices: list of American odds for home win, one per book
        draw_prices: list of American odds for draw, one per book
        away_prices: list of American odds for away win, one per book
        All three lists must have the same length (one entry per book).

    Returns:
        dict with keys:
          fair_home  (float) — consensus fair probability, home win
          fair_draw  (float) — consensus fair probability, draw
          fair_away  (float) — consensus fair probability, away win
          std_dev    (float) — std dev of per-book fair_home values (percentage points)
          n_books    (int)   — number of books used in consensus

    Raises:
        ValueError: if list lengths differ or any list is empty
    """
    if not home_prices:
        raise ValueError("home_prices is empty — need at least one book")
    if len(home_prices) != len(draw_prices) or len(home_prices) != len(away_prices):
        raise ValueError(
            f"Price list lengths differ: home={len(home_prices)}, "
            f"draw={len(draw_prices)}, away={len(away_prices)}"
        )

    fair_homes, fair_draws, fair_aways = [], [], []

    for h_price, d_price, a_price in zip(home_prices, draw_prices, away_prices):
        imp_h = american_to_implied(h_price)
        imp_d = american_to_implied(d_price)
        imp_a = american_to_implied(a_price)
        fh, fd, fa = _fair_3way(imp_h, imp_d, imp_a)
        fair_homes.append(fh)
        fair_draws.append(fd)
        fair_aways.append(fa)

    n = len(fair_homes)
    mean_home = sum(fair_homes) / n
    mean_draw = sum(fair_draws) / n
    mean_away = sum(fair_aways) / n

    # std_dev in percentage points — consistent with BetCandidate.std_dev semantics
    sd_pp = _std_dev(fair_homes) * 100

    return {
        "fair_home": round(mean_home, 6),
        "fair_draw": round(mean_draw, 6),
        "fair_away": round(mean_away, 6),
        "std_dev": round(sd_pp, 4),
        "n_books": n,
    }
