# TITANIUM V36.1 — Project Index
Generated: 2026-02-24 (V37 Reviewer Session 1 — Two-AI coordination system live)

## Quick Start
```bash
python3 -m pytest tests/ -v          # 163 tests — must pass before each session
python3 run_pipeline.py              # Full pipeline CLI test (needs ODDS_API_KEY env var)
python3 ncaab_parser.py              # NCAAB collar-filter pipeline test (1 API call)
streamlit run app.py                 # Launch Streamlit UI locally
grep -n "def calculate_edges" edge_calculator.py  # One def only — dead stub removed Session 13 cleanup
```

## Project Structure
```
titanium-v36/
├── CLAUDE.md                    # Architecture rules + session workflow
├── CLAUDE.local.md              # Private local context (not committed) — reviewer role, autonomous startup ritual
├── SESSION_STATE.md             # Session memory & resume instructions
├── PROJECT_INDEX.md             # This file (94% token reduction)
├── REVIEWER_PROMPT.md           # V37 Reviewer chat startup prompt — paste into new chat to resume seamlessly (NEW V37 S1)
├── requirements.txt             # streamlit, pytest, requests, pandas, numpy, scipy, supabase
├── run_pipeline.py              # End-to-end CLI test
├── docs/
│   └── MASTER_ROADMAP.md        # Feature roadmap + priority ordering (Session 20)
├── .streamlit/
│   ├── secrets.toml             # ODDS_API_KEY, SUPABASE_URL, SUPABASE_KEY (NEVER commit)
│   └── config.toml              # Native dark theme (Session 14) — gold/teal palette, monospace
├── app.py                       # Streamlit UI — 5 pages via st.navigation()
├── bet_card_renderer.py         # HTML card renderer (Session 14) — no math, no API
├── odds_fetcher.py              # Odds API + RLM cache + _extract_open_prices
├── edge_calculator.py           # Betting math, kill switches, pipeline entry point
├── bet_ranker.py                # Diversity engine + Sharp Score ranking
├── ncaab_parser.py              # NCAAB-specific game parser
├── originator_engine.py         # Monte Carlo — DO NOT TOUCH unless asked
├── data/
│   ├── __init__.py              # Empty — makes data/ a proper Python package (Session 14)
│   ├── efficiency_feed.py       # 234 teams (30 NBA + 80 NCAAB + 32 NHL + 30 MLB + 30 MLS + 32 NFL) — AdjEM static data
│   ├── kill_switch_feed.py      # Kill switch input stubs: rest, wind, 3PT%, drift, injury leverage
│   ├── bet_history_store.py     # Supabase bet_history persistence layer (Session 18)
│   ├── price_history_store.py   # Supabase price_history persistence layer — RLM 2.0 (Session 20)
│   ├── odds_comparator.py       # Odds Comparison data layer — build_odds_comparison() + to_dataframes() (Session 21)
│   ├── clv_store.py             # Supabase clv_history persistence layer — Closing Line Value tracking (Session 22)
│   ├── soccer_consensus.py      # 3-outcome vig removal for soccer h2h markets (Session 24)
│   ├── parlay_builder.py        # 2-leg parlay combo identification + EV ranking (Session 24)
│   └── team_stats_bunker.py     # Fallback static stats
└── tests/
    ├── test_validation.py           # 66 tests — math, collar, kelly, injury stubs, consensus badge, NHL/MLB/MLS/NFL efficiency, alias collision guards
    ├── test_odds_fetcher.py         # 40 tests — API, rest days, RLM, _extract_open_prices
    ├── test_price_history_store.py  # 10 tests — is_configured, record_new_events, inject_into_cache (Session 20)
    ├── test_clv_store.py            # 19 tests — record_clv_open, update_clv_close, fetch_clv_for_events, get_clv_summary (Session 22)
    ├── test_soccer_consensus.py     # 13 tests — american_to_implied, 3-way fair probs, std_dev (Session 24)
    └── test_parlay_builder.py       # 15 tests — _american_to_decimal, _parlay_ev, build_parlay_combos, format_parlay_table (Session 24)
```

---

## Supabase Tables

| Table | Purpose | Key columns |
|-------|---------|-------------|
| `bet_history` | Track bets placed, outcomes, P&L | event_id, matchup, market_type, price, edge_pct, result, profit |
| `price_history` | RLM 2.0 — first-ever-seen open prices per event | event_id (UNIQUE), home_price, away_price, first_seen_at |
| `clv_history` | Closing Line Value tracking — open vs closing implied prob | event_id, target, market_type (UNIQUE composite), open_price, closing_price, clv_pct |

All three tables gated behind `is_configured()` in their respective store modules. All Supabase I/O uses lazy imports to avoid breaking tests without credentials.

---

## Core Modules

### odds_fetcher.py — API + RLM Cache
No math, no UI. HTTP calls + session-scoped price cache.

| Function | Returns | Notes |
|----------|---------|-------|
| `fetch_game_lines(sport_key)` | `list` | 1 API call per sport |
| `fetch_sport(sport)` | `list` | Friendly name wrapper ("NCAAB" → basketball_ncaab) |
| `fetch_batch_odds(sport_key, api_key)` | `list` | Legacy wrapper |
| `preferred_book(bookmakers)` | `dict\|None` | DraftKings > FanDuel > BetMGM > BetRivers > Caesars |
| `all_books(bookmakers)` | `list` | All books sorted by preference |
| `get_quota_status()` | `str` | used/remaining/last_call_cost |
| `_extract_open_prices(game)` | `dict[str,float]` | **Session 20** — extract {"home": price, "away": price}; tries PREFERRED_BOOKS order; returns {} if no usable prices |
| `cache_open_prices(games)` | `int` | Freeze open prices (first call wins, frozen after) |
| `get_open_price(event_id, side)` | `float\|None` | Return cached open price |
| `clear_open_price_cache()` | `None` | Reset — call in test setup_method |
| `compute_rlm(games)` | `dict[str,bool]` | **Session 13** — passive RLM, 3% implied prob threshold |
| `compute_rest_days_from_schedule(raw_games)` | `dict[str,int\|None]` | **Session 11** — B2B detection from commence_time diffs |

Classes: `QuotaTracker` — tracks API usage per session.

**Circular import warning:** `edge_calculator` imports `odds_fetcher`. Never import `edge_calculator` from `odds_fetcher`. `_extract_open_prices` is imported by `price_history_store` via deferred import for the same reason.

---

### edge_calculator.py — Betting Math & Kill Switches
No API calls, no UI. Math + kill switch logic only.

| Function | Returns | Notes |
|----------|---------|-------|
| `calculate_edges(sport, raw_games, louisiana_mode, min_edge)` | `list[BetCandidate]` | Single entry point (dead stub removed Session 13) |
| `passes_collar(american_odds)` | `bool` | -180 to +150 only |
| `_implied_probability(american_odds)` | `float` | Vig-inclusive |
| `no_vig_probability(odds_a, odds_b)` | `(float, float)` | Fair probs both sides — 2-outcome |
| `calculate_edge(titanium_prob, market_odds)` | `float` | model − implied |
| `calculate_profit(odds, units)` | `float` | Profit in units |
| `fractional_kelly(win_prob, odds, fraction=0.25)` | `float` | 0.25x Kelly, capped |
| `calculate_sharp_score(edge_pct, rlm_confirmed, efficiency_gap, ...)` | `(float, dict)` | 0–100 composite |
| `sharp_to_size(sharp_score)` | `str` | NUCLEAR/STANDARD/LEAN tier label |
| `run_nemesis(bet, sport)` | `dict` | Display-only annotation — no scoring effect |
| `parse_game_markets(game, sport)` | `list[BetCandidate]` | Consensus edge detection. **Session 24:** soccer h2h uses `consensus_fair_prob_3way()` (3-way vig removal); non-soccer h2h uses 2-outcome `_consensus_fair_prob()`. |
| `nba/nfl/ncaab/soccer_kill_switch(...)` | `(bool, str)` | All four wired |

Internal: `_SPORT_ROUTING` maps 12 sports → fetch key + kill family. `_apply_nba_kill(bet, schedule_rest)` overlays live rest days. `_is_soccer` flag in `parse_game_markets()` checks uppercase routing key set: `{EPL, LIGUE1, BUNDESLIGA, SERIE_A, LA_LIGA, MLS}`.

**BetCandidate fields:**
`sport, matchup, market_type, target, line, price, edge_pct, win_prob, market_implied, fair_implied, kelly_size, signal, event_id, commence_time, book, sharp_score, sharp_breakdown, nemesis, simulation, kill_reason, rest_days, opp_rest_days, std_dev`

`std_dev: float = 0.0` — std dev of vig-free probs across books (Session 16). Display-only via BOOKS badge. Zero score impact.

`kill_reason=""` = clean · `"FLAG:..."` = kept with warning · `"KILL:..."` = dropped

**Pipeline:** `calculate_edges(sport, raw_games=raw_games)` — pass pre-fetched games to skip internal fetch (zero double API calls).

---

### bet_ranker.py — Ranking & Diversity
No API calls, no math beyond Sharp Score. Dedup + rank + top-10 only.

| Function | Returns | Notes |
|----------|---------|-------|
| `rank_bets(candidates, rlm_data, efficiency_data, situational_data)` | `list[BetCandidate]` | Main entry point |
| `format_bet_table(bets)` | `str` | CLI/Streamlit-ready output |
| `_deduplicate_markets(bets)` | `list` | Keep higher-edge side only |
| `_apply_diversity(bets, max_per_sport=3)` | `list` | Cap + 60% concentration guard |

Constants: `MAX_TOTAL_BETS=10` · `MAX_PER_SPORT=3` · `SPORT_CONCENTRATION_CAP=0.60` · `SHARP_THRESHOLD=45.0`

**Nemesis is display-only** — `run_nemesis()` populates `bet.nemesis` for rendering. Zero effect on score or survival.

---

### bet_card_renderer.py — HTML Card Renderer (Session 14)
No API calls, no math. Pure HTML string generation for Streamlit.

| Function | Returns | Notes |
|----------|---------|-------|
| `render_bet_card(bet, rank=0)` | `str` | HTML card for one BetCandidate |
| `render_bet_slate(bets, title="Today's Slate")` | `str` | Full slate — header + all cards + footer |
| `render_slate_header(bets, title="")` | `str` | **Session 18** — header fragment only |
| `render_slate_footer(bets)` | `str` | **Session 18** — footer fragment only (total Kelly) |

Key helpers: `_consensus_badge_html(std_dev)` — BOOKS TIGHT/MODERATE/WIDE · `_rlm_badge_html(breakdown)` — violet RLM badge · `_score_bar_html(...)` — Edge/RLM/Eff/Sit decomposition bar

Tier colours: NUCLEAR amber `#F59E0B` · STANDARD blue `#3B82F6` · LEAN teal `#14B8A6`

**Design:** Inline styles only (Streamlit strips `<style>` tags). Use `st.html()` for full slate — `st.markdown(unsafe_allow_html=True)` sandboxes large HTML in Streamlit 1.54+.

---

### data/price_history_store.py — RLM 2.0 Persistence (Session 20)
No math, no UI. Supabase persistence for first-ever-seen open prices across sessions.

| Function | Returns | Notes |
|----------|---------|-------|
| `is_configured()` | `bool` | True if Supabase credentials present |
| `record_new_events(games)` | `int` | Write first-seen prices; ON CONFLICT DO NOTHING |
| `inject_into_cache(games)` | `int` | Pre-seed `_OPEN_PRICE_CACHE` before `cache_open_prices()` runs |
| `purge_old_events(days_old=14)` | `int` | Delete rows older than N days |
| `price_history_status()` | `str` | One-line status with row count |

Uses deferred import for `odds_fetcher._extract_open_prices` (circular import guard).

---

### data/odds_comparator.py — Odds Comparison Data Layer (Session 21)
No API calls, no math, no UI. Pure transformation of raw game dicts. No pandas dependency.

| Function | Returns | Notes |
|----------|---------|-------|
| `build_odds_comparison(game)` | `dict` | All books, all markets, best_price per side, line_split flag |
| `to_dataframes(comp)` | `(h2h_rows, spread_rows, total_rows)` | List-of-dicts for `st.dataframe()` |

`_BOOK_PREFERENCE` mirrors `odds_fetcher.PREFERRED_BOOKS` — sync if Pinnacle is ever added.

---

### data/clv_store.py — Closing Line Value Tracking (Session 22)
No math, no UI. Supabase persistence for empirical edge validation.

| Function | Returns | Notes |
|----------|---------|-------|
| `is_configured()` | `bool` | True if Supabase credentials present |
| `record_clv_open(event_id, target, market_type, open_price, sport, matchup)` | `dict\|None` | Write entry price; UNIQUE constraint prevents duplicates; None on conflict |
| `update_clv_close(event_id, target, market_type, closing_price)` | `dict\|None` | Fill closing_price + compute clv_pct (built, not yet wired — future) |
| `fetch_clv_for_events(event_ids)` | `dict[tuple,dict]` | Batch fetch keyed by (event_id, target, market_type) |
| `get_clv_summary()` | `dict` | n, avg_clv_pct, positive_rate, verdict |

Verdict thresholds: `avg >= 1.5 AND pos_rate >= 0.55` → EDGE CONFIRMED · `avg >= 0.5 AND pos_rate >= 0.50` → MARGINAL · else → NO EDGE DETECTED

**Key design:** `open_price = bet.price` — NOT `get_open_price()` (team-name key collision across h2h/spreads markets).

---

### data/soccer_consensus.py — 3-way Vig Removal (Session 24)
No API calls, no UI. Math only — correct vig removal for soccer h2h markets.

| Function | Returns | Notes |
|----------|---------|-------|
| `american_to_implied(american)` | `float` | Raw implied probability (includes vig) |
| `consensus_fair_prob_3way(home_prices, draw_prices, away_prices)` | `dict` | Consensus fair probs for 3-outcome market. Keys: fair_home, fair_draw, fair_away, std_dev, n_books |

Called from `parse_game_markets()` for soccer h2h only (`_is_soccer` flag). All non-soccer h2h and all spreads/totals use existing 2-outcome `no_vig_probability()`. Draw outcome name in Odds API = `"Draw"` (verified in R&D probe).

**Why this exists:** `_consensus_fair_prob()` used 2-way vig removal on 3-outcome soccer markets, inflating fair_home by avg +13.46pp and fair_away by avg +10.42pp (live EPL probe, 198 book-game pairs). Fixed Session 24.

---

### data/parlay_builder.py — 2-leg Parlay Combos (Session 24)
No API calls, no UI. Math only — parlay combo identification + EV ranking.

| Function | Returns | Notes |
|----------|---------|-------|
| `_american_to_decimal(american)` | `float` | American → decimal odds (includes stake return) |
| `_parlay_ev(prob_a, price_a, prob_b, price_b)` | `dict` | 2-leg parlay metrics: parlay_prob, parlay_payout, parlay_ev |
| `build_parlay_combos(bets)` | `list[dict]` | All valid 2-leg combos (different event_id) with positive EV, sorted descending |
| `format_parlay_table(combos)` | `str` | CLI-printable table. "No positive-EV..." message if empty. |

Input: `list[dict]` — BetCandidate-style (keys: event_id, target, market_type, win_prob, price, edge_pct, matchup).

**v36 call site shim:** `build_parlay_combos([vars(b) for b in ranked_bets])` — converts BetCandidate dataclass → dict. Do NOT change parlay_builder to accept dataclasses (no v36-specific imports in data/ modules).

**Math:** `parlay_prob = prob_a × prob_b` · `parlay_payout = (payout_a+1)(payout_b+1) - 1` · `EV = parlay_prob × payout - (1-parlay_prob)`. Only positive-EV combos returned.

---

### data/bet_history_store.py — Bet Tracking Persistence (Session 18)

| Function | Returns | Notes |
|----------|---------|-------|
| `is_configured()` | `bool` | True if Supabase credentials present |
| `insert_bet(...)` | `dict\|None` | Write new tracked bet row |
| `fetch_pending_bets()` | `list` | All bets without a result |
| `fetch_bets(limit=500)` | `list` | Full history log |
| `update_outcome(row_id, result, profit)` | `bool` | Mark result + profit |
| `compute_pnl_summary(bets)` | `dict` | wins, losses, pushes, roi, equity_curve, roi_by_sport, winrate_by_market |

---

### data/efficiency_feed.py — AdjEM Static Data (234 teams)

| Function | Returns | Notes |
|----------|---------|-------|
| `get_efficiency_gap(home_team, away_team)` | `float` | 0–20 scale, 10.0 = even |
| `build_efficiency_data(games)` | `dict[str,float]` | event_id → gap, for rank_bets() |
| `get_team_data(team_name)` | `dict\|None` | adj_o, adj_d, adj_em, tempo |
| `list_teams(league=None)` | `list[str]` | "NBA" / "NCAAB" / "NHL" / "MLB" / "MLS" / "NFL" / None = all |

Coverage: 30 NBA + 80 NCAAB + 32 NHL + 30 MLB + 30 MLS + 32 NFL = **234 teams**. Unknown teams → 8.0 default gap. Single source of truth for NCAAB tempo.

---

### data/kill_switch_feed.py — Kill Switch Input Layer

| Function | Returns | Notes |
|----------|---------|-------|
| `get_nba_kill_inputs(...)` | `dict` | Rest days + B2B + pace std dev — 30 teams |
| `get_nfl_kill_inputs(...)` | `dict` | Wind mph — 32 teams + full stadium map |
| `get_ncaab_kill_inputs(...)` | `dict` | 3PT reliance (80 teams) · tempo from efficiency_feed |
| `get_soccer_kill_inputs(...)` | `dict` | Drift computed at runtime from open-price cache |
| `get_nba_injury_leverage(...)` | `(float, bool)` | Stub — always `(0.0, False)`. Gate: ESPN B2 ~2026-03-04 |
| `get_ncaab_injury_leverage(...)` | `(float, bool)` | Stub — always `(0.0, False)`. No ESPN college data. |

---

### originator_engine.py — Monte Carlo (DO NOT TOUCH)
Trinity-weighted simulation. Touch only if explicitly asked.
Known bug: `mean` input receives `bet.line` instead of projected margin. Tracked in R&D.

---

### app.py — Streamlit UI (5 pages)
No business logic, no API calls, no math.

Pages: `page_live_analysis()` · `page_bet_history()` · `page_pnl_tracker()` · `page_odds_comparison()` · `page_parlay_builder()` (Session 24)

`run_pipeline()` flow: pre-fetch `raw_games` → accumulate `all_raw_games` → RLM 2.0 store → `cache_open_prices()` → `compute_rlm()` → `calculate_edges(raw_games=raw_games)` → `rank_bets(rlm_data=rlm_data)`. **One API call per sport.**

Session 22: `record_clv_open(open_price=bet.price)` wired after Track Bet. Bet History History Log = 9 columns with CLV.

Session 24: `page_parlay_builder()` reads `st.session_state["results"]`, converts with `[vars(b) for b in ranked]`, calls `build_parlay_combos()`. Inert until pipeline runs.

---

## Sharp Score Formula

```
score = edge_pts(0–40) + rlm_pts(0–25) + efficiency_pts(0–20) + situational_pts(0–15)
```

| Component | Source | Live? |
|-----------|--------|-------|
| edge_pct | consensus books | ✅ |
| rlm_confirmed | `_OPEN_PRICE_CACHE` seeded from Supabase `price_history` | ✅ |
| efficiency_gap | efficiency_feed (234 teams) | ✅ |
| rest_edge | schedule rest days | ✅ NBA only |
| injury_leverage | stubs | ❌ always 0.0 |
| motivation | — | ❌ always 0 |
| matchup_score | — | ❌ always 0 |

Threshold: **45 pts**. Raise to 50–55 after RLM fires 5+ live sessions.
Tiers: NUCLEAR ≥90 = 2.0u · STANDARD ≥80 = 1.0u · LEAN ≥45 = 0.5u

---

## Kill Switches

| Sport | Condition | Action |
|-------|-----------|--------|
| NBA | rest_disadvantage AND spread < −4 | KILL spread |
| NFL | wind > 15mph AND total > 42 | FORCE UNDER |
| NCAAB | 3PT reliance > 40% AND is_away | KILL (80-team coverage) |
| Soccer | drift > 10% implied prob | KILL |

---

## Non-Negotiable Rules

| Rule | Value |
|------|-------|
| Odds collar | −180 to +150 American only |
| Min edge | ≥ 3.5% |
| Kelly | 0.25x fractional |
| Kelly caps | >60% winprob → 2.0u · >54% → 1.0u · else → 0.5u |
| Max bets | 10 total · 3 per sport · 60% concentration cap |
| Math > Narrative | Nemesis = display only. Kill switches = math only. No narrative inputs. |

---

## Tests

| File | Count | Covers |
|------|-------|--------|
| `test_validation.py` | 66 | collar, kelly, edge math, profit calc, injury stubs, consensus badge, NHL/MLB/MLS/NFL efficiency, alias collision guards |
| `test_odds_fetcher.py` | 40 | API fetch, preferred book, rest days, RLM, _extract_open_prices |
| `test_price_history_store.py` | 10 | is_configured, record_new_events, inject_into_cache (Session 20) |
| `test_clv_store.py` | 19 | record_clv_open, update_clv_close, fetch_clv_for_events, get_clv_summary (Session 22) |
| `test_soccer_consensus.py` | 13 | american_to_implied, 3-way fair probs, std_dev, validation (Session 24) |
| `test_parlay_builder.py` | 15 | _american_to_decimal, _parlay_ev, build_parlay_combos, format_parlay_table (Session 24) |
| **Total** | **163** | all passing |

---

## Session State

| Session | Status | Deliverable |
|---------|--------|-------------|
| 1–4 | ✅ | Scaffolds, odds_fetcher, edge_calculator, bet_ranker, full pipeline |
| 5–10 | ✅ | efficiency_feed, kill switches, UI, multi-page, NCAAB 80-team, Streamlit Cloud |
| 11 | ✅ | `compute_rest_days_from_schedule()`, `_apply_nba_kill()` live rest, `st.navigation()` |
| 12 | ✅ | Nemesis demoted display-only, `rest_edge` live in Sharp Score, NCAAB 80-team kill switch |
| 13 | ✅ | `SHARP_THRESHOLD` 40→45, `compute_rlm()` passive RLM, end-to-end pipeline wiring |
| 14 | ✅ | `bet_card_renderer.py` promoted from R&D, `.streamlit/config.toml` dark theme, `data/__init__.py` |
| 15 | ✅ | Feature backlog saved, /sc:estimate B+C+F, session transition prep |
| 16 | ✅ | Injury leverage stubs, `std_dev` on BetCandidate, BOOKS badge on card |
| 17 | ✅ | NHL efficiency data — 32 teams, GF60-GA60 × 10 AdjEM proxy |
| 18 | ✅ | `page_bet_history()` full impl, TRACK BET on cards, `render_slate_header/footer` |
| 19 | ✅ | `efficiency_feed.py` MLB/MLS/NFL (234 teams), Hawks alias fix, 11 new tests |
| 20 | ✅ | `data/price_history_store.py` (RLM 2.0), `_extract_open_prices()`, `page_pnl_tracker()`, `docs/MASTER_ROADMAP.md` |
| 21 | ✅ | `data/odds_comparator.py` (R&D promotion), `page_odds_comparison()`, app.py cleanup |
| 22 | ✅ | `data/clv_store.py` (CLV tracking), `clv_history` Supabase table, 19 new tests — **135 total** |
| 23 | ✅ | CLAUDE.md `.not_` mock pattern, PROJECT_INDEX + SESSION_STATE + MASTER_ROADMAP sync, housekeeping |
| 24 | ✅ | `data/soccer_consensus.py` (3-way vig removal), `data/parlay_builder.py` (2-leg combos), `page_parlay_builder()` — **163 total** |
| 25 | ✅ | Architecture transition: v36 chat → Reviewer/Auditor role. R&D chat RETIRED. Agentic sandbox is primary builder. |
| V37 S1 | ✅ | Reviewer role activated. Two-AI coordination via REVIEW_LOG.md confirmed live. Sandbox Sessions 23+24 APPROVED. Schema review for Advanced Analytics written. REVIEWER_PROMPT.md created. v36 compatibility rule established. |

Last commit: `a2a9b45` · Tests: **163 passing** · Quota: ~16,663 remaining
V37 Reviewer Session 1 complete (2026-02-24). Sandbox Session 25 in progress (Advanced Analytics build).
**NEW REVIEWER CHAT:** Paste REVIEWER_PROMPT.md contents as opening message. No other context needed.
B2 gate opens 2026-03-04 — check espn_stability.log on that date. SHARP_THRESHOLD raise gated at 5 live RLM fires (0/5).
