# TITANIUM V36.1 — Project Index
Generated: 2026-02-19 (Session 17 post-session)

## Quick Start
```bash
python3 -m pytest tests/ -v          # 95 tests — must pass before each session
python3 run_pipeline.py              # Full pipeline CLI test (needs ODDS_API_KEY env var)
python3 ncaab_parser.py              # NCAAB collar-filter pipeline test (1 API call)
streamlit run app.py                 # Launch Streamlit UI locally
grep -n "def calculate_edges" edge_calculator.py  # One def only — dead stub removed Session 13 cleanup
```

## Project Structure
```
titanium-v36/
├── CLAUDE.md                    # Architecture rules + session workflow
├── SESSION_STATE.md             # Session memory & resume instructions
├── PROJECT_INDEX.md             # This file (94% token reduction)
├── requirements.txt             # streamlit, pytest, requests, pandas, numpy, scipy
├── run_pipeline.py              # End-to-end CLI test
├── .streamlit/
│   ├── secrets.toml             # ODDS_API_KEY (NEVER commit)
│   └── config.toml              # Native dark theme (Session 14) — gold/teal palette, monospace
├── app.py                       # Streamlit UI — 4 pages via st.navigation()
├── bet_card_renderer.py         # HTML card renderer (Session 14) — no math, no API
├── odds_fetcher.py              # Odds API + RLM cache
├── edge_calculator.py           # Betting math, kill switches, pipeline entry point
├── bet_ranker.py                # Diversity engine + Sharp Score ranking
├── ncaab_parser.py              # NCAAB-specific game parser
├── originator_engine.py         # Monte Carlo — DO NOT TOUCH unless asked
├── data/
│   ├── __init__.py              # Empty — makes data/ a proper Python package (Session 14)
│   ├── efficiency_feed.py       # 142 teams (30 NBA + 80 NCAAB + 32 NHL) — AdjEM static data
│   ├── kill_switch_feed.py      # Kill switch input stubs: rest, wind, 3PT%, drift, injury leverage
│   └── team_stats_bunker.py     # Fallback static stats
└── tests/
    ├── test_validation.py       # 55 tests — math, collar, kelly, injury stubs, consensus badge, NHL efficiency
    └── test_odds_fetcher.py     # 40 tests — API, rest days, RLM
```

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
| `cache_open_prices(games)` | `int` | Freeze open prices (first call wins, frozen after) |
| `get_open_price(event_id, side)` | `float\|None` | Return cached open price |
| `clear_open_price_cache()` | `None` | Reset — call in test setup_method |
| `compute_rlm(games)` | `dict[str,bool]` | **Session 13** — passive RLM, 3% implied prob threshold |
| `compute_rest_days_from_schedule(raw_games)` | `dict[str,int\|None]` | **Session 11** — B2B detection from commence_time diffs |

Classes: `QuotaTracker` — tracks API usage per session.

**Circular import warning:** `edge_calculator` imports `odds_fetcher`. Never import `edge_calculator` from `odds_fetcher`.

---

### edge_calculator.py — Betting Math & Kill Switches
No API calls, no UI. Math + kill switch logic only.

| Function | Returns | Notes |
|----------|---------|-------|
| `calculate_edges(sport, raw_games, louisiana_mode, min_edge)` | `list[BetCandidate]` | Single entry point (dead stub removed Session 13) |
| `passes_collar(american_odds)` | `bool` | -180 to +150 only |
| `_implied_probability(american_odds)` | `float` | Vig-inclusive |
| `no_vig_probability(odds_a, odds_b)` | `(float, float)` | Fair probs both sides |
| `calculate_edge(titanium_prob, market_odds)` | `float` | model − implied |
| `fractional_kelly(win_prob, odds, fraction=0.25)` | `float` | 0.25x Kelly, capped |
| `calculate_sharp_score(edge_pct, rlm_confirmed, efficiency_gap, ...)` | `(float, dict)` | 0–100 composite |
| `sharp_to_size(sharp_score)` | `str` | NUCLEAR/STANDARD/LEAN tier label |
| `run_nemesis(bet, sport)` | `dict` | Display-only annotation — no scoring effect |
| `parse_game_markets(game, sport)` | `list[BetCandidate]` | Consensus edge detection |
| `nba/nfl/ncaab/soccer_kill_switch(...)` | `(bool, str)` | All four wired |

Internal: `_SPORT_ROUTING` maps 12 sports → fetch key + kill family. `_apply_nba_kill(bet, schedule_rest)` overlays live rest days.

**BetCandidate fields:**
`sport, matchup, market_type, target, line, price, edge_pct, win_prob, market_implied, fair_implied, kelly_size, signal, event_id, commence_time, book, sharp_score, sharp_breakdown, nemesis, simulation, kill_reason, rest_days, opp_rest_days, std_dev`

`std_dev: float = 0.0` — std dev of vig-free probs across books (Session 16). Passed from `_consensus_fair_prob()` at 3 call sites. Display-only via BOOKS badge. Zero score impact.

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

**Nemesis is display-only** — `run_nemesis()` populates `bet.nemesis` for card rendering. Zero effect on score or survival.

---

### bet_card_renderer.py — HTML Card Renderer (Session 14)
No API calls, no math. Pure HTML string generation for Streamlit.

| Function | Returns | Notes |
|----------|---------|-------|
| `render_bet_card(bet, rank=0)` | `str` | HTML card for one BetCandidate — safe for `st.markdown(..., unsafe_allow_html=True)` |
| `render_bet_slate(bets, title="Today's Slate")` | `str` | Full slate — header + all cards + total Kelly footer |

Internal helpers (not public API):

| Helper | Purpose |
|--------|---------|
| `_tier_config(signal)` | Lookup colour/label config dict for a signal string |
| `_rlm_badge_html(breakdown)` | Violet RLM badge — shown only when `breakdown["rlm"] > 0` |
| `_consensus_badge_html(std_dev)` | **Session 16** — BOOKS: TIGHT/MODERATE/WIDE badge. `<0.02` green · `0.02–0.04` amber · `>0.04` red · `0.0` empty |
| `_kill_reason_banner_html(kill_reason, accent)` | FLAG → amber advisory · KILL/FORCE_UNDER → red error · `""` → empty |
| `_nemesis_html(nemesis, text_color)` | Nemesis counter-thesis block (display-only, Session 12) |
| `_score_bar_html(score, breakdown, accent)` | Mini decomposition bar: Edge/RLM/Eff/Sit segments |
| `_fmt_price(price)` | American odds with explicit sign (`+115`, `-110`) |

Tier colour coding:

| Signal | Colour | Unit |
|--------|--------|------|
| `NUCLEAR_2.0U` | Amber `#F59E0B` | 2.0u |
| `STANDARD_1.0U` | Blue `#3B82F6` | 1.0u |
| `LEAN_0.5U` | Teal `#14B8A6` | 0.5u |
| `PASS` | Grey `#6B7280` | — |

**Design constraints:** Pure stdlib. Inline styles only (Streamlit strips `<style>` tags from markdown). Font stack: `IBM Plex Mono`, `Fira Code`, monospace.

---

### data/efficiency_feed.py — AdjEM Static Data (234 teams)
No API calls. Static data + lookup only.

| Function | Returns | Notes |
|----------|---------|-------|
| `get_efficiency_gap(home_team, away_team)` | `float` | 0–20 scale, 10.0 = even |
| `build_efficiency_data(games)` | `dict[str,float]` | event_id → gap, for rank_bets() |
| `get_team_data(team_name)` | `dict\|None` | adj_o, adj_d, adj_em, tempo |
| `list_teams(league=None)` | `list[str]` | "NBA" / "NCAAB" / "NHL" / "MLB" / "MLS" / "NFL" / None = all 234 |

Coverage: 30 NBA (NetRtg×2.2 → AdjEM equiv) + 80 NCAAB (ACC/Big 12/Big Ten/SEC/Big East/WCC/MWC/A-10 + top mid-majors) + 32 NHL (GF60-GA60 × 10 → AdjEM equiv, Session 17) + 30 MLB (run differential → AdjEM proxy, Session 19) + 30 MLS (xG differential → AdjEM proxy, Session 19) + 32 NFL (point differential → AdjEM proxy, Session 19). Hawks alias collision fixed (Session 19). Unknown teams → 8.0 default gap.

**Single source of truth for NCAAB tempo** — `kill_switch_feed.get_ncaab_tempo()` calls `get_team_data()`. No duplicate data.

---

### data/kill_switch_feed.py — Kill Switch Input Layer
No API calls, no math. Stub data keyed to kill switch signatures.

| Function | Returns | Notes |
|----------|---------|-------|
| `get_nba_kill_inputs(bet_team, opp_team, spread, market_type, star_absent)` | `dict` | Rest days + B2B flag + pace std dev — 30 teams |
| `get_nfl_kill_inputs(home_team, total, backup_qb, market_type)` | `dict` | Wind mph — all 32 teams + full stadium map |
| `get_ncaab_kill_inputs(bet_team, opp_team, is_away, conf_tournament, market_type)` | `dict` | 3PT reliance (80 teams) · tempo from efficiency_feed |
| `get_soccer_kill_inputs(open_price, current_price, dead_rubber, key_creator_out, market_type)` | `dict` | Drift computed at runtime from open-price cache |
| `get_nba_injury_leverage(bet_team, opp_team)` | `(float, bool)` | **Session 16** stub — always `(0.0, False)`. Wire when ESPN B2 blockers cleared. |
| `get_ncaab_injury_leverage(bet_team, opp_team)` | `(float, bool)` | **Session 16** stub — always `(0.0, False)`. ESPN endpoint has no NCAAB data. |

All return dict + `data_live: bool`. When `data_live=False`, kill decision is stub — note "Data unavailable" in UI rather than trust the kill.

---

### originator_engine.py — Monte Carlo (DO NOT TOUCH)
Trinity-weighted simulation. Stable. Touch only if explicitly asked.

| Function | Returns | Notes |
|----------|---------|-------|
| `run_trinity_simulation(mean, sport, line, ...)` | `SimulationResult` | 20/20/60 Trinity weighting |
| `run_poisson_matrix(home_xg, away_xg)` | `(float, float, float)` | Soccer: home/draw/away |
| `simulate_prop(season_avg, line, ...)` | `tuple` | Player prop over/under |

Known bug: `mean` input should be projected margin, not `bet.line`. Tracked in R&D, not fixed.

---

### app.py — Streamlit UI (4 pages)
No business logic, no API calls, no math.

Pages via `st.navigation()` + `st.Page()` (Streamlit 1.36+):
- `page_live_analysis()` — fully functional — runs full pipeline, renders via `render_bet_slate()`
- `page_bet_history()` — stub
- `page_pnl_tracker()` — stub
- `page_odds_comparison()` — stub

`run_pipeline(selected_sports)` → pre-fetches `raw_games` per sport → `cache_open_prices()` → `compute_rlm()` → `calculate_edges(sport, raw_games=raw_games)` → `rank_bets(rlm_data=rlm_data)`. One API call per sport total.

**Session 14:** Inline `render_bet_card()` removed from `app.py`. Now imports `render_bet_slate` from `bet_card_renderer`. Theme handled by `.streamlit/config.toml` instead of inline CSS.

**Session 17 post-session:** `st.html()` replaces `st.markdown(unsafe_allow_html=True)` for card slate — Streamlit 1.54 sandboxes large HTML into a code block via `st.markdown`. Always use `st.html()` for full HTML documents/blocks. `eff_data.update()` now runs for all sports (was NCAAB-only — NHL efficiency data was built but never reaching `rank_bets()`). Header top padding 2rem → 3.5rem.

**Session 18:** `page_bet_history()` fully implemented (P&L strip, Pending Results + MARK RESULT flow, History Log table). Live Analysis now loops `st.html(render_bet_card(...))` per bet + `+ TRACK BET` button → `insert_bet()`. All Supabase I/O gated behind `is_configured()`. `render_slate_header()` and `render_slate_footer()` added to `bet_card_renderer.py`.

---

## Sharp Score Formula

```
score = edge_pts(0–40) + rlm_pts(0–25) + efficiency_pts(0–20) + situational_pts(0–15)
```

| Component | Source | Live? |
|-----------|--------|-------|
| edge_pct | consensus books | ✅ |
| rlm_confirmed | `_OPEN_PRICE_CACHE` (3% implied shift) | ✅ cold on 1st run |
| efficiency_gap | efficiency_feed (142 teams) | ✅ |
| rest_edge | schedule rest days | ✅ NBA only |
| injury_leverage | kill_switch_feed stubs (Session 16) | ❌ always 0.0 — ESPN B2 endpoint not stable |
| motivation | — | ❌ always 0 |
| matchup_score | — | ❌ always 0 |

Threshold: **45 pts** (~7.8% real edge). Raise to 50–55 after RLM fires consistently on live data.
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
| `test_validation.py` | 55 | collar, kelly, edge math, profit calc, injury stubs, consensus badge, NHL efficiency |
| `test_odds_fetcher.py` | 40 | API fetch, preferred book, rest days, RLM |
| **Total** | **95** | all passing |

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
| 15 | ✅ | Feature backlog saved, /sc:estimate B+C+F completed, session transition prep |
| 16 | ✅ | Injury leverage stubs (kill_switch_feed), `std_dev` on BetCandidate, BOOKS badge on card |
| 17 | ✅ | NHL efficiency data — 32 teams, GF60-GA60 × 10 AdjEM proxy, aliases for NY Rangers/Islanders + Vegas |
| 18 | ✅ | `page_bet_history()` full impl, `+ TRACK BET` on Live Analysis cards, `render_slate_header/footer` helpers |
| 19 | ✅ | `efficiency_feed.py` MLB/MLS/NFL promotion (234 teams), Hawks alias fix, 11 new tests |

Last commit: `e0e58d3` · Tests: **106 passing** · Quota: ~18,250 remaining
Next session (20): Await further instructions.
