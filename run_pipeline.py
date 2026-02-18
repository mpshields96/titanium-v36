"""
run_pipeline.py — TITANIUM V36.1
==================================
End-to-end pipeline test script. Session 5/7 deliverable.

Uses calculate_edges() as the single entry point per sport (Session 7).

Run with: python3 run_pipeline.py

NOT imported by app.py — app.py has its own wiring.
This file is for CLI validation only.
"""

from edge_calculator import calculate_edges
from bet_ranker import rank_bets, format_bet_table
from data.efficiency_feed import build_efficiency_data
from odds_fetcher import fetch_game_lines, get_quota_status


def run_full_pipeline(sport: str = "NCAAB") -> None:
    print("=" * 70)
    print(f"TITANIUM V36.1 | FULL PIPELINE TEST — {sport}")
    print("=" * 70)

    print(f"\n[1] Pre-fetching {sport} games for efficiency data...")
    from edge_calculator import _SPORT_ROUTING
    routing = _SPORT_ROUTING.get(sport.upper())
    if routing is None:
        print(f"    Unknown sport '{sport}'. Valid: {sorted(_SPORT_ROUTING.keys())}")
        return
    raw_games = fetch_game_lines(routing["sport_key"])
    print(f"    Games fetched: {len(raw_games)}")

    if not raw_games:
        print("    No games found. Check API key or season schedule.")
        return

    print(f"\n[2] Building efficiency data (KenPom/Barttorvik mock)...")
    eff_data = build_efficiency_data(raw_games)
    known = sum(1 for v in eff_data.values() if v != 8.0)
    print(f"    Games mapped: {len(eff_data)} | Known teams (non-default): {known}")

    print(f"\n[3] Running calculate_edges({sport!r}) — parse + kill switch filter...")
    candidates = calculate_edges(sport, raw_games=raw_games)
    print(f"    Candidates surviving collar + min_edge + kill switches: {len(candidates)}")

    # Surface any FLAG'd bets
    flagged = [b for b in candidates if b.kill_reason]
    if flagged:
        print(f"    Flagged (kept with warning): {len(flagged)}")
        for b in flagged:
            print(f"      {b.matchup} | {b.market_type} | {b.kill_reason}")

    if not candidates:
        print("    No edges found today — market is well-priced. No output.")
        print(f"\n{get_quota_status()}")
        return

    print(f"\n[4] Ranking bets (Sharp Score + nemesis + diversity cap)...")
    ranked = rank_bets(candidates, efficiency_data=eff_data)
    print(f"    Candidates in: {len(candidates)} | Ranked out: {len(ranked)}")

    print(f"\n[5] Output:")
    print(format_bet_table(ranked))

    print(f"\n{get_quota_status()}")
    print("=" * 70)


if __name__ == "__main__":
    run_full_pipeline()
