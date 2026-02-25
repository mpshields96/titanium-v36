# PROMOTION_SPEC.md — V37 Reviewer Spec
# Written by: V37 Reviewer chat (titanium-v36)
# Date: 2026-02-24
# Target audience: Agentic sandbox builder chat
#
# PURPOSE:
#   Import path diffs, new packages, schema differences, test count deltas,
#   and V36 files that need editing for each sandbox module.
#   Sandbox reads this before building each promotion.
#
# RULE: Sandbox builds the code. Reviewer audits it. These are specs, not code.

---

## MODULE 1: `core/weather_feed.py` → v36

### Status: READY — DEFERRED (NFL off-season)
Not needed until Aug 2026 (NFL preseason window). Module is clean — build when NFL season approaches.

### What it does
Replaces the static `_NFL_WIND_FORECAST` dict in `data/kill_switch_feed.py` with live
Open-Meteo forecast data. Indoor/dome stadiums always return 0.0. Outdoor stadiums
fetch hourly wind at game time. Falls back to avg_wind static on any API failure.

### Import path change
- Sandbox: `from core.weather_feed import get_stadium_wind`
- V36 target: `from data.weather_feed import get_stadium_wind`
  → Place at `data/weather_feed.py` (data provider, no math, no UI — same tier as kill_switch_feed.py)

### New packages / deps
NONE. Uses only stdlib: `urllib.request`, `json`, `logging`, `time`, `datetime`, `typing`.
No new line in `requirements.txt` needed.

### Files to touch in v36
1. **ADD** `data/weather_feed.py` — copy sandbox `core/weather_feed.py` with one change:
   - Remove `from core.weather_feed import ...` docstring usage example → use `from data.weather_feed import ...`
   - All function signatures identical, no other changes.

2. **EDIT** `data/kill_switch_feed.py` — update `get_nfl_wind_mph()` and `get_nfl_kill_inputs()`:
   - `get_nfl_wind_mph()` currently reads from `_NFL_WIND_FORECAST` static dict
   - After promotion: call `get_stadium_wind(home_team, game_commence_utc)` from `data.weather_feed`
   - `get_nfl_kill_inputs()` needs a new `game_commence_utc: Optional[str] = None` param
     passed through to `get_nfl_wind_mph()` → `get_stadium_wind()`
   - `data_live`: set to `True` when Open-Meteo returns a value, `False` on fallback
   - KEEP `_NFL_WIND_FORECAST` as the fallback static dict (referenced inside weather_feed.py's `avg_wind`)
   - DO NOT delete the static dict from kill_switch_feed.py — weather_feed.py uses it as fallback values
     embedded in `NFL_STADIUMS["avg_wind"]` field (those values match the kill_switch_feed static dict).

3. **ADD** `tests/test_weather_feed.py`
   - Port sandbox's 24 tests, adjusting import path to `from data.weather_feed import ...`
   - All external calls (urllib) must be mocked — no live API calls in tests

4. **EDIT** `tests/test_validation.py` (optional) — add 2-3 regression tests for
   get_nfl_kill_inputs() with mocked get_stadium_wind() to confirm data_live=True path

### Test count delta
163 → 187 (+24 tests, all in `tests/test_weather_feed.py`)

### Call site in edge_calculator.py
`edge_calculator.py` calls `get_nfl_kill_inputs()` indirectly through `_KILL_ROUTER`.
No change needed in edge_calculator itself — the kill_switch_feed wrapper handles it.

### v36 compatibility check
- `get_nfl_kill_inputs()` signature change adds an optional param — backwards compatible.
- app.py currently passes no `game_commence_utc` to the NFL kill path. Wire-in:
  in the NFL section of `calculate_edges()`, pass `game["commence_time"]` through to
  `get_nfl_kill_inputs()`. This is a tactical implementation detail for the sandbox to spec.

### Priority
**DEFERRED — Aug 2026 window.** NFL season starts in September. Promote before preseason.

---

## MODULE 2: `core/originator_engine.py` → v36

### Status: READY — MEDIUM priority (bug fix value)

### What it does
Adds the caller-bug fix + new soccer Poisson model. The bug: v36 callers pass
`bet.line` (market spread) as `mean` to `run_trinity_simulation()`. This is circular —
it uses the market's view instead of a model-derived projection. The sandbox adds
`efficiency_gap_to_margin()` which converts efficiency_gap to a projected margin,
and `poisson_soccer()` / `PoissonResult` which replace the simpler `run_poisson_matrix()`.

### Import path change
NONE. Both sandbox and v36 have this at root level (`originator_engine.py`).

### New packages / deps
NONE. Pure stdlib math — no scipy, no numpy.

### What to ADD to v36's originator_engine.py
These functions/classes are IN the sandbox but NOT in v36:

```
efficiency_gap_to_margin(efficiency_gap, home_advantage_pts=0.0) -> float
    THE KEY BUG FIX. Converts efficiency_gap (0-20 scale) to projected margin.
    Gap=10 → margin=0. Gap=15 → margin=+5.0. Gap=5 → margin=-5.0.
    Callers should use this INSTEAD of passing bet.line as mean.

efficiency_gap_to_soccer_strength(efficiency_gap) -> tuple[float, float, float, float]
    Converts efficiency_gap to (home_attack, away_attack, home_defense, away_defense)
    for the Poisson soccer model. Gap=10 → all factors = 1.0 (neutral).

poisson_soccer(home_attack, away_attack, home_defense, away_defense, total_line,
               apply_home_advantage) -> PoissonResult
    Full Poisson matrix model for soccer. Returns PoissonResult dataclass.
    More complete than run_poisson_matrix(): includes over/under, expected goals,
    and proper home advantage boost (SOCCER_HOME_GOAL_BOOST = 0.20).

PoissonResult (dataclass)
    home_win, draw, away_win, over_probability, under_probability,
    expected_home_goals, expected_away_goals, expected_total, max_goals.

New constants:
    LEAGUE_AVG_TOTALS: dict[str, float]  (already inline in v36 — promote to module level)
    SOCCER_HOME_GOAL_BOOST: float = 0.20
    SOCCER_LEAGUE_AVG_GOALS_HOME: float = 1.54
    SOCCER_LEAGUE_AVG_GOALS_AWAY: float = 1.11
    EFFICIENCY_GAP_NEUTRAL: float = 10.0
    EFFICIENCY_GAP_SCALE: float = 1.0
```

### What to KEEP in v36 (not in sandbox — do NOT remove)
```
simulate_prop(season_avg, line, sigma, minutes_adj, matchup_factor, iterations)
    V36 has active callers. Sandbox dropped it. Keep it.

run_poisson_matrix(home_xg, away_xg, max_goals=9) -> tuple[float, float, float]
    V36 has callers. Sandbox replaced it with poisson_soccer(). Keep for backward compat.
    Add poisson_soccer() as the new enhanced version alongside it.
```

### Bug fix call site (THE ACTUAL FIX — this is the value)
V36 has a known bug: `run_trinity_simulation()` receives `bet.line` as `mean`.
After promotion, the caller must use `efficiency_gap_to_margin(efficiency_gap)` instead.

**Find the call site:** Search v36 codebase for `run_trinity_simulation(` to locate where
`bet.line` or similar is passed as `mean`. The correct fix:
```python
# BEFORE (buggy):
result = run_trinity_simulation(mean=bet.line, ...)

# AFTER (fixed):
from originator_engine import efficiency_gap_to_margin
projected_margin = efficiency_gap_to_margin(bet.sharp_breakdown.get("efficiency", 10.0))
result = run_trinity_simulation(mean=projected_margin, ...)
```

**Scope note:** v36's BetCandidate.simulation field is display-only. The bug doesn't
affect edge detection, Kelly sizing, or Sharp Score — only the simulation display.
Medium priority, not critical.

### Files to touch in v36
1. **EDIT** `originator_engine.py` — add new functions/classes listed above.
   Run `tests/test_originator_engine.py` to confirm no regressions.
2. **EDIT** the caller file where `run_trinity_simulation(mean=bet.line)` is called.
   Replace `bet.line` with `efficiency_gap_to_margin(...)`.
3. **ADD** `tests/test_originator_engine.py` — port ~40 tests from sandbox.
   All tests use `seed=42` for determinism. No external calls to mock.

### Test count delta
163 → 203 (+40 tests in `tests/test_originator_engine.py`)
Assumes the call site fix adds ~3 additional regression tests.

### Reviewer concern: PoissonResult integration
V36 `edge_calculator.py` uses soccer results for edge detection. The current pipeline
does NOT call `run_poisson_matrix()` for live edge calculation — it uses the consensus
fair_prob method (Session 24 soccer_consensus.py fix). The Poisson model is supplementary
(simulation display only). Confirm this before touching any edge detection path.

### Priority
**MEDIUM.** Bug fix is valuable. Simulation is display-only in v36 — not blocking.
Build after any in-season priority items.

---

## MODULE 3: `core/nhl_data.py` → v36

### Status: READY — MEDIUM-HIGH priority (NHL in season, Feb 2026)

### What it does
Real-time goalie starter detection via free `api-web.nhle.com` API.
Zero Odds API quota cost. Starter field populates ~T-60min before puck drop.
Module-level cache (`_goalie_cache`) keyed by Odds API `event_id`.

### Import path change
- Sandbox: `from core.nhl_data import ...`
- V36 target: `from data.nhl_data import ...`
  → Place at `data/nhl_data.py` (data provider tier — no math, no UI, live external calls,
    same architectural position as a kill_switch_feed for NHL data)

### New packages / deps
NONE. Uses `requests` — already in v36 `requirements.txt` (used by `odds_fetcher.py`).

### Files to touch in v36

1. **ADD** `data/nhl_data.py`
   - Copy sandbox `core/nhl_data.py` with import path change only:
     No content changes needed. Module is architecturally compliant (no math_engine imports,
     no odds_fetcher imports, no UI — pure data layer with session injection for tests).

2. **ADD** `nhl_kill_switch()` to `edge_calculator.py`
   - Port from sandbox `core/math_engine.py` (`nhl_kill_switch()` function).
   - Signature:
     ```python
     def nhl_kill_switch(
         backup_goalie: bool,
         b2b: bool = False,
         goalie_confirmed: bool = True,
     ) -> tuple[bool, str]:
     ```
   - Logic: KILL if backup_goalie=True. FLAG if b2b or not goalie_confirmed.
   - Place alongside other kill switch functions in edge_calculator.py.

3. **EDIT** `edge_calculator.py` → `parse_game_markets()`:
   - Add `nhl_goalie_status: Optional[dict] = None` parameter
   - When `sport == "NHL"` and `nhl_goalie_status` provided: determine per-candidate
     opponent goalie status and call `nhl_kill_switch()`
   - When `sport == "NHL"` and `nhl_goalie_status=None`: apply FLAG (goalie unconfirmed)
     to all NHL candidates as safe default
   - Import at top of file: `from data.nhl_data import get_cached_goalie_status`

4. **EDIT** `app.py` → `run_pipeline()` — NHL goalie poll (replaces scheduler pattern)
   V36 has no background APScheduler. The goalie poll must happen inline during pipeline:
   ```python
   # In the NHL section of run_pipeline(), after fetching raw_games:
   from data.nhl_data import get_starters_for_odds_game, cache_goalie_status
   for game in raw_nhl_games:
       commence_utc = parse datetime from game["commence_time"]
       result = get_starters_for_odds_game(
           away_team_name=game["away_team"],
           home_team_name=game["home_team"],
           game_start_utc=commence_utc
       )
       if result:
           cache_goalie_status(game["id"], result)
   ```
   Then pass `nhl_goalie_status` cache into `calculate_edges()` which passes to `parse_game_markets()`.

5. **ADD** `tests/test_nhl_data.py` — port sandbox's 34 tests
   - All external calls (`requests.get`) must be mocked — sandbox already uses session injection
   - Import path: `from data.nhl_data import ...`
   - Session injection pattern works as-is (no changes needed to test structure)

6. **ADD** tests for `nhl_kill_switch()` to `tests/test_validation.py` (~8 new tests):
   - backup_goalie=True → kill
   - b2b=True, backup_goalie=False → flag
   - goalie_confirmed=False → flag
   - all False → clean pass

### Test count delta
163 → 205 (+34 nhl_data tests + ~8 nhl_kill_switch tests)

### Architecture warning: parse_game_markets() signature change
`parse_game_markets()` already has existing callers in v36 and tests.
Adding `nhl_goalie_status` as an optional kwarg with `= None` default is backwards compatible.
All existing callers continue to work unchanged (they just get the safe-default FLAG behavior).
Verify: `grep -rn "parse_game_markets(" .` before editing to count all call sites.

### v36 compatibility check
- `requests` is already in requirements.txt ✅
- `data/__init__.py` already exists (Session 14) ✅ — `data.nhl_data` will import cleanly
- No Supabase dependency needed — goalie data is in-memory only (session-scoped cache) ✅

### Priority
**MEDIUM-HIGH.** NHL is in-season (February 2026). Goalie status is the primary kill signal
for NHL — collar-only protection (current v36 state) is weaker than it should be.

---

## CROSS-MODULE NOTES

### Collision risks
- No alias collision risk — `nhl_data.py` introduces `_TEAM_NAME_MAP` keyed to NHL full names,
  which don't overlap with efficiency_feed aliases.
- `weather_feed.NFL_STADIUMS` uses full NFL team names, same as `_NFL_WIND_FORECAST` keys —
  identical key space, no collision.

### Test isolation requirements
- `data/nhl_data.py` has `_goalie_cache` module-level state. Tests must call
  `clear_goalie_cache()` in `setup_method()` — identical to the `_OPEN_PRICE_CACHE`
  pattern already in test_odds_fetcher.py.
- `data/weather_feed.py` has `_wind_cache` module-level state. Tests must call
  `clear_wind_cache()` in `setup_method()`.

### Recommended build order
1. `nhl_data.py` — in-season, highest immediate value, clean promotion path
2. `originator_engine.py` — fix known bug, pure code addition, no external deps
3. `weather_feed.py` — deferred to Aug 2026 (NFL window)

---

## STATUS TRACKER

| Module | Spec written | Sandbox built | V37 audited | V36 promoted |
|--------|-------------|---------------|-------------|--------------|
| weather_feed | ✅ 2026-02-24 | ⏳ pending | — | DEFERRED Aug 2026 |
| originator_engine | ✅ 2026-02-24 | ⏳ pending | — | — |
| nhl_data | ✅ 2026-02-24 | ⏳ pending | — | — |
