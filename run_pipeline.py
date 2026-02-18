"""
run_pipeline.py — TITANIUM V36.1
==================================
End-to-end pipeline test script. Session 5 deliverable.

Wires:
  fetch_game_lines → parse_game_markets → build_efficiency_data
  → rank_bets(efficiency_data=...) → format_bet_table

Run with: python3 run_pipeline.py

NOT imported by app.py — app.py has its own wiring.
This file is for CLI validation only.
"""

from odds_fetcher import fetch_game_lines, get_quota_status
from edge_calculator import parse_game_markets
from bet_ranker import rank_bets, format_bet_table
from data.efficiency_feed import build_efficiency_data


def run_full_pipeline(sport_key: str = "basketball_ncaab", sport_label: str = "NCAAB") -> None:
    print("=" * 70)
    print(f"TITANIUM V36.1 | FULL PIPELINE TEST — {sport_label}")
    print("=" * 70)

    print(f"\n[1] Fetching {sport_label} odds (1 API call)...")
    raw_games = fetch_game_lines(sport_key)
    print(f"    Games fetched: {len(raw_games)}")

    if not raw_games:
        print("    No games found. Check API key or season schedule.")
        return

    print(f"\n[2] Building efficiency data (KenPom/Barttorvik mock)...")
    eff_data = build_efficiency_data(raw_games)
    known = sum(1 for v in eff_data.values() if v != 8.0)
    print(f"    Games mapped: {len(eff_data)} | Known teams (non-default): {known}")

    print(f"\n[3] Parsing game markets (consensus edge detection)...")
    all_candidates = []
    for game in raw_games:
        candidates = parse_game_markets(game, sport=sport_label)
        all_candidates.extend(candidates)
    print(f"    BetCandidates with ≥3.5% edge: {len(all_candidates)}")

    if not all_candidates:
        print("    No edges found today — market is well-priced. No output.")
        print(f"\n{get_quota_status()}")
        return

    print(f"\n[4] Ranking bets (Sharp Score + nemesis + diversity cap)...")
    ranked = rank_bets(all_candidates, efficiency_data=eff_data)
    print(f"    Candidates in: {len(all_candidates)} | Ranked out: {len(ranked)}")

    print(f"\n[5] Output:")
    print(format_bet_table(ranked))

    print(f"\n{get_quota_status()}")
    print("=" * 70)


if __name__ == "__main__":
    run_full_pipeline()
