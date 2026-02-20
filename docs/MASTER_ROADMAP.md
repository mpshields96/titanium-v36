# TITANIUM V36.1 — Master Roadmap & To-Do List
# Created: Session 20 (2026-02-19)
# Last updated: Session 20 end-of-session / v36 Session 21 prep (2026-02-19)
# Source: /sc:analyze edge_calculator.py + sport coverage audit
# This is the authoritative checklist. Update status as items complete.
# Accessible by: v36 chat, R&D chat, any future Claude session.

---

## SECTION 1 — MATH GAPS (complete to "perfect the math")

### GAP 1: NFL Wind — Live Weather API [ ]
- **Status:** Kill switch exists + correct. Input is static stub (seasonal averages per stadium).
- **Risk:** A 28mph Bills game reads as 13mph. Real money lost on FORCE_UNDER kills that don't fire.
- **Fix:** `data/weather_feed.py` — OpenWeatherMap free tier, stadium lat/long lookup, keyed to game time.
- **Where it lands in v36:** Replaces `get_nfl_kill_inputs()` wind stub in `kill_switch_feed.py`.
- **Deadline:** Before NFL season Aug 2026. Low urgency until then.
- **Owner:** R&D builds standalone module. v36 promotes when tested.

### GAP 2: Injury Leverage — ESPN B2 Wire-In [ ]
- **Status:** Stub in `kill_switch_feed.py` — always returns 0.0. R&D module built + usage%-scored.
- **Gate:** Check `results/espn_stability.log` on or after **2026-03-04**.
  - Error rate < 5% AND avg NBA record count > 50 consistently → promote.
  - If Olympic break suppressed counts → extend 3 weeks post-resumption.
- **Where it lands in v36:** `get_injury_leverage()` → `calculate_edges()` situational_data → `rank_bets()`.
- **Impact:** Up to +5 pts on Sharp Score for games with significant injuries.
- **NCAAB:** Permanently stub — ESPN endpoint returns 0 college records.

### GAP 3: Trinity Simulation Mean Bug [ ]
- **Status:** `originator_engine.py` receives `bet.line` (market spread) instead of projected margin.
- **Impact NOW:** Low — simulation is display-only, not wired into sizing.
- **Fix:** Call-site only. R&D fixed in `core/titanium.py`. Same pattern applies to v36 when simulation is promoted.
- **Do not promote until:** Simulation output is used for sizing decisions, not just display.

### GAP 4: Soccer 3-Outcome Edge Inflation [~] ← CONFIRMED MATERIAL — R&D Session 26
- **Problem:** `_consensus_fair_prob()` calls `no_vig_probability(odds_a, odds_b)` — a 2-outcome vig removal.
  Soccer h2h is a 3-outcome market (home / draw / away). Draw is excluded from denominator.
- **Measured error (live EPL, 20 games, 198 book-game pairs, 2026-02-19):**
  Avg home inflation: **+13.46pp**. Avg away inflation: **+10.42pp**. Max: +19.77pp.
- **Impact:** All current v36 soccer edges are inflated by ~10-19pp. A "5% edge" on EPL is likely 0% or negative.
  **Soccer betting signals are unreliable until this fix is promoted.**
- **Fix:** `fair_x = imp_x / (imp_home + imp_draw + imp_away)` — 3-way normalization per book, then average.
- **Prototype:** `consensus_fair_prob_3way()` built in R&D `core/soccer_3way_probe.py` (Session 26).
  Returns: `{fair_home, fair_draw, fair_away, std_dev, n_books}`.
- **R&D Session 27:** `core/soccer_consensus.py` COMPLETE. 6/6 smoke tests pass. Ready for v36 promotion.
- **v36 integration:** Detect soccer by sport key (`sport.startswith("soccer_")`).
  Soccer h2h → `consensus_fair_prob_3way()`. All other sports → existing 2-way method unchanged.
  Draw outcome: `fair_draw` computed but no draw BetCandidate generated (draw betting not in scope).
- **Wire-in:** `from core.soccer_consensus import consensus_fair_prob_3way` — see HANDOFF.md R&D S27 results for full integration snippet.
- **Owner:** v36 integrates into `edge_calculator.py`. R&D module is ready.

---

## SECTION 2 — STRUCTURAL CEILING PROBLEMS (previously called "what model will never catch")

### CEILING 1: Line Shopping — Pinnacle Consensus [ ]
- **Problem:** We use US books only (DK, FD, BetMGM, etc.). Pinnacle is the global sharp-money reference.
  Adding Pinnacle to consensus calculation makes model probability more accurate without changing math.
- **Solution:** R&D probe — check if Pinnacle is available in current Odds API tier.
  If yes: add "pinnacle" to `all_books()` preference list, test consensus accuracy vs. current.
  If no: note API tier upgrade cost (currently ~$30/mo for H2 tier which includes Pinnacle).
- **Where it lands:** `odds_fetcher.py` only — `all_books()` preference order + `_consensus_fair_prob()` gets better inputs automatically.
- **Impact:** Potentially the single highest improvement to model probability accuracy. No math changes.
- **Owner:** R&D probe first. v36 promote if available on current tier.

### CEILING 2: Late Lineup News — 90-Minute Window [ ]
- **Problem:** Injury decisions made at warmups (NBA) or ~60-90 min before tip (NFL) are invisible.
  A star sitting out 45 minutes before tip is undetectable with any free API.
- **Partial solution options (ranked by feasibility):**
  A. **Twitter/X scrape for beat reporters** — Adrian Wojnarowski, Shams Charania post out/in decisions
     minutes after they're made. Unofficial, no auth needed for public posts, fragile.
  B. **ESPN injury API polling** — the same endpoint B2 uses. Call it within 2 hours of tip, not just once.
     Already built in R&D (`espn_injury_fetcher.py`). Just needs to run closer to game time.
  C. **RotowWire inactives feed** — free RSS feed published ~1 hour before tip for NBA/NFL.
     Structured data, reliable, simple to parse. Best option.
  D. **Accept the gap** — model is evaluated at bet-placement time, not tip-off. If you bet at 9am
     and the news breaks at 6pm, that's normal variance for any bettor without a hotline.
- **Recommended approach:** Option B (already built) + Option D (accept residual gap).
  Wire `espn_injury_fetcher.py` to run on demand via a "Refresh Injuries" button in the UI.
  Does not require session restart. Zero API quota cost.
- **Where it lands:** New button in Live Analysis page → calls `espn_injury_fetcher.fetch_injuries()`
  → updates `situational_data` in session state → re-ranks with updated injury_leverage.
- **Owner:** v36 builds the UI button after B2 is promoted. R&D already has the module.

### CEILING 3: Sharp Money Timing — Overnight Line Movement [x] ← COMPLETE v36 Session 20
- **Built:** `data/price_history_store.py` — Supabase persistence layer. `price_history` table live.
  `record_new_events()` + `inject_into_cache()` wired into `run_pipeline()` in `app.py`.
  `inject_into_cache()` pre-seeds `_OPEN_PRICE_CACHE` with true multi-day open prices before
  `cache_open_prices()` runs. `ON CONFLICT DO NOTHING` at DB layer enforces never-overwrite.
  `purge_old_events(14)` prevents unbounded table growth.
  10 new tests. 116/116 passing. Commit `361a90e`.
- **Status:** LIVE. RLM now compares against true first-ever-seen price across sessions.
  First live fire expected when a game is seen across multiple sessions.

---

## SECTION 3 — R&D EXPERIMENTAL BACKLOG

### R&D EXP 1: CLV Tracker [x] ← Live run confirmed R&D Session 22. v36 wire-in complete Session 22.
- **What:** Closing Line Value — compare our bet price to the closing price at kickoff.
  Positive average CLV = empirical proof the edge detection method works.
- **Status:** `core/clv_tracker.py` built. Needs one live NBA game day run to confirm end-to-end.
  R&D Session 21: run `log_clv_snapshot()` on live game + confirm CSV output.
- **Schema clarification (confirmed R&D Session 20):** R&D CSV schema is the working format.
  v36 Supabase schema will differ at promotion (see HANDOFF.md schema delta table).
  Do NOT rewrite `clv_tracker.py` — run live as-is.
- **Output:** Per-bet CLV column in Bet History. Session-level CLV summary in P&L Tracker.
- **File:** `core/clv_tracker.py` in R&D. NOT in odds_fetcher.py.
- **v36 wire-in:** After R&D live run confirmed → v36 builds `data/clv_store.py` + UI column.
- **Owner:** R&D live run. v36 promotes after confirmation.

### R&D EXP 2: Pinnacle Consensus Probe [x] ← Live run confirmed R&D Session 22. NOT on current H1 tier.
- **What:** Check if Pinnacle appears in Odds API response on current tier. If yes, add to consensus.
- **Status:** Script built. R&D Session 21: run `python3 core/pinnacle_probe.py` on NBA game day.
- **If available:** Add "pinnacle" to top of `_BOOK_PREFERENCE` in `odds_fetcher.py`. Consensus auto-improves.
- **If not available:** Document API tier cost to unlock. User decision.
- **Owner:** R&D live run. v36 promotes if Pinnacle available on current tier.

### R&D EXP 3: Sharp Score Calibration Study [~] ← Script complete R&D Session 20. Gate: 30+ tracked outcomes.
- **What:** Validate that Sharp Score weights (Edge 40 / RLM 25 / Eff 20 / Sit 15) are optimal.
  Use Supabase bet history outcomes (when 30+ bets have results) to run Pearson correlation per component.
- **Status:** `core/sharp_score_calibration.py` built and live-tested (0 resolved bets → exits gracefully).
  Supabase connection confirmed working. Script is ready — just needs data.
- **Run when:** v36 has 30+ resolved bets in `bet_history` (outcome IS NOT NULL).
  Command: `python3 core/sharp_score_calibration.py` (in R&D env — supabase package installed).
- **Question:** Does efficiency_gap actually predict outcome? Is RLM 25 pts too high or too low?
- **Output:** `results/sharp_score_calibration.txt` — Pearson r per component + weight recommendations.
- **Owner:** Auto-runnable when data is available. R&D reports findings. v36 makes weight calls.

### R&D EXP 4: Live Weather API for NFL Wind [ ]
- **See SECTION 1 GAP 1 above.** R&D builds standalone module. Aug 2026 deadline.

### R&D EXP 5: Multi-Game Parlay Identification [~] ← Prototype complete R&D Session 24. Live validation pending.
- **What:** Identify 2-leg parlay combinations from the ranked slate where:
  (a) events are independent (different games), (b) both bets pass Sharp Score threshold,
  (c) combined Kelly suggests positive parlay EV.
- **Math:** parlay_prob = prob_a × prob_b. parlay_payout = (payout_a + 1) × (payout_b + 1) - 1.
  EV = parlay_prob × parlay_payout - (1 - parlay_prob). Only show if EV > 0.
- **Status:** `core/parlay_builder.py` built (Session 24). 6/6 smoke tests pass.
  `build_parlay_combos(bets)` + `format_parlay_table(combos)` implemented. Wire-in: `[vars(b) for b in ranked_bets]`.
  Live validation pending (Session 26 Task 2 — NBA game day required).
- **Where it lands:** New "Parlay Builder" tab in Streamlit app (UI 4).
- **Owner:** R&D live validation → v36 promotes.

### R&D EXP 6: Market Efficiency by Sport/Book [ ]
- **What:** Over 50+ bets, identify which books are most consistently mispriced vs. consensus.
  Does BetMGM overprice NHL moneylines? Are DraftKings NCAAB totals consistently off?
- **Output:** Per-book weight multipliers for `_consensus_fair_prob()`. Better model probability.
- **Gate:** Needs sufficient bet history data. Long-term research.

### R&D EXP 7: NCAAF Efficiency Data [ ]
- **What:** 130 FBS teams, SP+ ratings (ESPN public) as AdjEM equivalent.
- **Deadline:** Before NCAAF season Aug 2026.
- **Risk:** High alias collision (many NCAAF and NCAAB teams share city names). Run /sc:analyze first.
- **Owner:** R&D builds, same pattern as NCAAB.

### R&D EXP 8: Alternate Line Parsing [BLOCKED]
- **What:** Parse alternate spreads/totals (e.g. -3 at -140 vs standard -6.5 at -110).
  Higher consensus dispersion on alt lines = potentially larger real edges.
- **Status:** `alternate_spreads` / `alternate_totals` market keys NOT supported on H1 tier.
  API returns: "Markets not supported by this endpoint". Requires H2 tier (~$30/mo). Same gate as Pinnacle.
- **Reopen when:** User upgrades to H2 tier. No R&D build until then.

### R&D EXP 9: College Baseball Probe [x] ← CLOSED R&D Session 25
- **What:** Check Odds API coverage for `baseball_ncaa`. If < 5 books on average → skip.
- **Result (2026-02-19 live probe):** 44 games returned. Avg **2.1 books/game**. Min 1, max 6.
  84% of games have only DraftKings + BetMGM. Consensus invalid below 3 books.
- **Verdict:** SKIP. Do not build baseball_ncaa efficiency data or pipeline support.
  Market too thin for consensus-based edge detection at current tier.

### R&D EXP 10: Tennis — Separate Pipeline [ ]
- **Note:** Fundamentally different from all current sports. Moneyline only, no spread/totals,
  highly individual, surface-specific. Not an extension — a separate product.
  Worth its own R&D sandbox if pursued. Do not bolt onto Titanium architecture.
- **Pre-requisite:** Decide if tennis is in scope at all. User decision.

---

## SECTION 4 — STREAMLIT APP / UI BACKLOG

### UI 1: P&L Tracker Page [x] — COMPLETE (Session 20)
- **Built:** Equity curve chart, ROI by sport, win rate by market type, W/L/P summary strip.
- **Data source:** Supabase `bet_history` table. `fetch_bets(limit=500)` → `compute_pnl_summary()`.
- **File:** `app.py` → `page_pnl_tracker()`.

### UI 2: Odds Comparison Page [x] — COMPLETE (Session 21)
- **Built:** Game selectbox, side-by-side h2h/spreads/totals dataframes, BEST price badges, LINE SPLIT warnings.
- **Data source:** `raw_games` accumulated in `run_pipeline()` → `st.session_state["raw_games"]`. No new API calls.
- **Files:** `data/odds_comparator.py` (promoted from R&D) + `app.py` → `page_odds_comparison()`.
- **Also built Session 21:** app.py cleanup (dead imports removed, del→pop fix, tracked_* key hygiene, try/finally on pipeline).

### UI 3: Refresh Injuries Button (post-B2) [ ]
- **What:** On-demand re-fetch of ESPN injury data mid-session.
  Updates injury_leverage in session state, re-ranks bets without full pipeline re-run.
- **Dependencies:** B2 injury leverage must be promoted first (Gate: 2026-03-04).

### UI 4: Parlay Builder Tab (post-R&D EXP 5) [ ]
- **What:** Displays valid 2-leg parlay combinations from current slate with EV calculation.
- **Dependencies:** R&D EXP 5 must be validated first.

### UI 5: CLV Column in Bet History [x] — COMPLETE (Session 22)
- **Built:** `data/clv_store.py` (Supabase CLV persistence). `clv_history` table live.
  `record_clv_open()` called at Track Bet time (uses bet.price — NOT get_open_price, key collision).
  `fetch_clv_for_events()` batch-fetches CLV for all displayed bets. History Log has 9th CLV column.
  CLV shows `+Xpp` / `-Xpp` / `—` depending on whether closing_price has been filled.
  `update_clv_close()` built but not wired — future feature when closing prices are available.

---

## SECTION 5 — PERSISTENT RLM UPGRADE (HIGH VALUE) — [x] COMPLETE
See CEILING 3 above (also marked complete). Built v36 Session 20. Commit `361a90e`.

### RLM 2.0: Persistent Open-Price Store [x]
- **Table:** `price_history` in Supabase — event_id UNIQUE, home_price, away_price, first_seen_at.
- **File:** `data/price_history_store.py` — `record_new_events()`, `inject_into_cache()`,
  `purge_old_events(14)`, `price_history_status()`.
- **Wired:** `run_pipeline()` in `app.py` calls store before `cache_open_prices()`.
  `inject_into_cache()` pre-seeds `_OPEN_PRICE_CACHE` with historical baselines.
- **Tests:** 10 new tests in `tests/test_price_history_store.py`. 116/116 total.
- **Next step for this feature:** Monitor — next live RLM fire should show multi-day movement data.
  When RLM fires 5 live sessions: raise SHARP_THRESHOLD 45 → 50 (see SESSION_STATE.md gate).

---

## STATUS LEGEND
[ ] = Not started
[R] = In R&D
[~] = Partially done / gated
[x] = Complete

## GATE DATES
- **ROLLING:** v36 30+ resolved bets → run `core/sharp_score_calibration.py` (R&D EXP 3)
- **ROLLING:** RLM live sessions ≥ 5 → raise SHARP_THRESHOLD 45 → 50 (currently 0/5)
- **ROLLING (any NBA game day):** Run `python3 core/pinnacle_probe.py` + `log_clv_snapshot()` (EXP 1, EXP 2)
- 2026-03-04: B2 ESPN injury endpoint stability check (GAP 2, CEILING 2, UI 3)
- 2026-03-27: MLB season starts (efficiency data already promoted — no action needed)
- 2026-08-01: NFL/NCAAF season prep window opens (GAP 1, R&D EXP 4, R&D EXP 7)

## SESSION COMPLETION LOG
| Session | Completed items |
|---------|----------------|
| v36 S23 (2026-02-19) | CLAUDE.md Session 22 learnings, PROJECT_INDEX.md updated (135 tests, 3 new modules), session handoffs prepared |
| v36 S22 (2026-02-19) | UI 5 (CLV column), `data/clv_store.py` (NEW), `clv_history` Supabase table, 19 new tests (135 total) |
| v36 S21 (2026-02-19) | UI 2 (Odds Comparison page), `data/odds_comparator.py` promoted, app.py cleanup |
| v36 S20 (2026-02-19) | UI 1 (P&L Tracker), MASTER_ROADMAP created |
| v36 S20 cont. | CEILING 3 / SECTION 5 (RLM 2.0 persistent store) — `price_history_store.py` + Supabase table + tests |
| v36 S19 (2026-02-18) | MLB/MLS/NFL efficiency data (234 teams), Hawks collision fix |
| R&D S27 (2026-02-19) | GAP 4 `core/soccer_consensus.py` COMPLETE (6/6 smoke tests). Ready for v36 `edge_calculator.py` integration. |
| R&D S26 (2026-02-19) | GAP 4 soccer 3-outcome CONFIRMED MATERIAL (+13.46pp avg inflation). `core/soccer_3way_probe.py` + prototype built. |
| R&D S25 (2026-02-19) | EXP 9 CLOSED (baseball_ncaa 2.1 avg books — below threshold). EXP 8 BLOCKED (H2 tier). |
| R&D S24 (2026-02-19) | EXP 5 `core/parlay_builder.py` built + validated (6/6 smoke tests). B2 + calibration gated. |
| R&D S21 (2026-02-19) | `core/odds_comparator.py` built + validated (12/12 checks). Pinnacle probe + CLV live run blocked by wifi. |
| R&D S20 (2026-02-19) | EXP 3 script built (`sharp_score_calibration.py`), EXP 1 + EXP 2 scripts built (need live run) |
