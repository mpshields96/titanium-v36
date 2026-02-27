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
4. Say: "Resume Session 18. Read CLAUDE.md, CLAUDE.local.md, and SESSION_STATE.md.
         Run: python3 -m pytest tests/ -v and confirm all 95 tests pass before we start."
5. Wait for test confirmation, then state what you want to build

Notes:
- CLAUDE.local.md has current session scope + Session 18 pre-reqs (Supabase setup)
- PROJECT_INDEX.md is the fast orientation file — 94% token reduction vs reading source files
- Always use `python3 -m pytest` not bare `pytest` (avoids venv path issues on this machine)

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

## SESSION 14 GOAL ✅ COMPLETE
1. ✅ Promote bet_card_renderer.py from R&D — render_bet_card() + render_bet_slate()
2. ✅ Wire render_bet_slate() into app.py results section (replaces old inline renderer)
3. ✅ .streamlit/config.toml created — native theme backing CSS
4. ✅ data/__init__.py created — fixes Streamlit Cloud subpackage ImportError
5. ✅ app.py: sidebar expanded, soccer 3-col layout, empty-state icon fixed
6. ✅ 85/85 tests passing

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

## WHAT'S BUILT AND WORKING (as of Session 13 cleanup)
- edge_calculator.py: dead stub deleted, _KILL_ROUTER cleaned, kill_switch_feed imports promoted
  to module level, stale docstrings fixed (run_nemesis, calculate_sharp_score, sharp_to_size)
- bet_ranker.py: unused is_prop param removed from sharp_to_size() call sites
- All cleanup is structural only — zero behaviour changes. 85/85 tests green.

## WHAT'S BUILT AND WORKING (as of Session 14)
- bet_card_renderer.py: promoted from R&D — render_bet_card() + render_bet_slate()
  Tier colours: NUCLEAR amber (#F59E0B) / STANDARD blue (#3B82F6) / LEAN teal (#14B8A6)
  Score decomposition bar (Edge/RLM/Eff/Sit segments), RLM badge (violet, conditional),
  FLAG/KILL banners, Nemesis block, Monte Carlo sim row, commence_time display
  Inline styles only — Streamlit strips <style> tags from markdown
- app.py: wired render_bet_slate() — results section uses single st.markdown call
  Removed old inline render_bet_card() and _get_tier/_get_size_label/_get_tier_label helpers
- .streamlit/config.toml: created — native dark theme backing custom CSS
  primaryColor #E8A020, backgroundColor #0D1117, baseRadius none, monospace font
- data/__init__.py: created — fixes Streamlit Cloud ImportError on subpackage imports
- app.py: sidebar expanded by default, soccer 3-col layout, empty-state icon fixed (◈→—)
- 85/85 tests passing throughout

## CURRENT STATE
Last completed: V37 Reviewer Session 9 (autonomous) — 2026-02-26
Last git commit: `01b2c79` (REVIEWER_PROMPT.md + Session 36 directive)
Tests: **257/257 passing**
Quota: ⚠️ EXHAUSTED (~1 credit on main key). Test key (~485 remaining). Resets 2026-03-01.
BILLING_RESERVE: **50** (temporarily lowered from 1000 — restore after 2026-03-01 reset; DAILY_CREDIT_CAP=100 is permanent)
Streamlit Cloud: deployed, auto-deploys from main
RLM live sessions observed: 0 (gate for SHARP_THRESHOLD raise to 50 — increment each session RLM fires)

### Architecture (V37 — two-AI system)
- **Primary builder:** Agentic sandbox at ~/ClaudeCode/agentic-rd-sandbox/ (1099+ tests)
- **Reviewer/Auditor:** This chat — reviews sandbox sessions, flags issues, decides promotions to v36
- **R&D chat:** RETIRED. titanium-experimental/ archived.
- **Live product:** v36 on Streamlit Cloud
- **Coordination:** REVIEW_LOG.md + V37_INBOX.md in agentic-rd-sandbox/ (sandbox writes → reviewer reads)
- **Startup document:** REVIEWER_PROMPT.md at /Users/matthewshields/Projects/titanium-v36/REVIEWER_PROMPT.md

### What was done in V37 Reviewer Session 5 (2026-02-25)
1. **CRITICAL BUG FIX — Totals dedup cross-line guard**: `bet_ranker.py:183` — totals dedup key now drops `abs(line)`. Over 7.0 and Under 6.5 from same game now share same dedup bucket; highest-edge side survives. +6 tests in `TestTotalsDedupCrossLine`.
2. **Root cause analysis written** to REVIEW_LOG.md: two-failure breakdown of totals consensus line-mixing bug. Sandbox directed to implement Layer 1 (modal line pinning in `consensus_fair_prob()`).
3. **Math > Narrative sweep**: Full ecosystem scan — CLEAN. No narrative inputs in scoring, kill switches, or grade tiers.
4. **Session 27 cont. go-live config reviewed**: APPROVED. Sandbox credit limits and analytics gate change are correct.
5. **V37_INBOX Session 28 task**: Marked DONE.
6. **Test count: 251 → 257** (+6 dedup tests)

### What was done in V37 Reviewer Session 4 (2026-02-25)
1. **DAILY_CREDIT_CAP 1000 → 100** in odds_fetcher.py (user directive: permanent ceiling on 20K plan)
2. **BILLING_RESERVE 1000 → 50** (temp for quota drought — restores 2026-03-01)
3. **Zero-bets speculative protocol**: rank_bets() calibration_threshold=40.0 retry; bets scoring 40–44 returned with calibration=True and kelly capped at 0.25u
4. **Three-tier SPECULATIVE UI**: sharp_to_size() returns SPECULATIVE_0.25U for scores < 45; orange bet card config added; SPECULATIVE MODE banner in app.py
5. **nhl_data.py promoted to v36**: data/nhl_data.py, nhl_kill_switch() in edge_calculator.py, parse_game_markets() updated, inline NHL goalie poll in run_pipeline()
6. **Test count: 190 → 251** (+61 total across all work this session)

### Pending for next session
- **2026-03-01**: Restore `BILLING_RESERVE` 50 → 1_000 in v36 odds_fetcher.py (DAILY_CREDIT_CAP stays at 100 permanently)
- **2026-03-01**: Run full live pipeline stress test for model calibration (quota resets)
- **2026-03-04**: B2 gate check — /Users/matthewshields/Projects/titanium-experimental/results/espn_stability.log
- **Sandbox**: Layer 1 totals fix ✅ DONE (Session 29 — modal line pinning in consensus_fair_prob())
- **v36**: Stale docstrings in odds_fetcher.py ✅ DONE (V37 R7 — constant names not hardcoded values)

### What was built in Session 24
1. **GAP 4 — Soccer 3-outcome fix (CRITICAL)**
   - `data/soccer_consensus.py` — promoted from R&D `core/soccer_consensus.py` (6/6 R&D smoke tests pass).
     `american_to_implied()`, `_fair_3way()`, `_std_dev()`, `consensus_fair_prob_3way()`.
   - `edge_calculator.py` — `from data.soccer_consensus import consensus_fair_prob_3way` added at top.
     `parse_game_markets()` moneyline section now branches on `_is_soccer` flag:
     - Soccer: collects `home_prices / draw_prices / away_prices` per book (Draw = API outcome name).
       Calls `consensus_fair_prob_3way()` → correct 3-way vig removal (was inflating +10–19pp).
     - Non-soccer: unchanged 2-outcome `_consensus_fair_prob()` path.
   - 13 new tests: `tests/test_soccer_consensus.py` — all pass.

2. **EXP 5 — Parlay Builder promoted**
   - `data/parlay_builder.py` — promoted from R&D. `build_parlay_combos(bets: list[dict])` + `format_parlay_table()`.
     Call site shim: `[vars(b) for b in ranked_bets]` to convert BetCandidate dataclass → dict.
   - `app.py` — `page_parlay_builder()` added. Reads `st.session_state["results"]`. Inert until pipeline runs.
     Shows combo cards: EV badge, leg A/B targets+prices, P(win)/payout/matchup strip.
     Independence gate: same event_id pairs excluded. Positive-EV filter enforced.
   - `st.navigation()` — 🔗 Parlay Builder added as 5th page.
   - 15 new tests: `tests/test_parlay_builder.py` — all pass.

### ⚠️ NEW CHAT TRANSITION NOTE (v36 Session 25)
Session 24 complete. Read PROJECT_INDEX.md → docs/MASTER_ROADMAP.md → SESSION_STATE.md → CLAUDE.md
Then: python3 -m pytest tests/ -v (confirm 163/163)

Session 25 priorities — all current v36 work is gated:
- B2 injury leverage: gate 2026-03-04. espn_stability.log has 10 entries, all 2026-02-19 — gate not met yet.
  R&D Session 29 pre-wire COMPLETE: `get_nba_injury_leverage_for_game()` built in R&D kill_switch_feed.py.
  Wire-in spec: sandbox `kill_switch_feed.py` + `math_engine.py`. Gate: 2026-03-04. Ready to promote when gate opens.
- Sharp Score calibration: gate 30+ resolved bets in bet_history (currently 0).
- CLV close: update_clv_close() built but not wired — future when closing prices available.
- Pinnacle / alternate lines: H2 tier (~$30/mo). User decision.
- NCAAF efficiency: R&D EXP 7 complete (40 programs). v36 integration Aug 2026 window.
- API quota rule added to CLAUDE.md + MEMORY.md (Session 25): R&D live calls require explicit approval.

### What was built in Session 22
1. **R&D Session 22 findings absorbed:**
   - Pinnacle NOT available on current H1 US retail tier. No changes to _BOOK_PREFERENCE.
   - CLV live run confirmed working: 1 live row appended to CSV (7 total in results/clv_snapshots.csv).
   - Critical: use bet.price as open_price — NOT get_open_price() (team-name key collision across h2h/spreads markets).
   - B2 gate not yet met (9 log entries, all 2026-02-19 — need 14+ days of data).
2. **`data/clv_store.py`** (NEW) — Supabase CLV persistence layer.
   - `is_configured()`, `_implied()`, `_compute_clv_pct()`, `record_clv_open()`, `update_clv_close()`,
     `fetch_clv_for_events()`, `get_clv_summary()`
   - Separate `clv_history` table with UNIQUE(event_id, target, market_type). One CLV row per bet side + market.
   - open_price = bet.price at Track Bet time (NOT get_open_price — collision risk documented in docstring).
3. **Supabase `clv_history` table** created via MCP migration (id PK, event_id, target, market_type, sport,
   matchup, open_price, closing_price, open_implied, closing_implied, clv_pct, recorded_at).
   Two indexes: event_id + recorded_at DESC.
4. **`app.py`** — Track Bet handler: `record_clv_open()` called after `insert_bet()` (lazy import, is_configured() guard).
5. **`app.py`** — `page_bet_history()`: batch CLV fetch (`fetch_clv_for_events()`) after loading all_bets.
   History Log expanded from 8 to 9 columns: added CLV column between Score and Result.
   CLV displays as `+2.3pp` (green) / `-1.5pp` (red) / `—` (grey) when closing_price not yet filled.
6. **`tests/test_clv_store.py`** (NEW) — 19 tests. All Supabase I/O mocked. 135/135 total.

### What was built in Session 21
1. `data/odds_comparator.py` (NEW) — promoted from R&D Session 21. Pure transformation, no API calls.
   `build_odds_comparison(game)` + `to_dataframes(comp)`. `line_split` flag, `best_price` dict.
   `_BOOK_PREFERENCE` hardcoded (mirrors `odds_fetcher.PREFERRED_BOOKS` — sync if Pinnacle added).
2. `app.py` — `page_odds_comparison()` fully built (replaces stub).
   Game selectbox (all games in current slate), h2h/spreads/totals st.dataframe() tables,
   BEST price badges, LINE SPLIT warning banners, empty-state guard when no slate loaded.
3. `app.py` — `all_raw_games` accumulation in `run_pipeline()`. Stored as `st.session_state["raw_games"]`.
   Zero extra API calls — raw_games already fetched per sport, now persisted for UI 2.
4. `app.py` cleanup (all confirmed 116/116 throughout):
   - Removed dead imports: `format_bet_table`, `render_bet_slate`, `fetch_pending_bets`
   - `del st.session_state[...]` → `.pop(key, None)` (safe missing-key guard)
   - Removed duplicate `import streamlit as st` inside `page_pnl_tracker()`
   - Removed stale comment re: `render_bet_slate`
   - Added `tracked_*/track_*` key cleanup loop at `run_pipeline()` start
   - Wrapped post-loop ranking in `try/finally` to ensure `running` flag always resets

### What was built in Session 20
1. `docs/MASTER_ROADMAP.md` — authoritative to-do list: 5 sections covering math gaps,
   structural ceiling fixes (Pinnacle, late lineup, overnight RLM), R&D backlog (10 items),
   Streamlit UI backlog, RLM 2.0 spec. Status-tracked with [ ] / [R] / [~] / [x] legend.
   Updated at session end: CEILING 3 / SECTION 5 marked [x]. EXP 1/2/3 updated to [~].
2. `CLAUDE.md` — Chat Roles & File Access table, mandatory Loading screen tip rule. Session 20 log entry.
3. `data/efficiency_feed.py` — docstring typo fixed: "202 teams" → "234 teams"
4. `app.py` — `page_pnl_tracker()` fully implemented (was stub). Summary strip, equity curve,
   ROI by sport, win rate by market type. st.html() + is_configured() guard pattern.
5. **RLM 2.0 — `data/price_history_store.py`** (NEW) — Supabase persistence layer for first-ever-seen
   open prices. `record_new_events()` + `inject_into_cache()` + `purge_old_events(14)`.
   DB UNIQUE(event_id) + ON CONFLICT DO NOTHING enforces no-overwrite. Wired into `run_pipeline()`.
6. `odds_fetcher.py` — extracted `_extract_open_prices()` helper (no-op refactor, reusable).
7. Supabase `price_history` table created (event_id UNIQUE, home_price, away_price, first_seen_at, 2 indexes).
8. `tests/test_price_history_store.py` — 10 new tests. All Supabase I/O mocked. 116/116 total.
9. HANDOFF.md (R&D) — Session 21 instructions written: Task 0 (Pinnacle probe), Task 1 (CLV live run),
   Task 2 (Odds Comparison data layer design). R&D Session 20 questions answered.

### What was built in Session 19
1. `data/efficiency_feed.py` — promoted MLB (30), MLS (30), NFL (32) from R&D Session 17.
   Total coverage now 234 teams: NBA 30 + NCAAB 80 + NHL 32 + MLB 30 + MLS 30 + NFL 32.
   Formulas: MLB = (4.30 - era) * 8.0 | MLS = xgd_per_90 * 15.0 | NFL = epa_per_play * 80.0.
   Hawks alias collision fixed: "Hawks"→Atlanta Hawks (NBA), "Blackhawks"→Chicago Blackhawks.
   Alias collision table documented in file docstring.
2. `tests/test_validation.py` — added 11 new tests (TestNewLeaguesEfficiency).
   Team count assertions (30/30/32), gap range checks, 6 alias collision guard tests.
3. /sc:analyze findings on efficiency_feed.py addressed — Hawks collision was the only HIGH-severity issue.

### What was built in Session 18
1. `page_bet_history()` — full implementation replacing stub
   P&L summary strip (4 stat tiles), Pending Results section with
   WIN/LOSS/PUSH selectbox + MARK RESULT → update_outcome(), History Log
   columnar table with alternating rows + outcome badges.
   Supabase not-configured guard. bet_history_data session cache.
2. `render_slate_header()` + `render_slate_footer()` added to bet_card_renderer.py
3. Live Analysis: per-card loop replaces monolithic st.html(render_bet_slate()).
   + TRACK BET button per card → insert_bet() → cache bust.
   Lazy import of insert_bet inside results block (zero test impact).

### Key fixes applied this session (not a numbered session — post-17 cleanup)
1. eff_data bug: `build_efficiency_data()` was NCAAB-only — NHL efficiency data (Session 17) was never
   reaching rank_bets(). Fixed with `eff_data.update(build_efficiency_data(raw_games))` for all sports.
2. Card rendering: Streamlit 1.54 sandboxes large HTML in st.markdown into a code block.
   Fixed: `st.markdown(render_bet_slate(...), unsafe_allow_html=True)` → `st.html(render_bet_slate(...))`
3. Header clip: TITANIUM wordmark partially hidden under Streamlit toolbar.
   Fixed: `.block-container` top padding 2rem → 3.5rem.
4. Supabase MCP: configured in ~/Library/Application Support/Claude/claude_desktop_config.json
   with @supabase/mcp-server-supabase@latest. Restart Claude Desktop to activate.

### Session 18 pre-requisites
- ✅ Supabase MCP configured (claude_desktop_config.json)
- ✅ Supabase project created: titanium-claude (id: gghjavtjfvtsrdaiduuz, region: us-west-2)
- ✅ `bet_history` table created via MCP migration
- ✅ SUPABASE_URL + SUPABASE_KEY written to .streamlit/secrets.toml

### Pre-built for Session 18 (pre-session work, not a numbered session)
- ✅ `data/bet_history_store.py` scaffolded — insert_bet(), update_outcome(), fetch_bets(),
     fetch_pending_bets(), compute_pnl_summary(), is_configured(). All I/O in one file.
- ✅ `supabase>=2.3.0` added to requirements.txt
- ✅ SUPABASE_URL + SUPABASE_KEY in .streamlit/secrets.toml (never commit)
- ✅ `bet_history` table live in Supabase — ready for Session 18 UI build

## SESSION 16 GOAL ✅ COMPLETE
1. ✅ Feature B: get_nba_injury_leverage() + get_ncaab_injury_leverage() stubs in kill_switch_feed.py
   - Both return (0.0, False) — data_live=False. rank_bets() reads from situational_data (path was already live).
2. ✅ Feature F1: std_dev: float = 0.0 added to BetCandidate
   - Passed into BetCandidate at 3 call sites (spreads L686, moneylines L730, totals L777)
   - _consensus_badge_html() added to bet_card_renderer.py — TIGHT/MODERATE/WIDE tiers
   - Wired into render_bet_card() header row (after RLM badge)
3. ✅ Feature C deferred — RLM gate still unmet (0/5 sessions observed)
4. ✅ F2 (std_dev Sharp Score component) — R&D validated: REJECT permanently
   - R&D tested 580 sides: Pearson r=+0.020, no linear relationship
   - Discount A (penalty) breaks core mechanism — high std_dev = one outlier book = source of edge
   - Discount B (badge) = correct approach → already delivered in F1
   - F2 closed, not deferred

## R&D SESSION 15 FINDINGS (action items for v36)
Feature B2 — ESPN Unofficial Injury API:
  - Endpoint: https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries (no auth, ~0.4s)
  - NBA: 105 players across Out/Day-To-Day/Suspension statuses — data exists
  - NCAAB: 0 records — endpoint does not cover college basketball
  - Blocker 1: Position weights hit cap (5.0) on 3/5 teams tested — needs usage% cross-reference
  - Blocker 2: Unofficial endpoint — needs 2+ weeks stability monitoring before v36 promotion
  - Sandbox file: agentic-rd-sandbox/core/kill_switch_feed.py (B2 pre-wire in get_nba_injury_leverage_for_game — do not promote yet)
  - v36 stubs remain as-is until both blockers resolved

## SESSION 15 GOAL ✅ COMPLETE
1. ✅ Feature backlog saved permanently to SESSION_STATE.md (4 categories: Ready/Seasonal/Blocked/Deferred)
2. ✅ /sc:estimate completed for Options B (injury leverage), C (threshold raise), F (std_dev signal)
3. ✅ Session transition prep — new chat ready to resume at Session 16
4. ✅ RLM gate tracker added to CURRENT STATE (increment when RLM fires on live data)

## SESSION 15 ESTIMATES (reference for Session 16)
| Feature | Approach | Estimate | Decision |
|---------|----------|----------|----------|
| B — Injury leverage | Manual stub in kill_switch_feed.py | ~2.5 hrs | ✅ Build in Session 16 |
| C — Threshold raise 45→50 | One-liner + docs | ~20 min | ⚠️ Gate: RLM must fire on 5+ live sessions first |
| F1 — std_dev badge | Display badge on bet card | ~1.5 hrs | ✅ Build in Session 16 |
| F2 — std_dev score | Sharp Score sub-component | ~4–6 hrs | 🔬 R&D only — validate before promoting |

Session 16 scope: B + F1 (~4 hrs). C deferred. F2 to R&D.

## ORIENTATION (read this first in any new session)
1. Read PROJECT_INDEX.md — 229 lines, covers all modules, functions, Sharp Score formula, kill switches, test counts. 94% token reduction vs reading all source files.
2. Run: python3 -m pytest tests/ -v — confirm 85/85 before touching anything.
3. Then read SESSION_STATE.md CHECKPOINT block for exact system state.
4. For sandbox context: read REVIEW_LOG.md + SESSION_LOG.md in ~/ClaudeCode/agentic-rd-sandbox/ (R&D chat RETIRED as of Session 25 — titanium-experimental/ is archived).

## CHECKPOINT — Session 13 cleanup (2026-02-18)
State: CLEAN. All code committed. 85/85 tests green.
Commit: c3954ad — dead stub, _KILL_ROUTER NBA entry, deferred imports, stale docstrings all cleaned.

### Sharp Score formula (as implemented — memorise this)
  score = edge_pts(0-40) + rlm_pts(0-25) + efficiency_pts(0-20) + situational_pts(0-15)
  Threshold: 45 pts (raised from 40 in Session 13)
  NUCLEAR ≥90 = 2.0u | STANDARD ≥80 = 1.0u | LEAN ≥45 = 0.5u | FAIL <45 = dropped

### Live data sources (what's actually wired vs stub)
  | Component         | Source             | Live? |
  |-------------------|--------------------|-------|
  | edge_pct          | consensus books    | ✅    |
  | rlm_confirmed     | open-price cache   | ✅ (cold on first run — fires on refresh) |
  | efficiency_gap    | efficiency_feed    | ✅ (142 teams: 30 NBA + 80 NCAAB + 32 NHL) |
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

---

## FEATURE BACKLOG (assessed 2026-02-18, Session 15)
Priority order within each group. Update as seasons change.

### 🟢 READY TO BUILD NOW (in-season, no blockers)

| Feature | Effort | Notes |
|---------|--------|-------|
| **`std_dev` badge (F1)** | ✅ Done | Delivered Session 16. BOOKS: TIGHT/MODERATE/WIDE badge on card. F2 (Sharp Score component) validated by R&D and permanently rejected (r=+0.020, no linear relationship). |
| **NHL efficiency data** | ✅ Done | Delivered Session 17. 32 teams, GF60-GA60 × 10 AdjEM proxy. Arizona Coyotes removed (relocated to Utah HC in 2024-25). Aliases wired for NY Rangers/Islanders collision + Las Vegas/Vegas GK variant. |
| **Bet History page** | Medium | Stub page exists. Needs: local JSON/CSV to persist bets, record-bet button on card, outcome tracking, P&L summary. Pure UI — no math, no API. |
| **RLM threshold raise (45→50)** | Trivial | DATA GATE: raise only after RLM fires consistently on 5+ live sessions with observed signals. Do NOT raise on theory. |
| **P&L Tracker page** | Medium | Stub page exists. Depends on Bet History being built first (needs outcome data). |

### 🟡 SEASONAL — BUILD BEFORE SEASON STARTS

| Feature | Season | Window | Notes |
|---------|--------|--------|-------|
| **NFL efficiency data** | NFL | Aug–Sep 2026 | 32 teams, EPA/play → AdjEM equiv. Kill switch wind map already done (Session 9). Routing already wired. Build ~2 weeks before preseason. |
| **NCAAF expansion** | NCAAF | Aug–Sep 2026 | Similar to NCAAB pattern. 130 FBS teams. Low priority until NFL confirmed working. |
| **MLB expansion** | MLB | Mar–Apr 2026 | Season starts April. Needs: run-line + totals parsing, pitcher efficiency proxy (ERA/FIP), no spread kill switch (run-line collar applies). |
| **MLS expansion** | MLS | Mar 2026 | MLS season starts March. Soccer pipeline already works — just needs MLS teams in efficiency feed (low-quality data available). |

### 🔴 BLOCKED — EXTERNAL DATA REQUIRED

| Feature | Blocker | Notes |
|---------|---------|-------|
| **Injury leverage (NBA)** | ESPN unofficial endpoint not stable | R&D (Session 15) found endpoint works but position weights cap at 5.0 for 3/5 teams — needs usage% cross-reference. Also needs 2+ weeks stability monitoring. NCAAB: endpoint returns 0 records — no path forward for college. v36 stubs exist (return 0.0). Wire when B2 blockers resolved. |
| **Motivation component** | Subjective / no source | Rat poison per CLAUDE.md. Do not add. |
| **`public_on_side` upgrade** | Action Network or similar | RLM heuristic (price < -105) is Phase 1 placeholder. Upgrade when consensus % data available. |
| **Bet History outcomes** | No results source | Odds API doesn't provide final scores. Would need a sports data API (ESPN, sportsdata.io) to auto-resolve bets. Manual outcome entry is an option. |

### ⚪ DEFERRED / LOW PRIORITY

| Feature | Notes |
|---------|-------|
| **Trinity simulation `mean` bug fix** | `bet.line` passed instead of projected margin. Tracked in R&D. Fix before relying on simulation output for sizing. |
| **`remove_vig_shin()` cleanup** | In R&D method_b_clv.py — unused. Ask before removing. |
| **Odds Comparison page** | Stub exists. Would show side-by-side prices across all books. Nice-to-have, not core. |
| **NHL expansion** | Sparse API coverage makes signal quality low. Worth building if NHL is a priority sport. |
| **Props support** | Confirmed 422 on bulk endpoint — per-event only (4 calls/game). API tier limitation. Revisit if tier upgrades. |
