# TITANIUM V36.1 — Master Roadmap & To-Do List
# Created: Session 20 (2026-02-19)
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

### CEILING 3: Sharp Money Timing — Overnight Line Movement [ ]
- **Problem:** RLM currently catches intra-session movement only (open price cached at session start,
  compared to current). If sharp money hits at 2am and moves the line by 20 cents before you open
  the app at 8am, our open-price cache starts from the already-moved price. Invisible.
- **Solution:** Persistent open-price store — save the *first-ever-seen* price for each event_id
  to Supabase, not just in-session memory.
  - On session start: fetch current prices. For any event_id already in DB, use stored price as open.
  - For new event_ids: store current price as open baseline.
  - RLM then compares against the TRUE open (first time we ever saw that game) not today's first fetch.
- **Impact:** Transforms RLM from intra-session to multi-day. A line that moved from -3 to -6.5 over
  3 days now shows as a massive RLM signal instead of 0.
- **Where it lands:** `data/` new file `price_history_store.py` (same pattern as `bet_history_store.py`).
  `odds_fetcher.cache_open_prices()` checks DB first. Supabase already configured.
- **Owner:** R&D designs the schema. v36 builds the store + wires into `cache_open_prices()`.
- **This is HIGH value. Upgrade RLM from a weak signal to a strong one.**

---

## SECTION 3 — R&D EXPERIMENTAL BACKLOG

### R&D EXP 1: CLV Tracker [R] ← R&D Session 18 task
- **What:** Closing Line Value — compare our bet price to the closing price at kickoff.
  Positive average CLV = empirical proof the edge detection method works.
- **Data needed:** Already have open prices (session cache). Need closing prices (fetch same game
  near tipoff or use Odds API historical endpoint if available on our tier).
- **Output:** Per-bet CLV column in Bet History. Session-level CLV summary in P&L Tracker.
- **File:** `core/clv_tracker.py` in R&D. NOT in odds_fetcher.py.
- **CSV columns:** event_id, sport, matchup, market_type, our_price, closing_price, clv_pct, recorded_at
- **Why now:** Zero new infrastructure. Uses existing RLM cache + Supabase bet history.
- **Owner:** R&D builds standalone `core/clv_tracker.py`. v36 wires into Bet History page.

### R&D EXP 2: Pinnacle Consensus Probe [R] ← R&D Session 18 task
- **What:** Check if Pinnacle appears in Odds API response on current tier. If yes, add to consensus.
- **Simple test:** Fetch any NBA game and `print([b["key"] for b in game["bookmakers"]])`. Look for "pinnacle".
- **If available:** Add "pinnacle" to top of `_BOOK_PREFERENCE` in `odds_fetcher.py`. Consensus auto-improves.
- **If not available:** Document API tier cost to unlock. User decision.
- **Owner:** R&D 10-minute probe. Report findings in HANDOFF.md.

### R&D EXP 3: Sharp Score Calibration Study [ ]
- **What:** Validate that Sharp Score weights (Edge 40 / RLM 25 / Eff 20 / Sit 15) are optimal.
  Use Supabase bet history outcomes (when 30+ bets have results) to run Pearson correlation per component.
- **Question:** Does efficiency_gap actually predict outcome? Is RLM 25 pts too high or too low?
- **Output:** Weight adjustment recommendations or confirmation that current weights are correct.
- **Gate:** Need 30-50 bets with recorded outcomes. Check Supabase data volume first.
- **Owner:** R&D analysis script. No v36 changes until validated.

### R&D EXP 4: Live Weather API for NFL Wind [ ]
- **See SECTION 1 GAP 1 above.** R&D builds standalone module. Aug 2026 deadline.

### R&D EXP 5: Multi-Game Parlay Identification [ ]
- **What:** Identify 2-leg parlay combinations from the ranked slate where:
  (a) events are independent (different games), (b) both bets pass Sharp Score threshold,
  (c) combined Kelly suggests positive parlay EV.
- **Math:** parlay_prob = prob_a × prob_b. parlay_payout = (payout_a + 1) × (payout_b + 1) - 1.
  EV = parlay_prob × parlay_payout - (1 - parlay_prob). Only show if EV > 0.
- **Where it lands:** New "Parlay Builder" tab in Streamlit app.
- **Owner:** R&D prototypes. No v36 until validated.

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

### R&D EXP 8: Alternate Line Parsing [ ]
- **What:** Parse alternate spreads/totals (e.g. -3 at -140 vs standard -6.5 at -110).
  Higher consensus dispersion on alt lines = potentially larger real edges.
- **Risk:** Alt lines are often traps — juice reflects true price adjustment. Needs validation first.
- **Owner:** R&D probe only. Do not promote without CLV validation.

### R&D EXP 9: College Baseball Probe [ ]
- **What:** Check Odds API coverage for `baseball_ncaa`. If < 5 books on average → skip.
  Consensus signal breaks down below 3 books. Market is thin.
- **Owner:** R&D 10-minute probe. Report book count per game.

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

### UI 2: Odds Comparison Page [ ]
- **What:** Side-by-side book prices for any game in the current slate.
  Line shopper view — shows where each book is on spread/total/ML.
- **Data source:** `raw_games` already fetched by pipeline. No new API calls.
- **Value:** Helps user identify best book to bet manually when Titanium flags an edge.

### UI 3: Refresh Injuries Button (post-B2) [ ]
- **What:** On-demand re-fetch of ESPN injury data mid-session.
  Updates injury_leverage in session state, re-ranks bets without full pipeline re-run.
- **Dependencies:** B2 injury leverage must be promoted first (Gate: 2026-03-04).

### UI 4: Parlay Builder Tab (post-R&D EXP 5) [ ]
- **What:** Displays valid 2-leg parlay combinations from current slate with EV calculation.
- **Dependencies:** R&D EXP 5 must be validated first.

### UI 5: CLV Column in Bet History [ ]
- **What:** Add CLV % column to Bet History log once CLV tracker is built.
- **Dependencies:** R&D EXP 1 (CLV Tracker) must be built first.

---

## SECTION 5 — PERSISTENT RLM UPGRADE (HIGH VALUE)
See CEILING 3 above. This is architecturally significant enough to call out separately.

### RLM 2.0: Persistent Open-Price Store [ ]
- **New table in Supabase:** `price_history` — columns: event_id, side, open_price, first_seen_at.
- **New file in v36:** `data/price_history_store.py` — same pattern as `bet_history_store.py`.
- **Modified:** `odds_fetcher.cache_open_prices()` — check DB first, only write if event_id not seen.
- **Result:** RLM fires on multi-day line movement, not just intra-session. Major signal upgrade.
- **Owner:** R&D designs schema. v36 builds and wires.

---

## STATUS LEGEND
[ ] = Not started
[R] = In R&D
[~] = Partially done / gated
[x] = Complete

## GATE DATES
- 2026-03-04: B2 ESPN injury endpoint stability check (GAP 2, CEILING 2, UI 3)
- 2026-03-27: MLB season starts (efficiency data already promoted — no action needed)
- 2026-08-01: NFL/NCAAF season prep window opens (GAP 1, R&D EXP 4, R&D EXP 7)
