"""
parlay_builder.py — TITANIUM V36.1
=====================================
Multi-game parlay identification and EV ranking.

Promoted from R&D core/parlay_builder.py (Session 24 — 6/6 smoke tests pass).

Input: list of BetCandidate-style dicts (already ranked, all pass Sharp Score threshold).
       Each dict must have: event_id, target, market_type, win_prob, price, edge_pct, matchup

Logic:
  - Find all valid 2-leg combos where event_id differs (independent games)
  - Compute parlay_prob, parlay_payout, parlay_ev
  - Filter: parlay_ev > 0
  - Return sorted by parlay_ev descending

v36 call site shim:
  BetCandidate is a dataclass — convert before passing:
      from data.parlay_builder import build_parlay_combos
      combos = build_parlay_combos([vars(b) for b in ranked_bets])

DO NOT add API calls, Streamlit calls, or match logic to this file.
"""

import math
from itertools import combinations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _american_to_decimal(american: int) -> float:
    """Convert American odds to decimal odds (includes stake return)."""
    if american > 0:
        return american / 100 + 1
    else:
        return 100 / abs(american) + 1


def _parlay_ev(prob_a: float, price_a: int, prob_b: float, price_b: int) -> dict:
    """
    Compute 2-leg parlay metrics.

    parlay_prob    = prob_a × prob_b
    parlay_payout  = (payout_a + 1) × (payout_b + 1) − 1
                   where payout = decimal − 1  (profit per unit staked)
    parlay_ev      = parlay_prob × parlay_payout − (1 − parlay_prob)

    Returns dict with parlay_prob, parlay_payout, parlay_ev.
    """
    dec_a = _american_to_decimal(price_a)
    dec_b = _american_to_decimal(price_b)

    payout_a = dec_a - 1   # profit per unit if leg A wins
    payout_b = dec_b - 1   # profit per unit if leg B wins

    parlay_prob = prob_a * prob_b
    parlay_payout = (payout_a + 1) * (payout_b + 1) - 1
    parlay_ev = parlay_prob * parlay_payout - (1 - parlay_prob)

    return {
        "parlay_prob": round(parlay_prob, 4),
        "parlay_payout": round(parlay_payout, 4),
        "parlay_ev": round(parlay_ev, 4),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_parlay_combos(bets: list[dict]) -> list[dict]:
    """
    Find all valid 2-leg parlay combos with positive EV.

    Args:
        bets: list of BetCandidate-style dicts. Required keys:
              event_id, target, market_type, win_prob, price, edge_pct, matchup

    Returns:
        list of dicts sorted by parlay_ev descending. Each dict contains:
          leg_a, leg_b  — full bet dicts for each leg
          parlay_prob   — combined win probability
          parlay_payout — profit per unit staked if both win
          parlay_ev     — expected value (positive = +EV parlay)
    """
    if len(bets) < 2:
        return []

    results = []

    for bet_a, bet_b in combinations(bets, 2):
        # Independence gate: must be different games
        if bet_a["event_id"] == bet_b["event_id"]:
            continue

        metrics = _parlay_ev(
            bet_a["win_prob"], bet_a["price"],
            bet_b["win_prob"], bet_b["price"],
        )

        # Filter: only keep positive EV parlays
        if metrics["parlay_ev"] <= 0:
            continue

        results.append({
            "leg_a": bet_a,
            "leg_b": bet_b,
            "parlay_prob": metrics["parlay_prob"],
            "parlay_payout": metrics["parlay_payout"],
            "parlay_ev": metrics["parlay_ev"],
        })

    results.sort(key=lambda x: x["parlay_ev"], reverse=True)
    return results


def format_parlay_table(combos: list[dict]) -> str:
    """
    CLI-printable table of top parlay combos.

    Returns a formatted string. Empty string if no combos.
    """
    if not combos:
        return "No positive-EV 2-leg parlays found on current slate."

    header = (
        f"{'#':<3}  {'Leg A':<28}  {'Leg B':<28}  "
        f"{'P(win)':<8}  {'Payout':<8}  {'EV':<8}"
    )
    separator = "-" * len(header)
    lines = [header, separator]

    for i, combo in enumerate(combos, start=1):
        a = combo["leg_a"]
        b = combo["leg_b"]

        label_a = f"{a['target']} ({a['market_type']})"[:28]
        label_b = f"{b['target']} ({b['market_type']})"[:28]

        lines.append(
            f"{i:<3}  {label_a:<28}  {label_b:<28}  "
            f"{combo['parlay_prob']:<8.3f}  "
            f"{combo['parlay_payout']:<8.3f}  "
            f"{combo['parlay_ev']:+.4f}"
        )

    lines.append(separator)
    lines.append(f"Total combos: {len(combos)}")
    return "\n".join(lines)
