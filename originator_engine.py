"""
originator_engine.py — TITANIUM V36.1
========================================
Monte Carlo simulation engine. Ported from R&D — live-tested and working.

DO NOT MODIFY unless explicitly asked. This file is stable.

Provides:
  run_trinity_simulation() — spread/total cover probability via Trinity weighting
  run_poisson_matrix()     — soccer match outcome probabilities
  simulate_prop()          — player prop over/under probability

Trinity weighting (per V36.1 spec):
  Ceiling scenario (20% weight): optimistic inputs
  Floor scenario   (20% weight): pessimistic inputs
  Median scenario  (60% weight): baseline inputs
  Simulates uncertainty in INPUTS, not just noise in outputs.

Known limitation (flagged, not yet fixed):
  run_trinity_simulation() mean input should be the projected margin from
  the sport module — currently callers sometimes pass bet.line instead.
  Fix tracked in SESSION_STATE.md.
"""

import math
import random
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Base volatility by sport (std dev in points/goals)
# ---------------------------------------------------------------------------

BASE_VOLATILITY = {
    "NBA":    6.5,
    "NCAAB":  8.5,
    "NFL":    10.5,
    "NCAAF":  12.0,
    "NHL":    1.8,
    "MLB":    2.2,
    "SOCCER": 1.1,
}

# Input variance constants (per V36.1 spec)
EFFICIENCY_VARIANCE = 2.5   # ± pts per 100 possessions
PACE_VARIANCE       = 3.0   # ± possessions
REST_VARIANCE       = 1.5   # pts from rest edge
TRAVEL_VARIANCE     = 1.0   # pts from travel
HOME_VARIANCE       = 2.5   # home court pts


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class SimulationResult:
    cover_probability: float    # % of sims where home team covers the line
    over_probability: float     # % of sims where total goes over
    projected_margin: float     # median projected margin (home - away)
    ci_10: float                # 10th percentile margin
    ci_90: float                # 90th percentile margin
    volatility: float           # std dev of simulated margins
    iterations: int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normal_sample(mu: float, sigma: float) -> float:
    """Box-Muller transform — normal sample without scipy dependency."""
    u1 = random.uniform(1e-10, 1.0)
    u2 = random.uniform(0.0, 1.0)
    z = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
    return mu + sigma * z


# ---------------------------------------------------------------------------
# Trinity simulation
# ---------------------------------------------------------------------------

def run_trinity_simulation(
    mean: float,
    sport: str = "NBA",
    line: float = 0.0,
    total_line: Optional[float] = None,
    rest_edge: float = 0.0,
    travel_penalty: float = 0.0,
    home_advantage: float = 0.0,
    iterations: int = 10_000,
    seed: Optional[int] = None,
) -> SimulationResult:
    """
    Trinity Monte Carlo simulation for spread and total cover probability.

    Args:
        mean:           Base projected margin (home minus away, positive = home favoured).
                        IMPORTANT: Pass the projected margin from the sport module,
                        NOT the market spread line. Known caller bug — see module docstring.
        sport:          Sport key for base volatility lookup (e.g. "NBA", "NCAAB").
        line:           Market spread line (e.g. -4.5 means home is -4.5 favourite).
                        Home covers if simulated_margin > -line.
        total_line:     Over/under market line. Pass None to skip total simulation.
        rest_edge:      Rest advantage adjustment in points (positive = home better rested).
        travel_penalty: Travel fatigue penalty in points.
        home_advantage: Home court/field advantage in points.
        iterations:     Monte Carlo iterations (default 10,000).
        seed:           Random seed for reproducibility in tests.

    Returns:
        SimulationResult with cover probability, CI bounds, and volatility.

    Trinity weighting:
        Ceiling (20%): mean + optimistic input noise, tighter vol (x0.85)
        Floor   (20%): mean + pessimistic input noise, wider vol (x1.15)
        Median  (60%): mean + small baseline noise, standard vol
    """
    if seed is not None:
        random.seed(seed)

    base_vol = BASE_VOLATILITY.get(sport.upper(), 8.0)
    situational = rest_edge - travel_penalty + home_advantage
    adjusted_mean = mean + situational

    margins = []
    covers = 0
    overs = 0

    for _ in range(iterations):
        roll = random.random()

        if roll < 0.20:
            # CEILING — optimistic inputs
            eff_noise = abs(_normal_sample(0, EFFICIENCY_VARIANCE))
            pace_noise = abs(_normal_sample(0, PACE_VARIANCE)) * 0.3
            scenario_mean = adjusted_mean + eff_noise + pace_noise
            vol = base_vol * 0.85

        elif roll < 0.40:
            # FLOOR — pessimistic inputs
            eff_noise = -abs(_normal_sample(0, EFFICIENCY_VARIANCE))
            pace_noise = -abs(_normal_sample(0, PACE_VARIANCE)) * 0.3
            scenario_mean = adjusted_mean + eff_noise + pace_noise
            vol = base_vol * 1.15

        else:
            # MEDIAN — baseline (60% of iterations)
            eff_noise = _normal_sample(0, EFFICIENCY_VARIANCE * 0.5)
            scenario_mean = adjusted_mean + eff_noise
            vol = base_vol

        simulated_margin = _normal_sample(scenario_mean, vol)
        margins.append(simulated_margin)

        # Cover: home covers if margin beats the line
        if simulated_margin > -line:
            covers += 1

        # Total: approximate game total from margin + league average
        if total_line is not None:
            league_avg = {
                "NBA": 228.0, "NCAAB": 148.0, "NFL": 45.0,
                "NHL": 6.0,   "MLB": 9.0,     "SOCCER": 2.65,
            }.get(sport.upper(), 200.0)
            simulated_total = league_avg + _normal_sample(0, base_vol * 0.6)
            if simulated_total > total_line:
                overs += 1

    margins.sort()
    n = len(margins)
    ci_10 = margins[int(0.10 * n)]
    ci_90 = margins[int(0.90 * n)]
    median_margin = margins[n // 2]

    variance = sum((m - adjusted_mean) ** 2 for m in margins) / n
    std_dev = math.sqrt(variance)

    return SimulationResult(
        cover_probability=covers / iterations,
        over_probability=overs / iterations if total_line is not None else 0.0,
        projected_margin=median_margin,
        ci_10=ci_10,
        ci_90=ci_90,
        volatility=std_dev,
        iterations=iterations,
    )


# ---------------------------------------------------------------------------
# Poisson matrix — soccer
# ---------------------------------------------------------------------------

def _poisson_pmf(k: int, lam: float) -> float:
    """P(X=k) for Poisson(lambda) using log space for numerical stability."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    log_pmf = k * math.log(lam) - lam - sum(math.log(i) for i in range(1, k + 1))
    return math.exp(log_pmf)


def run_poisson_matrix(
    home_xg: float,
    away_xg: float,
    max_goals: int = 9,
) -> tuple[float, float, float]:
    """
    Build a Poisson probability matrix for soccer match outcomes.

    Args:
        home_xg:   Expected goals for home team (e.g. 1.6).
        away_xg:   Expected goals for away team (e.g. 1.1).
        max_goals: Max goals per team to model (default 9).

    Returns:
        (home_win_prob, draw_prob, away_win_prob) as decimals summing to 1.0.
    """
    home_win = 0.0
    draw = 0.0
    away_win = 0.0

    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            p = _poisson_pmf(h, home_xg) * _poisson_pmf(a, away_xg)
            if h > a:
                home_win += p
            elif h == a:
                draw += p
            else:
                away_win += p

    total = home_win + draw + away_win
    if total > 0:
        home_win /= total
        draw /= total
        away_win /= total

    return home_win, draw, away_win


# ---------------------------------------------------------------------------
# Prop simulation
# ---------------------------------------------------------------------------

def simulate_prop(
    season_avg: float,
    line: float,
    sigma: Optional[float] = None,
    minutes_adj: float = 1.0,
    matchup_factor: float = 1.0,
    iterations: int = 10_000,
) -> tuple[float, float]:
    """
    Simulate a player prop over/under probability via Monte Carlo.

    Args:
        season_avg:     Player's season average for the stat.
        line:           Book's over/under line.
        sigma:          Std dev. Default: 35% of season_avg (NBA-calibrated).
        minutes_adj:    Minutes multiplier (e.g. 0.90 for B2B).
        matchup_factor: DvP multiplier (e.g. 1.10 = favourable matchup).
        iterations:     Monte Carlo iterations.

    Returns:
        (over_prob, under_prob) as decimals summing to 1.0.
    """
    if sigma is None:
        sigma = max(season_avg * 0.35, 1.5)

    adjusted_mean = season_avg * minutes_adj * matchup_factor
    overs = 0

    for _ in range(iterations):
        sim = max(0.0, _normal_sample(adjusted_mean, sigma))
        if sim > line:
            overs += 1

    over_prob = overs / iterations
    return over_prob, 1.0 - over_prob
