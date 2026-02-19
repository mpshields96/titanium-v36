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

## WHAT'S BUILT AND WORKING (as of Session 6, partial)
- edge_calculator.py: all 4 kill switches implemented — nba/nfl/ncaab/soccer_kill_switch
  all return tuple[bool, str], spec rules + extended rules, verified test cases pass
- data/kill_switch_feed.py: stub input layer for all 4 kill switches
  NBA rest/pace, NFL wind, NCAAB 3PT/tempo, Soccer drift computed at runtime
  Same pattern as efficiency_feed — data_live flag gates UI display

## WHAT'S BUILT AND WORKING (as of Session 7)
- edge_calculator.py: calculate_edges(sport, raw_games, louisiana_mode, min_edge) — Session 7
  Main pipeline entry point: fetch → parse → kill switch → return live candidates
  12 sports routed. BetCandidate.kill_reason field added (FLAG/KILL tagging)
- run_pipeline.py: updated to use calculate_edges() as single entry point — live tested ✓
  76 NCAAB games, kill switch routing clean, 0 false crashes

## WHAT'S BUILT AND WORKING (as of Session 8)
- app.py: full Streamlit UI — "Military Intelligence Terminal" aesthetic
  Dark theme (#0A0A0F), JetBrains Mono, amber accent (#F59E0B)
  Sport selector grouped checkboxes, EXECUTE button, progress per sport
  Bet cards: NUCLEAR/STANDARD/LEAN tier color coded, nemesis block, FLAG badges
  Error states: missing API key, fetch error, 0 edges (neutral message)
  Quota status footer, st.session_state for result persistence

## WHAT'S BUILT AND WORKING (as of Session 9)
- data/efficiency_feed.py: all 30 NBA franchises added (NetRtg×2.2 → AdjEM equivalent)
  54 total teams (30 NBA + 24 NCAAB). league field on every entry.
  list_teams(league=None) accepts optional "NBA" or "NCAAB" filter.
- data/kill_switch_feed.py: full 30-team NBA rest/pace coverage (was 15)
  Full 32-team NFL stadium wind map (was 14). Indoor stubs 2mph, cold-weather correct.
- odds_fetcher.py: cache_open_prices(), get_open_price(), clear_open_price_cache()
  Session-start price cache for soccer drift detection. Zero API cost.
- app.py: UI redesign — "Precision Instrument" aesthetic
  Background softened to #0D1117. Font: IBM Plex Mono.
  TITANIUM header bug fixed (letters as individual spans — no letter-spacing wrap).
  Sport chips restyled. Well-priced neutral card. Cleaner bet cards.

## WHAT'S BUILT AND WORKING (as of Session 10)
- data/efficiency_feed.py: NCAAB expanded 24 → 80 teams (Session 10)
  ACC (17), Big 12 (13), Big Ten (14), SEC (14), Big East (8), WCC/MWC/A-10 (11), low-major (3)
  Full mascot-name aliases for all 80 teams. 110 total (30 NBA + 80 NCAAB).
  Unknown teams still fall back to _DEFAULT_GAP (8.0). Drop-in replacement, no API changes.

## WHAT'S BUILT AND WORKING (as of Session 11)
- odds_fetcher.py: compute_rest_days_from_schedule(raw_games) → dict[str, int | None]
  Derives live rest days from commence_time diffs. Zero extra API calls.
  int = rest days before next game (0 = B2B). None = 1 game in window → stub fallback.
- edge_calculator.py: _apply_nba_kill(bet, schedule_rest=None)
  Accepts optional schedule_rest dict. Overlays live rest/B2B data when both teams present.
  Falls back to kill_switch_feed stub when schedule_rest=None or team has None rest value.
  calculate_edges("NBA") automatically derives + passes schedule_rest. Zero code change in app.py.
- app.py: st.navigation() + st.Page() multi-page scaffold
  4 pages: Live Analysis (fully functional), Bet History, P&L Tracker, Odds Comparison (stubs).
  Live Analysis is default page. No functionality broken. Sidebar hidden as before.

## WHAT'S STUBBED (TODO)
- Streamlit Cloud deploy: DONE (auto-deploys from main branch push)

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

## SESSION 5–7 GOALS ✅ ALL COMPLETE
1. ✅ Promote efficiency_feed.py — wired into rank_bets, live tested
2. ✅ PROJECT_INDEX.md created (repo index for 94% token reduction)
3. ✅ Kill switches implemented in edge_calculator.py (Session 6)
4. ✅ data/kill_switch_feed.py promoted (Session 6)
5. ✅ calculate_edges() — main pipeline entry point (Session 7)
6. ✅ Wire Streamlit app.py — mobile-first UI, dark terminal aesthetic (Session 8)
7. ✅ Mobile view polish — max 720px, flex wrap, iPhone-safe (Session 8)
8. 🔲 Streamlit Cloud deploy — pending user action at share.streamlit.io

## SESSION 9 GOAL ✅ COMPLETE
1. ✅ efficiency_feed.py: all 30 NBA franchises added (NetRtg×2.2, league field, list_teams filter)
2. ✅ kill_switch_feed.py: full 30-team NBA rest/pace coverage
3. ✅ kill_switch_feed.py: full 32-team NFL stadium wind map
4. ✅ Soccer drift: cache_open_prices() added to odds_fetcher.py (zero API cost pattern)
5. ✅ app.py: UI redesign — Precision Instrument aesthetic, header bug fixed, softer bg

## SESSION 10 GOAL ✅ COMPLETE
1. ✅ efficiency_feed.py: NCAAB expanded 24 → 80 teams (ACC/Big 12/Big Ten/SEC/Big East/WCC/MWC/A-10)
2. 🔲 Architecture advisory: commence_time diffs for NBA rest days (R&D researched, v36 code TBD)
3. 🔲 Multi-page planning: st.navigation() + st.Page() structure for future expansion

## SESSION 11 GOAL ✅ COMPLETE
1. ✅ NBA rest days: compute_rest_days_from_schedule() in odds_fetcher.py
     Derives live rest from commence_time diffs. None = stub fallback. Zero extra API calls.
2. ✅ Wire into _apply_nba_kill(): optional schedule_rest param, overlays live data over stubs.
     calculate_edges("NBA") auto-computes + passes schedule_rest. No app.py changes required.
3. ✅ Multi-page scaffold: st.navigation() + st.Page() in app.py
     Live Analysis (working), Bet History / P&L Tracker / Odds Comparison (stubs).
     All 75 tests passing.

## SESSION 13 GOAL (NEXT)
1. 🔲 TBD — user to define

## WHAT'S BUILT AND WORKING (as of Session 12)
- bet_ranker.py: Nemesis demoted to display-only annotation. No score adjustment, no removal.
  Math (edge, efficiency, kill switches) is the sole filter. Narrative never vetoes math.
- bet_ranker.py: rest_edge wired into Sharp Score situational component for NBA.
  Derived from bet.rest_days / bet.opp_rest_days (live schedule data from Session 11).
  Formula: (opp_rest - bet_rest) clamped [-3, +3]. Rested vs B2B opp = +3pts. B2B vs rested = -3pts.
- data/kill_switch_feed.py: NCAAB 3PT reliance expanded from 24 → 80 teams (matches efficiency_feed).
  _NCAAB_TEMPO dict removed — tempo now sourced live from efficiency_feed.get_team_data(). No duplicate data.
- CLAUDE.md: Model Philosophy section added. Math > Narrative is now a permanent documented rule.

## WHAT'S BUILT AND WORKING (as of Session 13)
- bet_ranker.py: SHARP_THRESHOLD raised 40 → 45.
  Rationale: 6% edge with live situational data scores ~38–40 — too marginal to promote.
  45 correctly requires ~7.8% real edge. Next raise: 50–55 after RLM wired.
- odds_fetcher.py: compute_rlm(games) → dict[event_id, bool].
  Passive RLM detection. Zero API calls. Uses _OPEN_PRICE_CACHE baseline from cache_open_prices().
  Threshold: 3% implied probability shift (not raw cents — R&D validated Feb 2026).
  Public side heuristic: price < -105 = favourite = public is on that side.
  Pick-em games (neither side < -105) → no RLM signal.
- app.py: run_pipeline() now pre-fetches raw_games explicitly, calls cache_open_prices() + compute_rlm()
  on each sport, passes rlm_data to rank_bets(). calculate_edges() receives pre-fetched raw_games
  (no double API call). One API call per sport, as before.
- tests/test_odds_fetcher.py: 10 new compute_rlm() tests. 85 total, all passing.

## CURRENT STATE
Last completed: Session 13 — threshold 40→45, passive RLM wired end-to-end
Last git commit: 9fb28e5 (PROJECT_INDEX.md refresh — all Sessions 11–13 committed)
Tests: 85 total, all passing
Quota: ~18,307 remaining (no API calls this session)
Streamlit Cloud: deployed, auto-deploys from main
Next: Session 14 — TBD

## ORIENTATION (read this first in any new session)
1. Read PROJECT_INDEX.md — 229 lines, covers all modules, functions, Sharp Score formula, kill switches, test counts. 94% token reduction vs reading all source files.
2. Run: python3 -m pytest tests/ -v — confirm 85/85 before touching anything.
3. Then read SESSION_STATE.md CHECKPOINT block for exact system state.

## CHECKPOINT — Session 13 (2026-02-18)
State: CLEAN. All code committed. 85/85 tests green.

### Sharp Score formula (as implemented — memorise this)
  score = edge_pts(0-40) + rlm_pts(0-25) + efficiency_pts(0-20) + situational_pts(0-15)
  Threshold: 45 pts (raised from 40 in Session 13)
  NUCLEAR ≥90 = 2.0u | STANDARD ≥80 = 1.0u | LEAN ≥45 = 0.5u | FAIL <45 = dropped

### Live data sources (what's actually wired vs stub)
  | Component         | Source             | Live? |
  |-------------------|--------------------|-------|
  | edge_pct          | consensus books    | ✅    |
  | rlm_confirmed     | open-price cache   | ✅ (cold on first run — fires on refresh) |
  | efficiency_gap    | efficiency_feed    | ✅ (110 teams: 30 NBA + 80 NCAAB) |
  | rest_edge         | schedule rest days | ✅ NBA only |
  | injury_leverage   | (none)             | ❌ always 0 |
  | motivation        | (none)             | ❌ always 0 |
  | matchup_score     | (none)             | ❌ always 0 |

### Kill switches (all four active)
  NBA:    rest_disadvantage AND spread < -4 → KILL spread
  NFL:    wind > 15mph AND total > 42 → FORCE UNDER
  NCAAB:  3PT reliance > 40% AND is_away → KILL (80-team coverage)
  Soccer: drift > 10% implied prob shift → KILL

### Key architecture invariants (do not break)
  - One API call per sport (raw_games pre-fetched in run_pipeline, passed to calculate_edges)
  - Multi-book consensus = edge signal. Never single-book comparison.
  - Nemesis = display annotation only. Zero effect on score or survival.
  - Math > Narrative. No narrative input may gate or penalise a bet.
  - _OPEN_PRICE_CACHE frozen on first call — second call is no-op (RLM baseline integrity)

### Next threshold raise trigger
  Raise SHARP_THRESHOLD from 45 → 50 when: RLM fires consistently on live data
  (i.e. R&D validates that 6% edge + RLM + eff=12 + rest=2 = 63 is observed empirically).
  Do NOT raise on theory alone — validate distribution first.

## SESSION 12 GOAL ✅ COMPLETE
1. ✅ Nemesis demoted to display-only (bet_ranker.py) — no veto power over math
2. ✅ rest_edge wired into Sharp Score for NBA — live rest days feed situational component
3. ✅ NCAAB kill switch 3PT reliance expanded to 80 teams
4. ✅ NCAAB tempo sourced from efficiency_feed — duplicate dict removed
5. ✅ CLAUDE.md Math > Narrative rule documented permanently
6. ✅ 75/75 tests passing

## SESSION 13 GOAL ✅ COMPLETE
1. ✅ SHARP_THRESHOLD raised 40 → 45 (R&D validated — requires ~7.8% real edge)
2. ✅ compute_rlm() implemented in odds_fetcher.py — 3% implied prob threshold, pick-em guard
3. ✅ RLM wired into run_pipeline() — feeds rlm_data to rank_bets() on every execution
4. ✅ No double API calls — raw_games pre-fetched, passed to calculate_edges(raw_games=...)
5. ✅ 10 new compute_rlm tests — 85/85 passing

## UI RESEARCH FINDINGS (Session 9 — for future multi-page build)
- Stay with Streamlit until genuinely outgrown. Deployment solved, Claude Code iteration fastest.
- For multi-page: st.navigation() + st.Page() is the correct approach (Streamlit 1.36+)
- Best plugins for premium look: streamlit-extras (cards/badges), streamlit-aggrid (bet table)
- Long-term migration target if going public/mobile: FastAPI + HTMX (not React, not Reflex yet)
- Design reference: civixsolutions.com — "normal on surface, neo-brutal on hover" conceit
  Font pairing (Fraunces serif + mono data) worth adopting for future multi-page build
