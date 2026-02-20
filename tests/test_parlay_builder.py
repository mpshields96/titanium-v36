"""
tests/test_parlay_builder.py — TITANIUM V36.1
Tests for data/parlay_builder.py
"""

import pytest
from data.parlay_builder import build_parlay_combos, format_parlay_table, _american_to_decimal, _parlay_ev


# ---------------------------------------------------------------------------
# Synthetic bets (5 bets across 4 games — same as R&D smoke tests)
# ---------------------------------------------------------------------------

BETS = [
    {
        "event_id": "EVT001",
        "target": "Boston Celtics",
        "market_type": "h2h",
        "win_prob": 0.62,
        "price": -140,
        "edge_pct": 0.055,
        "matchup": "Celtics vs Hawks",
    },
    {
        "event_id": "EVT002",
        "target": "Oklahoma City Thunder",
        "market_type": "h2h",
        "win_prob": 0.58,
        "price": -115,
        "edge_pct": 0.048,
        "matchup": "Thunder vs Nuggets",
    },
    {
        "event_id": "EVT003",
        "target": "Cleveland Cavaliers",
        "market_type": "spread",
        "win_prob": 0.54,
        "price": -110,
        "edge_pct": 0.038,
        "matchup": "Cavaliers vs Bucks",
    },
    {
        "event_id": "EVT003",  # Same game — should be excluded from combos with EVT003
        "target": "Milwaukee Bucks",
        "market_type": "h2h",
        "win_prob": 0.47,
        "price": 130,
        "edge_pct": 0.041,
        "matchup": "Cavaliers vs Bucks",
    },
    {
        "event_id": "EVT004",
        "target": "Golden State Warriors",
        "market_type": "h2h",
        "win_prob": 0.35,   # Low prob — drags combos to negative EV
        "price": 180,
        "edge_pct": 0.031,
        "matchup": "Warriors vs Grizzlies",
    },
]


# ---------------------------------------------------------------------------
# _american_to_decimal
# ---------------------------------------------------------------------------

def test_decimal_positive_odds():
    # +180 → 180/100 + 1 = 2.80
    assert abs(_american_to_decimal(180) - 2.80) < 0.0001


def test_decimal_negative_odds():
    # -140 → 100/140 + 1 ≈ 1.7143
    assert abs(_american_to_decimal(-140) - (100/140 + 1)) < 0.0001


def test_decimal_minus_110():
    # -110 → 100/110 + 1 ≈ 1.9091
    assert abs(_american_to_decimal(-110) - (100/110 + 1)) < 0.0001


# ---------------------------------------------------------------------------
# _parlay_ev math spot-check
# ---------------------------------------------------------------------------

def test_parlay_ev_math():
    # EVT001 (-140) + EVT002 (-115), probs 0.62 and 0.58
    # dec_a = 100/140 + 1 ≈ 1.7143, payout_a = 0.7143
    # dec_b = 100/115 + 1 ≈ 1.8696, payout_b = 0.8696
    # parlay_payout = 1.7143 * 1.8696 - 1 ≈ 2.2051
    # parlay_prob = 0.62 * 0.58 = 0.3596
    # parlay_ev = 0.3596 * 2.2051 - 0.6404 ≈ 0.1525
    result = _parlay_ev(0.62, -140, 0.58, -115)
    assert abs(result["parlay_prob"] - round(0.62 * 0.58, 4)) < 0.0001
    assert result["parlay_ev"] > 0


# ---------------------------------------------------------------------------
# build_parlay_combos
# ---------------------------------------------------------------------------

def test_same_event_excluded():
    """Same event_id pairs must never appear in combos."""
    combos = build_parlay_combos(BETS)
    same_game = [
        c for c in combos
        if c["leg_a"]["event_id"] == c["leg_b"]["event_id"]
    ]
    assert len(same_game) == 0


def test_all_combos_positive_ev():
    """Every returned combo must have parlay_ev > 0."""
    combos = build_parlay_combos(BETS)
    for c in combos:
        assert c["parlay_ev"] > 0, f"Non-positive EV combo: {c}"


def test_sorted_descending():
    """Combos must be sorted by parlay_ev descending."""
    combos = build_parlay_combos(BETS)
    if len(combos) >= 2:
        for i in range(len(combos) - 1):
            assert combos[i]["parlay_ev"] >= combos[i + 1]["parlay_ev"]


def test_evt001_evt002_combo_found():
    """EVT001+EVT002 are both high-prob bets — their combo should be in results."""
    combos = build_parlay_combos(BETS)
    pair = next(
        (c for c in combos
         if {c["leg_a"]["event_id"], c["leg_b"]["event_id"]} == {"EVT001", "EVT002"}),
        None,
    )
    assert pair is not None, "EVT001+EVT002 combo not found"


def test_evt001_evt002_math():
    """Verify parlay math for EVT001+EVT002 spot-check pair."""
    combos = build_parlay_combos(BETS)
    pair = next(
        (c for c in combos
         if {c["leg_a"]["event_id"], c["leg_b"]["event_id"]} == {"EVT001", "EVT002"}),
        None,
    )
    assert pair is not None

    expected_prob = round(0.62 * 0.58, 4)
    dec_a = _american_to_decimal(-140)
    dec_b = _american_to_decimal(-115)
    expected_payout = round(dec_a * dec_b - 1, 4)
    expected_ev = round(expected_prob * expected_payout - (1 - expected_prob), 4)

    assert abs(pair["parlay_prob"] - expected_prob) < 0.0001
    assert abs(pair["parlay_ev"] - expected_ev) < 0.001


def test_too_few_bets_returns_empty():
    """Single bet — no combos possible."""
    assert build_parlay_combos([BETS[0]]) == []


def test_empty_bets_returns_empty():
    assert build_parlay_combos([]) == []


def test_combo_contains_full_bet_dicts():
    """Each combo must carry the full leg dicts, not just IDs."""
    combos = build_parlay_combos(BETS)
    if combos:
        c = combos[0]
        assert "event_id" in c["leg_a"]
        assert "win_prob" in c["leg_a"]
        assert "target" in c["leg_b"]


# ---------------------------------------------------------------------------
# format_parlay_table
# ---------------------------------------------------------------------------

def test_format_returns_string():
    combos = build_parlay_combos(BETS)
    table = format_parlay_table(combos)
    assert isinstance(table, str)
    assert len(table) > 0


def test_format_empty_message():
    msg = format_parlay_table([])
    assert "No positive-EV" in msg


def test_format_contains_leg_targets():
    """Table must mention bet targets from each leg."""
    combos = build_parlay_combos(BETS)
    if combos:
        table = format_parlay_table(combos)
        top = combos[0]
        # At least one leg target should appear (truncated to 28 chars)
        label_a = f"{top['leg_a']['target']} ({top['leg_a']['market_type']})"[:28]
        assert label_a in table
