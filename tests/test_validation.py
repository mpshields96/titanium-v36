"""
tests/validation_tests.py — TITANIUM V36.1
============================================
Unit tests for all core betting math in edge_calculator.py.

Run with: pytest tests/validation_tests.py -v

All expected values are derived from standard betting math:
- Implied probability:  negative odds → |odds|/(|odds|+100)
                        positive odds → 100/(odds+100)
- No-vig:               raw_p / (raw_p_a + raw_p_b)
- Edge:                 titanium_win_prob - implied_probability(market_odds)
- Kelly:                (b×p − q) / b × fraction, capped per V36.1 rules
- Profit:               positive odds → stake × (odds/100)
                        negative odds → stake × (100/|odds|)
"""

import sys
import os
import pytest

# Allow import from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from edge_calculator import (
    _implied_probability,
    no_vig_probability,
    calculate_edge,
    fractional_kelly,
    calculate_profit,
    passes_collar,
)
from data.kill_switch_feed import (
    get_nba_injury_leverage,
    get_ncaab_injury_leverage,
)
from bet_card_renderer import _consensus_badge_html


# ============================================================================
# 1. IMPLIED PROBABILITY
#    Formula: negative → |odds|/(|odds|+100)   positive → 100/(odds+100)
# ============================================================================

class TestImpliedProbability:
    """Convert American odds to raw (vig-inclusive) implied probability."""

    def test_minus_110_standard_vig_line(self):
        # -110: the most common market line (e.g., spread or total)
        # 110 / (110 + 100) = 110 / 210 = 0.52381
        result = _implied_probability(-110)
        assert abs(result - 0.52381) < 0.00001

    def test_minus_180_heavy_favorite(self):
        # -180: near the collar limit for favorites
        # 180 / (180 + 100) = 180 / 280 = 0.64286
        result = _implied_probability(-180)
        assert abs(result - 0.64286) < 0.00001

    def test_plus_150_near_collar_limit(self):
        # +150: near the collar limit for underdogs
        # 100 / (150 + 100) = 100 / 250 = 0.40000
        result = _implied_probability(150)
        assert abs(result - 0.40000) < 0.00001

    def test_plus_100_even_money(self):
        # +100 (even money): should be exactly 50%
        # 100 / (100 + 100) = 100 / 200 = 0.50000
        result = _implied_probability(100)
        assert abs(result - 0.50000) < 0.00001

    def test_minus_120_common_favorite(self):
        # -120: common short-priced favorite
        # 120 / (120 + 100) = 120 / 220 = 0.54545
        result = _implied_probability(-120)
        assert abs(result - 0.54545) < 0.00001

    def test_plus_130_underdog(self):
        # +130: typical underdog price
        # 100 / (130 + 100) = 100 / 230 = 0.43478
        result = _implied_probability(130)
        assert abs(result - 0.43478) < 0.00001

    def test_minus_200_outside_collar_still_calculates(self):
        # -200: outside collar, but math should still work (collar enforced elsewhere)
        # 200 / (200 + 100) = 200 / 300 = 0.66667
        result = _implied_probability(-200)
        assert abs(result - 0.66667) < 0.00001


# ============================================================================
# 2. NO-VIG PROBABILITY
#    Method: raw_p_a / (raw_p_a + raw_p_b)  for side A (same for side B)
#    Both sides normalised so they sum to exactly 1.0
# ============================================================================

class TestNoVigProbability:
    """Remove bookmaker juice from both sides of a two-outcome market."""

    def test_standard_spread_both_minus_110(self):
        # A -110 / -110 spread is a symmetric market — fair line is 50/50
        # raw_a = raw_b = 110/210 = 0.52381, overround = 1.04762
        # fair = 0.52381 / 1.04762 = 0.50000
        fair_a, fair_b = no_vig_probability(-110, -110)
        assert abs(fair_a - 0.50000) < 0.00001
        assert abs(fair_b - 0.50000) < 0.00001

    def test_probabilities_sum_to_one(self):
        # No matter the odds, the two fair probabilities must sum to exactly 1.0
        fair_a, fair_b = no_vig_probability(-130, 110)
        assert abs(fair_a + fair_b - 1.0) < 0.00001

    def test_minus_130_plus_110_favourite_and_dog(self):
        # -130 / +110 market
        # raw_a = 130/230 = 0.56522, raw_b = 100/210 = 0.47619
        # overround = 1.04141
        # fair_a = 0.56522 / 1.04141 = 0.54277
        # fair_b = 0.47619 / 1.04141 = 0.45723
        fair_a, fair_b = no_vig_probability(-130, 110)
        assert abs(fair_a - 0.54277) < 0.00010
        assert abs(fair_b - 0.45723) < 0.00010

    def test_minus_150_plus_130_asymmetric(self):
        # -150 / +130 market
        # raw_a = 150/250 = 0.60000, raw_b = 100/230 = 0.43478
        # overround = 1.03478
        # fair_a = 0.60000 / 1.03478 = 0.57982
        # fair_b = 0.43478 / 1.03478 = 0.42018
        fair_a, fair_b = no_vig_probability(-150, 130)
        assert abs(fair_a - 0.57982) < 0.00010
        assert abs(fair_b - 0.42018) < 0.00010

    def test_even_money_both_sides(self):
        # +100 / +100: each side is raw 50%, overround = 1.0, fair = 50% each
        fair_a, fair_b = no_vig_probability(100, 100)
        assert abs(fair_a - 0.50000) < 0.00001
        assert abs(fair_b - 0.50000) < 0.00001

    def test_minus_180_plus_150_at_collar_limits(self):
        # Test at the exact collar boundary values
        # raw_a = 180/280 = 0.64286, raw_b = 100/250 = 0.40000
        # overround = 1.04286
        # fair_a = 0.64286 / 1.04286 = 0.61647
        # fair_b = 0.40000 / 1.04286 = 0.38353
        fair_a, fair_b = no_vig_probability(-180, 150)
        assert abs(fair_a + fair_b - 1.0) < 0.00001
        assert fair_a > fair_b  # favorite has higher probability


# ============================================================================
# 3. EDGE CALCULATION
#    Formula: titanium_win_prob - _implied_probability(market_odds)
#    Positive edge = Titanium has an advantage over the market
# ============================================================================

class TestCalculateEdge:
    """Edge = Titanium's estimated win prob minus the market's implied prob."""

    def test_positive_edge_classic_example(self):
        # Titanium says 55% win prob, market at -110 implies 52.38%
        # Edge = 0.5500 - 0.52381 = 0.02619
        result = calculate_edge(0.55, -110)
        assert abs(result - 0.02619) < 0.00001

    def test_zero_edge_no_advantage(self):
        # Titanium agrees exactly with the market — zero edge
        # Market: -110 → 52.381%. Titanium also says 52.381%
        result = calculate_edge(0.52381, -110)
        assert abs(result) < 0.00001

    def test_negative_edge_market_has_advantage(self):
        # Titanium says 48%, market at -110 implies 52.38%
        # Edge = 0.48 - 0.52381 = -0.04381 (we're the sucker here)
        result = calculate_edge(0.48, -110)
        assert abs(result - (-0.04381)) < 0.00001

    def test_edge_at_plus_odds(self):
        # Titanium says 45% win prob, market at +130 implies 43.48%
        # Edge = 0.45 - 0.43478 = 0.01522
        result = calculate_edge(0.45, 130)
        assert abs(result - 0.01522) < 0.00010

    def test_edge_passes_minimum_threshold(self):
        # V36.1 rule: edge must be >= 3.5% (0.035) to place a bet
        # 57% Titanium vs -110 market (52.38%) = 4.62% edge — should pass
        result = calculate_edge(0.57, -110)
        assert result >= 0.035

    def test_edge_fails_minimum_threshold(self):
        # 54% Titanium vs -110 market (52.38%) = 1.62% edge — should fail the 3.5% rule
        result = calculate_edge(0.54, -110)
        assert result < 0.035

    def test_large_edge_underdog_spot(self):
        # Titanium says 50% win prob for a team at +150 (market implies 40%)
        # Edge = 0.50 - 0.40 = 0.10 — strong edge on an underdog
        result = calculate_edge(0.50, 150)
        assert abs(result - 0.10) < 0.00001


# ============================================================================
# 4. NO-VIG PROBABILITY (additional edge-case tests)
#    Tested above in class TestNoVigProbability — additional tests here
#    focus on the overround (juice) being correctly identified
# ============================================================================

class TestNoVigOverround:
    """Verify the overround (total implied probability > 100%) is correct."""

    def test_standard_spread_overround_is_about_4_76_pct(self):
        # -110 / -110 standard spread: overround = 110/210 + 110/210 = 1.04762
        raw_a = 110 / 210
        raw_b = 110 / 210
        overround = raw_a + raw_b
        assert abs(overround - 1.04762) < 0.00001

    def test_fair_probs_sum_to_1_various_markets(self):
        markets = [
            (-110, -110),
            (-120, 100),
            (-150, 130),
            (-180, 150),
            (-130, 110),
        ]
        for odds_a, odds_b in markets:
            fair_a, fair_b = no_vig_probability(odds_a, odds_b)
            assert abs(fair_a + fair_b - 1.0) < 0.00001, (
                f"Failed for market {odds_a}/{odds_b}: sum={fair_a + fair_b}"
            )

    def test_larger_favorite_has_higher_fair_prob(self):
        # In every valid market the favourite's fair prob must exceed the dog's
        fair_fav, fair_dog = no_vig_probability(-150, 130)
        assert fair_fav > fair_dog


# ============================================================================
# 5. KELLY SIZING
#    Formula: ((b × p) - q) / b × fraction, then capped per V36.1 rules
#    b = decimal_odds - 1,  q = 1 - win_prob
# ============================================================================

class TestFractionalKelly:
    """Fractional Kelly bet sizing with V36.1 caps."""

    def test_55_pct_at_minus_110_baseline(self):
        # decimal = 100/110 + 1 = 1.90909
        # b = 0.90909, q = 0.45
        # full_kelly = (0.90909 × 0.55 - 0.45) / 0.90909
        #            = (0.50000 - 0.45) / 0.90909
        #            = 0.05000 / 0.90909 = 0.05500
        # fractional = 0.05500 × 0.25 = 0.01375
        # win_prob 0.55 is NOT > 0.60 and NOT > 0.54, so cap is 0.5 units
        # 0.01375 < 0.5, so result = 0.01375
        result = fractional_kelly(0.55, -110)
        assert abs(result - 0.01375) < 0.00010

    def test_50_pct_at_plus_100_zero_edge_bet(self):
        # decimal = 2.0, b = 1.0, q = 0.5
        # full_kelly = (1.0 × 0.5 - 0.5) / 1.0 = 0.0
        # fractional = 0.0 × 0.25 = 0.0
        # Kelly correctly recommends zero units on a break-even bet
        result = fractional_kelly(0.50, 100)
        assert abs(result - 0.0) < 0.00001

    def test_65_pct_win_prob_triggers_nuclear_cap(self):
        # win_prob > 0.60 → max 2.0 units
        # If Kelly formula returns > 2.0, result must be capped at 2.0
        # Use a high win_prob and good odds to produce a large raw Kelly
        result = fractional_kelly(0.65, -110)
        assert result <= 2.0

    def test_57_pct_win_prob_triggers_standard_cap(self):
        # 0.54 < win_prob <= 0.60 → max 1.0 unit
        result = fractional_kelly(0.57, -110)
        assert result <= 1.0

    def test_52_pct_win_prob_triggers_lean_cap(self):
        # win_prob <= 0.54 → max 0.5 units
        result = fractional_kelly(0.52, -110)
        assert result <= 0.5

    def test_positive_odds_kelly_calculation(self):
        # 55% win prob at +130
        # decimal = 130/100 + 1 = 2.30, b = 1.30, q = 0.45
        # full_kelly = (1.30 × 0.55 - 0.45) / 1.30
        #            = (0.715 - 0.45) / 1.30
        #            = 0.265 / 1.30 = 0.20385
        # fractional = 0.20385 × 0.25 = 0.05096
        # 0.55 is not > 0.60 and not > 0.54 → cap 0.5; 0.05096 < 0.5 → 0.05096
        result = fractional_kelly(0.55, 130)
        assert abs(result - 0.05096) < 0.00010

    def test_negative_kelly_returns_negative_or_zero(self):
        # If Titanium's prob < implied prob, Kelly is negative (do not bet)
        # 40% win prob at -110 (implied 52.38%): we have no edge
        # full_kelly = (0.90909 × 0.40 - 0.60) / 0.90909
        #            = (0.36364 - 0.60) / 0.90909 = -0.26000
        # fractional = -0.26 × 0.25 = -0.065 — negative means no bet
        result = fractional_kelly(0.40, -110)
        assert result < 0  # caller is responsible for filtering negatives


# ============================================================================
# 6. PROFIT CALCULATION
#    Positive odds: profit = stake × (odds / 100)
#    Negative odds: profit = stake × (100 / |odds|)
# ============================================================================

class TestCalculateProfit:
    """Profit for a winning bet (excludes returned stake)."""

    def test_plus_150_on_100_dollar_stake(self):
        # +150 on $100: profit = 100 × (150/100) = $150.00
        result = calculate_profit(100, 150)
        assert abs(result - 150.00) < 0.01

    def test_minus_110_on_110_dollar_stake(self):
        # -110 on $110: profit = 110 × (100/110) = $100.00
        result = calculate_profit(110, -110)
        assert abs(result - 100.00) < 0.01

    def test_minus_110_on_100_dollar_stake(self):
        # -110 on $100: profit = 100 × (100/110) = $90.91
        result = calculate_profit(100, -110)
        assert abs(result - 90.91) < 0.01

    def test_plus_100_even_money(self):
        # +100 on $100: profit = 100 × (100/100) = $100.00
        result = calculate_profit(100, 100)
        assert abs(result - 100.00) < 0.01

    def test_plus_200_long_shot(self):
        # +200 on $50: profit = 50 × (200/100) = $100.00
        result = calculate_profit(50, 200)
        assert abs(result - 100.00) < 0.01

    def test_minus_180_heavy_favorite(self):
        # -180 on $180: profit = 180 × (100/180) = $100.00
        result = calculate_profit(180, -180)
        assert abs(result - 100.00) < 0.01

    def test_minus_120_on_100_dollar_stake(self):
        # -120 on $100: profit = 100 × (100/120) = $83.33
        result = calculate_profit(100, -120)
        assert abs(result - 83.33) < 0.01


# ============================================================================
# 7. ODDS COLLAR
#    Rule: -180 <= american_odds <= +150 only
# ============================================================================

class TestPassesCollar:
    """Odds collar enforces the -180 to +150 range."""

    def test_minus_110_passes(self):
        assert passes_collar(-110) is True

    def test_plus_150_exact_limit_passes(self):
        assert passes_collar(150) is True

    def test_minus_180_exact_limit_passes(self):
        assert passes_collar(-180) is True

    def test_plus_151_just_outside_fails(self):
        assert passes_collar(151) is False

    def test_minus_181_just_outside_fails(self):
        assert passes_collar(-181) is False

    def test_plus_200_far_outside_fails(self):
        assert passes_collar(200) is False

    def test_minus_200_far_outside_fails(self):
        assert passes_collar(-200) is False

    def test_even_money_plus_100_passes(self):
        assert passes_collar(100) is True


# ============================================================================
# 8. INJURY LEVERAGE STUBS
#    Both stubs must return (0.0, False) — no live data source wired yet.
#    data_live=False is the gate for "Data unavailable" display in UI.
# ============================================================================

class TestInjuryLeverageStubs:
    """Injury leverage stubs return neutral values with data_live=False."""

    def test_nba_stub_returns_zero_leverage(self):
        leverage, _ = get_nba_injury_leverage("Boston Celtics", "New York Knicks")
        assert leverage == 0.0

    def test_nba_stub_data_live_is_false(self):
        _, data_live = get_nba_injury_leverage("Boston Celtics", "New York Knicks")
        assert data_live is False

    def test_ncaab_stub_returns_zero_leverage(self):
        leverage, _ = get_ncaab_injury_leverage("Duke", "UConn")
        assert leverage == 0.0

    def test_ncaab_stub_data_live_is_false(self):
        _, data_live = get_ncaab_injury_leverage("Duke", "UConn")
        assert data_live is False


# ============================================================================
# 9. CONSENSUS BADGE THRESHOLDS
#    std_dev < 0.02  → TIGHT (books agree)
#    std_dev 0.02–0.04 → MODERATE
#    std_dev > 0.04  → WIDE (books disagree)
#    std_dev == 0.0  → empty string (unknown)
# ============================================================================

class TestConsensusBadge:
    """_consensus_badge_html() renders correct tier labels at threshold boundaries."""

    def test_tight_threshold_below_002(self):
        html = _consensus_badge_html(0.01)
        assert "TIGHT" in html

    def test_wide_threshold_above_004(self):
        html = _consensus_badge_html(0.05)
        assert "WIDE" in html

    def test_moderate_at_midpoint(self):
        html = _consensus_badge_html(0.03)
        assert "MODERATE" in html

    def test_zero_std_dev_returns_empty(self):
        html = _consensus_badge_html(0.0)
        assert html == ""


# ============================================================================
# 10. NHL EFFICIENCY DATA
#     All 32 NHL franchises in efficiency_feed.py.
#     get_efficiency_gap() returns float in [0, 20] for NHL matchups.
#     list_teams("NHL") returns exactly 32 entries.
# ============================================================================

class TestNHLEfficiency:
    """NHL efficiency data coverage and gap calculation."""

    def test_nhl_gap_returns_valid_float(self):
        from data.efficiency_feed import get_efficiency_gap
        gap = get_efficiency_gap("Florida Panthers", "San Jose Sharks")
        assert isinstance(gap, float)
        assert 0.0 <= gap <= 20.0

    def test_nhl_list_teams_returns_32(self):
        from data.efficiency_feed import list_teams
        nhl_teams = list_teams("NHL")
        assert len(nhl_teams) == 32


# ============================================================================
# 11. MLB / MLS / NFL EFFICIENCY DATA (Session 19 promotion)
#     30 MLB franchises (ERA proxy), 30 MLS clubs (xGD/90 proxy),
#     32 NFL franchises (EPA proxy). Team counts + gap range checks.
#     Alias collision checks: Hawks→NBA, Rangers→NHL, Panthers→NHL.
# ============================================================================

class TestNewLeaguesEfficiency:
    """MLB, MLS, NFL efficiency data coverage and alias collision guards."""

    def test_mlb_list_teams_returns_30(self):
        from data.efficiency_feed import list_teams
        assert len(list_teams("MLB")) == 30

    def test_mls_list_teams_returns_30(self):
        from data.efficiency_feed import list_teams
        assert len(list_teams("MLS")) == 30

    def test_nfl_list_teams_returns_32(self):
        from data.efficiency_feed import list_teams
        assert len(list_teams("NFL")) == 32

    def test_mlb_gap_returns_valid_float(self):
        from data.efficiency_feed import get_efficiency_gap
        gap = get_efficiency_gap("Los Angeles Dodgers", "Colorado Rockies")
        assert isinstance(gap, float)
        assert 0.0 <= gap <= 20.0

    def test_mls_gap_returns_valid_float(self):
        from data.efficiency_feed import get_efficiency_gap
        gap = get_efficiency_gap("Inter Miami CF", "Chicago Fire")
        assert isinstance(gap, float)
        assert 0.0 <= gap <= 20.0

    def test_nfl_gap_returns_valid_float(self):
        from data.efficiency_feed import get_efficiency_gap
        gap = get_efficiency_gap("Kansas City Chiefs", "Chicago Bears")
        assert isinstance(gap, float)
        assert 0.0 <= gap <= 20.0

    def test_hawks_alias_resolves_to_nba_not_nhl(self):
        from data.efficiency_feed import get_team_data
        data = get_team_data("Hawks")
        assert data is not None
        assert data["league"] == "NBA"

    def test_rangers_alias_resolves_to_nhl_not_mlb(self):
        from data.efficiency_feed import get_team_data
        data = get_team_data("Rangers")
        assert data is not None
        assert data["league"] == "NHL"

    def test_panthers_alias_resolves_to_nhl_not_nfl(self):
        from data.efficiency_feed import get_team_data
        data = get_team_data("Panthers")
        assert data is not None
        assert data["league"] == "NHL"

    def test_cardinals_alias_resolves_to_mlb_not_nfl(self):
        from data.efficiency_feed import get_team_data
        data = get_team_data("Cardinals")
        assert data is not None
        assert data["league"] == "MLB"

    def test_nfl_jets_explicit_alias(self):
        from data.efficiency_feed import get_team_data
        data = get_team_data("NY Jets")
        assert data is not None
        assert data["league"] == "NFL"


# ============================================================================
# Calibration mode — rank_bets() sub-threshold retry (V37 R4)
#
# Formula reference (no RLM, no situational, default efficiency_gap=8.0):
#   score = (edge_pct / 0.10) × 40 + 8.0
#   edge_pct=9.5% → score=46 (above SHARP_THRESHOLD=45, production)
#   edge_pct=8.5% → score=42 (below 45 but above calibration_threshold=40)
#   edge_pct=7.0% → score=36 (below even calibration_threshold=40)
# ============================================================================

class TestCalibrationMode:
    """Tests for rank_bets() calibration retry when zero bets pass threshold."""

    def _make_bet(self, edge_pct: float, event_id: str = "evt1") -> "BetCandidate":
        from edge_calculator import BetCandidate
        return BetCandidate(
            sport="NBA",
            matchup="Team A @ Team B",
            market_type="spread",
            target="Team A -4.5",
            line=-4.5,
            price=-110,
            edge_pct=edge_pct,
            win_prob=0.55,
            market_implied=0.524,
            fair_implied=0.55,
            kelly_size=0.5,
            event_id=event_id,
        )

    def test_calibration_flag_set_on_sub_threshold_bets(self):
        """Bets in [40, 45) range returned with calibration=True when no bets pass threshold."""
        from bet_ranker import rank_bets
        # edge_pct=8.5% → score=42, which is below SHARP_THRESHOLD=45 but above calibration_threshold=40
        bet = self._make_bet(edge_pct=0.085)
        results = rank_bets([bet], calibration_threshold=40.0)
        assert len(results) == 1
        assert results[0].calibration is True

    def test_calibration_not_triggered_when_production_bets_pass(self):
        """When a bet scores >= SHARP_THRESHOLD, no calibration retry occurs."""
        from bet_ranker import rank_bets
        # edge_pct=9.5% → score=46, passes SHARP_THRESHOLD=45
        bet = self._make_bet(edge_pct=0.095)
        results = rank_bets([bet], calibration_threshold=40.0)
        assert len(results) == 1
        assert results[0].calibration is False

    def test_calibration_disabled_when_threshold_none(self):
        """calibration_threshold=None → empty list when no production bets pass."""
        from bet_ranker import rank_bets
        bet = self._make_bet(edge_pct=0.085)  # score=42, below threshold
        results = rank_bets([bet], calibration_threshold=None)
        assert results == []

    def test_calibration_empty_when_below_calibration_floor(self):
        """No bets returned if all candidates score below calibration_threshold too."""
        from bet_ranker import rank_bets
        # edge_pct=7.0% → score=36, below calibration_threshold=40
        bet = self._make_bet(edge_pct=0.070)
        results = rank_bets([bet], calibration_threshold=40.0)
        assert results == []

    def test_calibration_false_on_default_betcandidate(self):
        """BetCandidate.calibration defaults to False."""
        from edge_calculator import BetCandidate
        bet = self._make_bet(edge_pct=0.10)
        assert bet.calibration is False

    def test_mixed_bets_production_wins_no_calibration_retry(self):
        """When one bet passes threshold and one doesn't, no calibration retry runs."""
        from bet_ranker import rank_bets
        passing = self._make_bet(edge_pct=0.095, event_id="evt1")  # score=46
        failing = self._make_bet(edge_pct=0.085, event_id="evt2")  # score=42
        results = rank_bets([passing, failing], calibration_threshold=40.0)
        # Only the passing bet should appear, with calibration=False
        assert len(results) == 1
        assert results[0].event_id == "evt1"
        assert results[0].calibration is False


# ============================================================================
# NHL kill switch — nhl_kill_switch() (V37 R4)
# ============================================================================

class TestNHLKillSwitch:
    """Tests for nhl_kill_switch() in edge_calculator.py."""

    def test_backup_goalie_kills(self):
        from edge_calculator import nhl_kill_switch
        killed, reason = nhl_kill_switch(backup_goalie=True)
        assert killed is True
        assert "KILL" in reason

    def test_confirmed_starter_passes(self):
        from edge_calculator import nhl_kill_switch
        killed, reason = nhl_kill_switch(backup_goalie=False, goalie_confirmed=True)
        assert killed is False
        assert reason == ""

    def test_b2b_flags_not_kills(self):
        from edge_calculator import nhl_kill_switch
        killed, reason = nhl_kill_switch(backup_goalie=False, b2b=True)
        assert killed is False
        assert "FLAG" in reason

    def test_goalie_unconfirmed_flags_not_kills(self):
        from edge_calculator import nhl_kill_switch
        killed, reason = nhl_kill_switch(backup_goalie=False, goalie_confirmed=False)
        assert killed is False
        assert "FLAG" in reason

    def test_backup_beats_b2b_priority(self):
        """backup_goalie=True kills even when b2b=True (backup is stronger signal)."""
        from edge_calculator import nhl_kill_switch
        killed, reason = nhl_kill_switch(backup_goalie=True, b2b=True)
        assert killed is True

    def test_all_false_returns_clean(self):
        from edge_calculator import nhl_kill_switch
        killed, reason = nhl_kill_switch(backup_goalie=False, b2b=False, goalie_confirmed=True)
        assert killed is False
        assert reason == ""

    def test_return_is_tuple(self):
        from edge_calculator import nhl_kill_switch
        result = nhl_kill_switch(backup_goalie=False)
        assert isinstance(result, tuple)
        assert len(result) == 2


# ============================================================================
# SPECULATIVE tier — sharp_to_size() + kelly cap (V37 R4)
# ============================================================================

class TestSpeculativeTier:
    """Tests for SPECULATIVE_0.25U tier: sharp_to_size() and kelly hard cap."""

    def _make_bet(self, edge_pct: float, event_id: str = "evt1") -> "BetCandidate":
        from edge_calculator import BetCandidate
        return BetCandidate(
            sport="NBA",
            matchup="Team A @ Team B",
            market_type="spread",
            target="Team A -4.5",
            line=-4.5,
            price=-110,
            edge_pct=edge_pct,
            win_prob=0.55,
            market_implied=0.524,
            fair_implied=0.55,
            kelly_size=0.5,
            event_id=event_id,
        )

    def test_sharp_to_size_returns_speculative_for_score_40(self):
        """Score exactly at calibration floor returns SPECULATIVE_0.25U."""
        from edge_calculator import sharp_to_size
        assert sharp_to_size(40.0) == "SPECULATIVE_0.25U"

    def test_sharp_to_size_returns_speculative_for_score_42(self):
        """Score in [40, 45) range returns SPECULATIVE_0.25U."""
        from edge_calculator import sharp_to_size
        assert sharp_to_size(42.5) == "SPECULATIVE_0.25U"

    def test_sharp_to_size_returns_lean_at_threshold(self):
        """Score exactly at SHARP_THRESHOLD=45 returns LEAN_0.5U (not SPECULATIVE)."""
        from edge_calculator import sharp_to_size
        assert sharp_to_size(45.0) == "LEAN_0.5U"

    def test_sharp_to_size_speculative_boundary_just_below_threshold(self):
        """Score at 44.9 is still SPECULATIVE_0.25U."""
        from edge_calculator import sharp_to_size
        assert sharp_to_size(44.9) == "SPECULATIVE_0.25U"

    def test_speculative_bets_kelly_capped_at_025(self):
        """rank_bets() hard caps kelly_size at 0.25 for speculative bets."""
        from bet_ranker import rank_bets
        # edge_pct=8.5% → score=42, calibration retry. Original kelly_size=0.5 must be capped.
        bet = self._make_bet(edge_pct=0.085)
        results = rank_bets([bet], calibration_threshold=40.0)
        assert len(results) == 1
        assert results[0].kelly_size <= 0.25

    def test_speculative_bets_signal_label_is_speculative(self):
        """Speculative bets get SPECULATIVE_0.25U signal label from sharp_to_size."""
        from bet_ranker import rank_bets
        from edge_calculator import sharp_to_size
        bet = self._make_bet(edge_pct=0.085)
        results = rank_bets([bet], calibration_threshold=40.0)
        assert len(results) == 1
        assert sharp_to_size(results[0].sharp_score) == "SPECULATIVE_0.25U"

    def test_production_bets_kelly_not_capped(self):
        """Production bets (score ≥45) keep their original kelly_size — not capped to 0.25."""
        from bet_ranker import rank_bets
        # edge_pct=9.5% → score=46, passes SHARP_THRESHOLD=45
        bet = self._make_bet(edge_pct=0.095)
        results = rank_bets([bet], calibration_threshold=40.0)
        assert len(results) == 1
        # kelly_size should NOT be capped — original value (0.5) or re-computed full size
        assert results[0].kelly_size > 0.25
