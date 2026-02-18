# TITANIUM V36.1 — Session State
# Paste this into any new Claude Code chat to resume instantly.
# Update the "Current State" section at the end of every session.

---

## PROJECT
Sports betting analysis tool. Fetches live odds, applies math, outputs top-10 bets.
User accesses on iPhone browser each morning.
Working dir: /Users/matthewshields/Projects/titanium-v36
R&D sandbox: /Users/matthewshields/Projects/titanium-experimental (read-only reference)
Hosting: Streamlit Cloud (auto-deploy from GitHub main branch)
API: The Odds API v4 — key in .streamlit/secrets.toml (never commit)

## NON-NEGOTIABLE RULES (enforce in all code)
1. Odds collar: -180 to +150 only. Reject everything outside.
2. Minimum edge: ≥ 3.5% (Titanium prob vs market implied prob)
3. No duplicate markets: never both sides of same bet
4. Kelly: 0.25x fractional. Caps: >60% winprob → 2.0u, >54% → 1.0u, else → 0.5u
5. Kill switches: NBA rest+spread, NFL wind+total, NCAAB 3P+away, Soccer drift

## ARCHITECTURE (one file = one job)
- app.py          → Streamlit UI only
- odds_fetcher.py → API calls only
- edge_calculator.py → Math only
- bet_ranker.py   → Dedup + rank + top-10
- originator_engine.py → Monte Carlo (working, touch only if asked)
- data/team_stats_bunker.py → Static fallback stats

## WHAT'S BUILT AND WORKING (as of Session 2)
- odds_fetcher.py: fetch_batch_odds(sport_key, api_key) — live tested, returns real data
- odds_fetcher.py: _preferred_book() — DraftKings first, fallback to first available
- edge_calculator.py: passes_collar, _implied_probability, no_vig_probability,
  calculate_edge, calculate_profit, fractional_kelly — all implemented + 45 tests passing
- tests/validation_tests.py: 45 tests, all passing
- tests/test_odds_fetcher.py: 20 tests, all passing

## WHAT'S STUBBED (TODO in Session 3+)
- edge_calculator.py: calculate_edges(), all kill switches
- originator_engine.py: run_trinity_simulation(), run_poisson_matrix()
- bet_ranker.py: rank_bets(), _deduplicate_markets(), _apply_diversity()
- app.py: full pipeline wiring

## SESSION 3 GOAL
1. Upgrade odds_fetcher.py: add all_books(), fetch_game_lines(), QuotaTracker, retry logic
2. Port originator_engine.py from R&D (trinity simulation + poisson matrix — working)
3. Build ncaab_parser.py (new file — collar filter + best-price extraction across all books)
4. Wire edge_calculator.parse_game_markets() — multi-book consensus edge detection
5. Live end-to-end pipeline test against real NCAAB data

## EDGE DETECTION METHOD (critical — proven in R&D)
Problem solved: single-book comparison always returns ~0 edge (market prices itself out)
Solution: multi-book consensus
  - Step 1: Collect vig-free probability from each book that has both sides
  - Step 2: Average them → this is the "model probability"
  - Step 3: Find best available price at any single book
  - Step 4: Edge = consensus_prob - implied_probability(best_price)
This works because books occasionally misprice relative to the consensus.

## KNOWN R&D BUGS (do not promote to v36 until fixed)
- Props edge ~0: model_prob uses best_price fair_prob instead of cross-book consensus
- Trinity simulation: receives bet.line as mean input — should be projected margin
- RLM Sharp Score component always returns 0 (no line movement data source yet)

## API FACTS
- Key: 01dc7be6ca076e6b79ac4f54001d142d (in secrets.toml — do not hardcode in code)
- Quota: ~18,350 remaining as of Feb 2026
- fetch_batch_odds = 1 API call per sport
- Soccer bulk: h2h,totals only (btts/h2h_3_way cause 422)
- Props: NOT supported on bulk endpoint — per-event only, 4 calls per game
- NHL/NBA on Olympic break Feb 2026 — sparse coverage is expected

## HOW TO RESUME IN A NEW CHAT
1. Open Claude Code desktop app
2. Navigate to: /Users/matthewshields/Projects/titanium-v36
3. Paste this entire SESSION_STATE.md file into the chat
4. Say: "Resume Session [N]. Read CLAUDE.md and SESSION_STATE.md.
         Run: pytest tests/ -v and confirm all tests pass before we start."
5. Wait for test confirmation, then state what you want to build

## CURRENT STATE
Last completed: Session 2 — odds_fetcher.py live-tested against real NHL/NCAAB data
Last git commit: "Session 1+2 complete: scaffold, math validation, odds fetcher live-tested"
Tests: 65 total (45 math + 20 fetcher), all passing
Next: Session 3 — see SESSION 3 GOAL above
