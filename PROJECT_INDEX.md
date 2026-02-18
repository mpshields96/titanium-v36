# TITANIUM V36.1 — Project Index
Generated: 2026-02-18

## Quick Start
```bash
python3 -m pytest tests/ -v          # Run all 65 tests (must pass before each session)
python3 run_pipeline.py              # Full pipeline CLI test (needs ODDS_API_KEY env var)
python3 ncaab_parser.py              # NCAAB collar-filter pipeline test
streamlit run app.py                 # Launch UI (Session 5+)
```

## Project Structure
```
titanium-v36/
├── CLAUDE.md                    # Architecture rules (one file = one job)
├── SESSION_STATE.md             # Session memory & resume instructions
├── PROJECT_INDEX.md             # This file (94% token reduction vs full codebase read)
├── requirements.txt             # Dependencies
├── run_pipeline.py              # End-to-end CLI test script
├── .streamlit/
│   └── secrets.toml             # API key (NEVER commit)
├── app.py                       # Streamlit UI layer (stub → Session 5)
├── odds_fetcher.py              # Odds API interface
├── edge_calculator.py           # Betting math & collar enforcement
├── bet_ranker.py                # Diversity engine & Sharp Score ranking
├── ncaab_parser.py              # NCAAB game parser + collar filter
├── originator_engine.py         # Monte Carlo simulation (stable — do not touch)
├── data/
│   ├── efficiency_feed.py       # KenPom/Barttorvik static data (25 NCAAB teams)
│   └── team_stats_bunker.py     # Fallback NBA/NFL stats (static, updated weekly)
└── tests/
    ├── test_validation.py       # 45 core math tests
    └── test_odds_fetcher.py     # 20 API fetcher tests
```

---

## Core Modules

### odds_fetcher.py — Odds API Interface
No math, no UI. All HTTP calls only.

| Function | Returns | Notes |
|----------|---------|-------|
| `fetch_game_lines(sport_key)` | `list` | 1 API call per sport |
| `fetch_sport(sport)` | `list` | Friendly name wrapper ("NCAAB" → basketball_ncaab) |
| `fetch_batch_odds(sport_key, api_key)` | `list` | Legacy wrapper (Session 2) |
| `preferred_book(bookmakers)` | `dict` | DraftKings > FanDuel > BetMGM > BetRivers > Caesars |
| `all_books(bookmakers)` | `list` | All books sorted by preference (used by consensus edge) |
| `get_quota_status()` | `str` | used/remaining/last_call_cost report |

Classes: `QuotaTracker` — tracks API usage per session.

---

### edge_calculator.py — Betting Math
No API calls, no UI. All probability math only.

| Function | Returns | Notes |
|----------|---------|-------|
| `passes_collar(american_odds)` | `bool` | -180 to +150 only |
| `_implied_probability(american_odds)` | `float` | Vig-inclusive |
| `no_vig_probability(odds_a, odds_b)` | `(float, float)` | Fair probs both sides |
| `calculate_edge(titanium_prob, market_odds)` | `float` | model - implied |
| `fractional_kelly(win_prob, odds, fraction=0.25)` | `float` | 0.25x Kelly, capped |
| `calculate_sharp_score(edge_pct, rlm_confirmed, efficiency_gap, ...)` | `(float, dict)` | 0-100 composite |
| `sharp_to_size(sharp_score)` | `str` | NUCLEAR/STANDARD/LEAN tier label |
| `run_nemesis(bet, sport)` | `dict` | Adversarial counter-thesis |
| `parse_game_markets(game, sport)` | `list[BetCandidate]` | **Main entry point** — consensus edge detection |
| `_consensus_fair_prob(team, market_key, side, bookmakers)` | `(float, float, int)` | mean, std_dev, n_books |

Kill switches (all stubbed — Session 5): `nba_kill_switch`, `nfl_kill_switch`, `ncaab_kill_switch`, `soccer_kill_switch`

Classes: `BetCandidate` — dataclass with sport, matchup, market_type, target, line, price, edge_pct, win_prob, market_implied, fair_implied, kelly_size, signal, event_id, commence_time, book, sharp_score, sharp_breakdown, nemesis, simulation.

---

### bet_ranker.py — Ranking & Diversity
No API calls, no math beyond sharp score. Dedup + rank + top-10 only.

| Function | Returns | Notes |
|----------|---------|-------|
| `rank_bets(candidates, rlm_data, efficiency_data, situational_data)` | `list[BetCandidate]` | **Main entry point** |
| `format_bet_table(bets)` | `str` | CLI/Streamlit-ready output |
| `_deduplicate_markets(bets)` | `list` | Keep higher edge side |
| `_apply_diversity(bets, max_per_sport=3)` | `list` | Cap + 60% concentration |

Constants: `MAX_TOTAL_BETS=10`, `MAX_PER_SPORT=3`, `SPORT_CONCENTRATION_CAP=0.60`, `SHARP_THRESHOLD=40.0`

---

### ncaab_parser.py — NCAAB Game Parser
Collar filter + best-price extraction only. No edge calc, no UI.

| Function | Returns | Notes |
|----------|---------|-------|
| `parse_ncaab_games(raw_games)` | `list[NCAABBetOpportunity]` | Spreads + ML + Totals |
| `run_pipeline_test()` | `None` | Session 3 validation (1 API call) |

Classes: `NCAABBetOpportunity` — matchup, home_team, away_team, bet_type, team, line, odds, implied_prob, fair_prob, book, event_id, commence_time.

---

### data/efficiency_feed.py — KenPom/Barttorvik Static Data
No API calls, no math beyond scaling. Static data + lookup only.

| Function | Returns | Notes |
|----------|---------|-------|
| `get_efficiency_gap(home_team, away_team)` | `float` | 0-20 scale, 10.0 = even |
| `build_efficiency_data(games)` | `dict[str, float]` | event_id → gap, for rank_bets() |
| `get_team_data(team_name)` | `dict \| None` | adj_o, adj_d, adj_em, tempo |
| `list_teams()` | `list[str]` | 25 canonical names |

Teams: Duke, Kansas, Kentucky, Houston, UConn, Auburn, Michigan St, Marquette, Purdue, Tennessee, Texas, Gonzaga, Creighton, Illinois, Baylor, Indiana, Ole Miss, Virginia, Miami FL, Nebraska, DePaul, Bryant, Alabama St, Texas Southern. Unknown → 8.0 default.

---

### originator_engine.py — Monte Carlo (DO NOT TOUCH)
Trinity-weighted simulation. Stable and working. Touch only if explicitly asked.

| Function | Returns | Notes |
|----------|---------|-------|
| `run_trinity_simulation(mean, sport, line, ...)` | `SimulationResult` | 20/20/60 Trinity weighting |
| `run_poisson_matrix(home_xg, away_xg)` | `(float, float, float)` | Soccer: home_win, draw, away_win |
| `simulate_prop(season_avg, line, ...)` | `tuple` | Player prop over/under |

Known bug: `mean` input should be projected margin, not `bet.line` — tracked, not yet fixed.

---

### run_pipeline.py — End-to-End CLI Test
```
run_full_pipeline(sport_key, sport_label) → None
  [1] fetch_game_lines → [2] build_efficiency_data → [3] parse_game_markets
  → [4] rank_bets(efficiency_data=...) → [5] format_bet_table
```

---

## Non-Negotiable Rules

| Rule | Value |
|------|-------|
| Odds collar | -180 to +150 American only |
| Min edge | ≥ 3.5% |
| Kelly | 0.25x fraction |
| Kelly caps | >60% winprob → 2.0u max \| >54% → 1.0u \| else → 0.5u |
| Max bets | 10 total, 3 per sport, 60% concentration cap |
| Sharp Score tiers | ≥90 = NUCLEAR 2.0u \| ≥80 = STANDARD 1.0u \| else = LEAN 0.5u |
| Sharp threshold | 40 pts pre-nemesis (temp — raise to 75 when KenPom wired) |

Kill switches: NBA rest+spread | NFL wind+total | NCAAB 3P+away | Soccer drift (all stubbed)

---

## Session State

| Session | Status | Deliverable |
|---------|--------|-------------|
| 1 | ✅ | File structure, scaffolds |
| 2 | ✅ | odds_fetcher.py, 20 tests |
| 3 | ✅ | odds_fetcher upgrade, originator_engine, ncaab_parser, consensus edge |
| 4 | ✅ | bet_ranker.py, Sharp Score, nemesis, full pipeline live-tested |
| 5 | 🔲 | efficiency_feed promoted ✅ · kill switches · Streamlit UI · deploy |

Tests: **65 passing** (45 math + 20 fetcher) · Quota: ~18,322 remaining
