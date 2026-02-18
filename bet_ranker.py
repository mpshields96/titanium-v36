"""
bet_ranker.py — TITANIUM V36.1
=================================
Diversity engine and final bet selection. No API calls, no math, no UI.

V36.1 NON-NEGOTIABLE RULES:
- No duplicate markets: never both sides of the same bet
- Max 10 bets returned total
- Max 3 bets per sport
- Max 60% of day's action from single sport
- Nemesis protocol applied: remove if counter >40%, penalize if 30-40%
- Final sort: Sharp Score descending

Sharp Score threshold: 45 pts (Session 13).
Rationale: 6% edge with live situational data scores ~38–40; that's too marginal.
45 correctly requires ~7.8% real edge before a bet is promoted.
Next raise → 50–55 after RLM is wired (adds 25 pts to genuine sharp bets).

DO NOT add API calls, betting math, or Streamlit calls to this file.
"""

from typing import Optional

from edge_calculator import (
    BetCandidate,
    calculate_sharp_score,
    run_nemesis,
    sharp_to_size,
)


MAX_TOTAL_BETS = 10
MAX_PER_SPORT = 3                   # V36.1 spec: 3 (not 4)
SPORT_CONCENTRATION_CAP = 0.60      # Max 60% of bets from one sport
SHARP_THRESHOLD = 45.0              # Session 13: raised 40→45. Raise to 50–55 after RLM wired.
SHARP_FLOOR_POST_NEMESIS = 0.0      # No second cutoff — sort handles final ranking


def rank_bets(
    candidates: list[BetCandidate],
    rlm_data: Optional[dict] = None,
    efficiency_data: Optional[dict] = None,
    situational_data: Optional[dict] = None,
) -> list[BetCandidate]:
    """
    Full ranking pipeline per V36.1.

    Steps:
    1. Score each candidate (Sharp Score)
    2. Filter below SHARP_THRESHOLD
    3. Apply nemesis protocol (remove >40% counter, penalise 30-40%)
    4. Deduplicate markets (keep higher edge side)
    5. Sort by sharp_score descending
    6. Apply diversity cap (max 3 per sport, 60% concentration)
    7. Return top 10

    Args:
        candidates:       All BetCandidates passing collar + 3.5% edge.
        rlm_data:         Dict mapping event_id → bool (RLM confirmed).
                          Pass None when no line movement data available.
        efficiency_data:  Dict mapping event_id → float (efficiency gap 0-20).
                          Defaults to 8.0 per game (moderate) when None.
        situational_data: Dict mapping event_id → dict with rest/injury/etc.
                          Defaults to zeros when None.

    Returns:
        Ranked list of up to 10 BetCandidates with sharp_score,
        sharp_breakdown, nemesis, and signal fields populated.
    """
    if not candidates:
        return []

    rlm_data = rlm_data or {}
    efficiency_data = efficiency_data or {}
    situational_data = situational_data or {}

    # --- Step 1: Score all candidates ---
    scored = []
    for bet in candidates:
        rlm = rlm_data.get(bet.event_id, False)
        eff_gap = efficiency_data.get(bet.event_id, 8.0)   # default moderate

        sit = situational_data.get(bet.event_id, {})

        # rest_edge: derived from live schedule rest days when available (NBA only).
        # +3 = rested vs B2B opponent. -3 = B2B vs rested opponent. 0 = neutral/unknown.
        # Formula: (opp_rest - bet_rest) clamped to [-3, +3], scaled to 0-5pt range.
        # This is the only situational input with a live data source.
        live_rest = getattr(bet, "rest_days", None)
        live_opp_rest = getattr(bet, "opp_rest_days", None)
        if live_rest is not None and live_opp_rest is not None:
            rest_delta = live_opp_rest - live_rest   # positive = we're more rested
            rest = max(-3.0, min(3.0, float(rest_delta)))
        else:
            rest = sit.get("rest_edge", 0.0)

        injury = sit.get("injury_leverage", 0.0)
        motivation = sit.get("motivation", 0.0)
        matchup = sit.get("matchup_score", 0.0)

        score, breakdown = calculate_sharp_score(
            edge_pct=bet.edge_pct,
            rlm_confirmed=rlm,
            efficiency_gap=eff_gap,
            rest_edge=rest,
            injury_leverage=injury,
            motivation=motivation,
            matchup_score=matchup,
        )

        bet.sharp_score = score
        bet.sharp_breakdown = breakdown

        if score < SHARP_THRESHOLD:
            continue

        scored.append(bet)

    # --- Step 2: Nemesis — annotation only, no score adjustment ---
    # Nemesis counter-theses are narrative-driven and not mathematically grounded.
    # They are displayed on bet cards for awareness but do NOT affect Sharp Score
    # or remove bets. Edge detection, kill switches, and efficiency gap handle
    # the mathematical filtering. Narrative should not veto math.
    post_nemesis = []
    for bet in scored:
        nemesis = run_nemesis(bet, bet.sport)
        bet.nemesis = nemesis
        # No removal, no score adjustment — annotation only
        post_nemesis.append(bet)

    # --- Step 3: Deduplicate markets ---
    deduped = _deduplicate_markets(post_nemesis)

    # --- Step 4: Sort by sharp score ---
    deduped.sort(key=lambda b: b.sharp_score, reverse=True)

    # --- Step 5: Apply diversity cap ---
    diversified = _apply_diversity(deduped, max_per_sport=MAX_PER_SPORT)

    # --- Step 6: Return top 10 with tier labels ---
    final = diversified[:MAX_TOTAL_BETS]
    for bet in final:
        bet.signal = sharp_to_size(bet.sharp_score, is_prop=(bet.market_type == "prop"))

    return final


def _deduplicate_markets(bets: list[BetCandidate]) -> list[BetCandidate]:
    """
    Remove one side when both sides of the same market appear.
    Rule: keep the side with higher edge_pct.

    Market identity: (event_id, market_type, abs(line))
    Example: Celtics -4.5 and Wizards +4.5 → same market, keep higher edge.
    Moneylines: both ML bets from same game share event_id + "moneyline" + 0.0 → deduped.
    """
    market_groups: dict[tuple, list[BetCandidate]] = {}
    for bet in bets:
        key = (bet.event_id, bet.market_type, round(abs(bet.line), 1))
        market_groups.setdefault(key, []).append(bet)

    result = []
    for group in market_groups.values():
        if len(group) == 1:
            result.append(group[0])
        else:
            result.append(max(group, key=lambda b: b.edge_pct))

    return result


def _apply_diversity(
    bets: list[BetCandidate],
    max_per_sport: int = MAX_PER_SPORT,
) -> list[BetCandidate]:
    """
    Cap each sport at max_per_sport bets.
    Also enforce concentration cap: no sport >60% of final slate.

    Assumes bets are already sorted by sharp_score descending so
    we always drop the lowest-scoring bet when a sport hits its cap.

    Concentration cap only enforced once slate has 5+ bets — at lower
    counts the per-sport cap is the effective guard.
    """
    sport_counts: dict[str, int] = {}
    result = []

    for bet in bets:
        sport = bet.sport
        count = sport_counts.get(sport, 0)

        if count >= max_per_sport:
            continue

        count_after = count + 1
        total_after = len(result) + 1
        if total_after >= 5:
            if count_after / total_after > SPORT_CONCENTRATION_CAP:
                continue

        sport_counts[sport] = count + 1
        result.append(bet)

    return result


def format_bet_table(bets: list[BetCandidate]) -> str:
    """
    Format ranked bets as a CLI/Streamlit-ready string.
    One block per bet with Sharp Score breakdown and nemesis note.
    """
    if not bets:
        return "No bets passed all filters today."

    lines = []
    lines.append("=" * 90)
    lines.append("TITANIUM V36.1 | RANKED BET SLATE")
    lines.append("=" * 90)

    tier_labels = {
        "NUCLEAR_2.0U": "[NUCLEAR]",
        "STANDARD_1.0U": "[STANDARD]",
        "LEAN_0.5U": "[LEAN]",
        "PASS": "[PASS]",
    }

    for i, bet in enumerate(bets, 1):
        tier = sharp_to_size(bet.sharp_score, bet.market_type == "prop")
        label = tier_labels.get(tier, "")

        lines.append(f"\n#{i} {label} {bet.matchup}")
        lines.append(f"   {bet.sport} | {bet.market_type.upper()} | {bet.target}")
        lines.append(f"   Price: {bet.price:+d}  |  Book: {bet.book}")
        lines.append(
            f"   Edge: Model {bet.win_prob:.1%} vs Market {bet.market_implied:.1%}"
            f" | EDGE {bet.edge_pct:+.1%}"
        )
        lines.append(
            f"   Sharp Score: {bet.sharp_score:.0f}/100"
            f" | Edge:{bet.sharp_breakdown.get('edge', 0):.0f}"
            f" RLM:{bet.sharp_breakdown.get('rlm', 0):.0f}"
            f" Eff:{bet.sharp_breakdown.get('efficiency', 0):.0f}"
            f" Sit:{bet.sharp_breakdown.get('situational', 0):.0f}"
        )
        lines.append(f"   Kelly Size: {bet.kelly_size:.2f}u")

        if bet.simulation:
            sim = bet.simulation
            lines.append(
                f"   Monte Carlo: Cover {sim.cover_probability:.1%}"
                f" | CI [{sim.ci_10:+.1f}, {sim.ci_90:+.1f}]"
                f" | Vol {sim.volatility:.1f}"
            )

        if bet.nemesis:
            nem = bet.nemesis
            lines.append(
                f"   Nemesis: {nem.get('counter', '?')}"
                f" | Prob {nem.get('probability', 0):.0%}"
                f" | Adj {nem.get('adjustment', 0):+d}pts"
            )

        if bet.commence_time:
            lines.append(f"   Game time: {bet.commence_time}")

    lines.append("\n" + "=" * 90)
    lines.append(
        f"Total bets: {len(bets)} | Sizes: "
        + ", ".join(f"{b.kelly_size:.2f}u" for b in bets)
    )
    lines.append("=" * 90)

    return "\n".join(lines)
