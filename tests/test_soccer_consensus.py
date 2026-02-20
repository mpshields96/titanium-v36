"""
tests/test_soccer_consensus.py — TITANIUM V36.1
Tests for data/soccer_consensus.py (GAP 4 fix — 3-outcome vig removal)
"""

import pytest
from data.soccer_consensus import american_to_implied, consensus_fair_prob_3way


# ---------------------------------------------------------------------------
# american_to_implied
# ---------------------------------------------------------------------------

def test_implied_negative_odds():
    # -110 → 110/210 ≈ 0.5238
    assert abs(american_to_implied(-110) - 110/210) < 0.0001


def test_implied_positive_odds():
    # +150 → 100/250 = 0.40
    assert abs(american_to_implied(150) - 0.40) < 0.0001


def test_implied_even_money():
    # +100 → 100/200 = 0.50
    assert abs(american_to_implied(100) - 0.50) < 0.0001


# ---------------------------------------------------------------------------
# consensus_fair_prob_3way — math
# ---------------------------------------------------------------------------

def test_three_way_sums_to_one():
    """fair_home + fair_draw + fair_away must sum to 1.0 (single book)."""
    result = consensus_fair_prob_3way([-120], [+240], [+110])
    total = result["fair_home"] + result["fair_draw"] + result["fair_away"]
    assert abs(total - 1.0) < 0.0001


def test_three_way_multi_book_sums_to_one():
    """Average fair probs should sum to ~1.0 across books."""
    result = consensus_fair_prob_3way(
        [-130, -125, -120],
        [+250, +240, +235],
        [+120, +115, +110],
    )
    total = result["fair_home"] + result["fair_draw"] + result["fair_away"]
    assert abs(total - 1.0) < 0.001


def test_n_books_correct():
    result = consensus_fair_prob_3way(
        [-120, -125],
        [+240, +235],
        [+110, +115],
    )
    assert result["n_books"] == 2


def test_std_dev_zero_single_book():
    """Single book → no dispersion → std_dev = 0.0."""
    result = consensus_fair_prob_3way([-120], [+240], [+110])
    assert result["std_dev"] == 0.0


def test_std_dev_nonzero_multi_book():
    """Different prices across books → std_dev > 0."""
    result = consensus_fair_prob_3way(
        [-150, -110],   # Wide spread — high dispersion
        [+250, +220],
        [+130, +110],
    )
    assert result["std_dev"] > 0


def test_draw_reduces_home_prob():
    """3-way normalization must produce lower fair_home than 2-way."""
    from data.soccer_consensus import american_to_implied

    # Single book: -120 home, +240 draw, +110 away
    imp_h = american_to_implied(-120)
    imp_d = american_to_implied(240)
    imp_a = american_to_implied(110)

    # 2-way: ignores draw
    two_way_home = imp_h / (imp_h + imp_a)

    # 3-way (correct)
    result = consensus_fair_prob_3way([-120], [240], [110])
    three_way_home = result["fair_home"]

    assert three_way_home < two_way_home, (
        f"3-way ({three_way_home:.4f}) should be < 2-way ({two_way_home:.4f})"
    )


def test_home_advantage_reflected():
    """When home is heavy favourite, fair_home > fair_away."""
    result = consensus_fair_prob_3way([-200], [+280], [+350])
    assert result["fair_home"] > result["fair_away"]


# ---------------------------------------------------------------------------
# consensus_fair_prob_3way — validation
# ---------------------------------------------------------------------------

def test_raises_on_empty_input():
    with pytest.raises(ValueError, match="empty"):
        consensus_fair_prob_3way([], [], [])


def test_raises_on_mismatched_lengths():
    with pytest.raises(ValueError):
        consensus_fair_prob_3way([-120, -125], [+240], [+110, +115])


def test_return_keys():
    result = consensus_fair_prob_3way([-120], [+240], [+110])
    for key in ("fair_home", "fair_draw", "fair_away", "std_dev", "n_books"):
        assert key in result, f"Missing key: {key}"
