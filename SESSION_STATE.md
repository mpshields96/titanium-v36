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

## WHAT'S BUILT AND WORKING (as of Session 3)
- odds_fetcher.py: QuotaTracker, _get_api_key(), _get() (retry+errors), all_books(),
  preferred_book(), fetch_game_lines(), fetch_batch_odds() (legacy), fetch_sport(),
  get_quota_status() — live tested 60 NCAAB games, DraftKings present
- edge_calculator.py: passes_collar, _implied_probability, no_vig_probability,
  calculate_edge, calculate_profit, fractional_kelly — 45 tests passing
- edge_calculator.py: BetCandidate dataclass, _consensus_fair_prob(),
  parse_game_markets() — live tested, 0 false positives on well-priced market ✓
- originator_engine.py: run_trinity_simulation(), run_poisson_matrix(),
  simulate_prop() — ported from R&D, full Trinity weighting (20/20/60)
- ncaab_parser.py: parse_ncaab_games() — live tested: 60 games → 280 bets pass collar
- tests/test_validation.py: 45 tests, all passing
- tests/test_odds_fetcher.py: 20 tests, all passing

## WHAT'S BUILT AND WORKING (as of Session 4)
- bet_ranker.py: rank_bets(), _deduplicate_markets(), _apply_diversity(),
  format_bet_table() — promoted from R&D, synthetic test + live pipeline clean
- edge_calculator.py: calculate_sharp_score(), run_nemesis(), sharp_to_size()
  added (ported from R&D). BetCandidate now has sharp_score, sharp_breakdown,
  nemesis, simulation fields.
- Full pipeline live-tested: fetch → parse_game_markets → rank_bets → format_bet_table ✓

## WHAT'S BUILT AND WORKING (as of Session 5, partial)
- data/efficiency_feed.py: get_efficiency_gap(), build_efficiency_data(), get_team_data(),
  list_teams() — promoted from R&D, alias fix applied (Texas Southern Tigers), live tested ✓
- run_pipeline.py: full end-to-end CLI test: fetch → efficiency → edge → rank → format ✓
- PROJECT_INDEX.md: repo index created (94% token reduction for future sessions)

## WHAT'S STUBBED (TODO in Session 5+)
- edge_calculator.py: calculate_edges() routing stub, all kill switch stubs
- app.py: full Streamlit UI wiring

## SESSION 3 GOAL ✅ COMPLETE
1. ✅ Upgrade odds_fetcher.py: all_books(), fetch_game_lines(), QuotaTracker, retry logic
2. ✅ Port originator_engine.py from R&D (trinity simulation + poisson matrix)
3. ✅ Build ncaab_parser.py (collar filter + best-price extraction across all books)
4. ✅ Wire edge_calculator.parse_game_markets() — multi-book consensus edge detection
5. ✅ Live end-to-end pipeline test against real NCAAB data

## EDGE DETECTION METHOD (critical — proven in R&D)
Problem solved: single-book comparison always returns ~0 edge (market prices itself out)
Solution: multi-book consensus
  - Step 1: Collect vig-free probability from each book that has both sides
  - Step 2: Average them → this is the "model probability"
  - Step 3: Find best available price at any single book
  - Step 4: Edge = consensus_prob - implied_probability(best_price)
This works because books occasionally misprice relative to the consensus.

## KNOWN R&D BUGS (do not promote to v36 until fixed)
- Props edge ~0: FIXED in R&D (Feb 2026) — model_prob now uses avg consensus fair_prob
  across all books, same pattern as _consensus_fair_prob(). Ready for Session 4 promotion review.
  Verified: 8 books, 78 props, no false positives, correct distribution.
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

## SESSION 4 GOAL ✅ COMPLETE
1. ✅ Promote bet_ranker.py from R&D (MAX_PER_SPORT=3, threshold=40, Sharp Score sort)
2. ✅ Add calculate_sharp_score, run_nemesis, sharp_to_size to edge_calculator.py
3. ✅ BetCandidate updated with sharp_score/sharp_breakdown/nemesis/simulation fields
4. ✅ Full pipeline live-tested: fetch → edge → rank → format

## CALIBRATION NOTES (important for Session 5)
- Sharp Score threshold: 40 pre-nemesis (temp). Raise to 75 when KenPom/Barttorvik wired.
- Nemesis penalty (-15 pts) is applied but no post-nemesis threshold — sort handles ranking.
- RLM component always 0 — no line movement tracking yet.
- efficiency_gap defaults to 8.0 (moderate) — real values come from KenPom in Session 5.
- Kill switches (nba/nfl/ncaab/soccer) still stubbed — Session 5 work.

## SESSION 5 GOAL (IN PROGRESS)
1. ✅ Promote efficiency_feed.py (KenPom mock) — wired into rank_bets, live tested
2. ✅ PROJECT_INDEX.md created (repo index for 94% token reduction)
3. 🔲 Implement kill switches in edge_calculator.py
4. 🔲 Wire calculate_edges() routing function
5. 🔲 Wire Streamlit app.py: button → fetch → edge → rank → display table
6. 🔲 Mobile view polish (iPhone layout)
7. 🔲 Deployment checklist + push to Streamlit Cloud

## CURRENT STATE
Last completed: Session 5 (partial) — efficiency_feed promoted, run_pipeline.py built, PROJECT_INDEX.md created
Last git commit: pending (commit after updating this file)
Tests: 65 total (45 math + 20 fetcher), all passing
Quota: ~18,322 remaining
Next: Kill switches → calculate_edges() → Streamlit UI → deploy
