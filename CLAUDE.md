# TITANIUM V36.1 — Project Rules for Claude Code

## Architecture (One File = One Job)
| File | Does | Does NOT |
|------|------|----------|
| `app.py` | Streamlit UI, button handling | Business logic, API calls |
| `odds_fetcher.py` | Odds API calls only | Math, UI |
| `edge_calculator.py` | Betting math only | API calls, UI |
| `bet_ranker.py` | Dedup + Sharp Score rank + top-10 | Math, API calls |
| `ncaab_parser.py` | NCAAB collar filter + best-price extraction | Edge calc, UI |
| `originator_engine.py` | Monte Carlo — DO NOT TOUCH unless asked | — |
| `data/team_stats_bunker.py` | Static fallback stats | Live data |

## Commands
```bash
python3 -m pytest tests/ -v          # Run all tests (must pass before any session)
python3 ncaab_parser.py              # Live NCAAB pipeline test (1 API call)
streamlit run app.py                 # Launch UI locally (Session 5+)
grep -n "def calculate_edges" edge_calculator.py  # One def only — dead stub removed Session 13 cleanup
```

## Non-Negotiable Betting Rules
1. **Odds collar**: Only -180 to +150 (American). Reject everything else.
2. **Minimum edge**: ≥ 3.5% between Titanium True Price and market. No exceptions.
3. **No duplicate markets**: Never output both sides of the same bet.
4. **Kelly sizing**: 0.25x fractional. Hard caps: >60% winprob → 2.0u max, >54% → 1.0u max, else → 0.5u max.
5. **Kill switches** (abort immediately):
   - NBA: rest disadvantage AND spread < -4 → ABORT spread
   - NFL: wind > 15mph AND total > 42 → FORCE UNDER or PASS
   - NCAAB: 3P reliance > 40% AND away game → FADE
   - Soccer: market drift > 10% against position → ABORT

## Output Format (Definition of Done)
Table with max 10 rows, **sorted by Sharp Score descending** (NOT Edge% — changed Session 4):
`Time | Matchup | Type | Target | Line | Price | Edge% | Kelly_Size | Signal`

Sharp Score tiers: NUCLEAR (≥90) = 2.0u | STANDARD (≥80) = 1.0u | LEAN (else) = 0.5u
Threshold: **45 pts** (raised 40→45 Session 13, ~7.8% real edge required). Raise to 50–55 after RLM fully activates.

## Model Philosophy (non-negotiable)
**Math > Narrative. Always.**
- Nemesis is display-only annotation. It NEVER removes bets or adjusts scores.
- Kill switches operate on structural mathematical inputs only (rest days, wind, 3PT rate, drift).
- Situational Sharp Score inputs must have a live computable source to be non-zero.
  - rest_edge: ✅ live (schedule-derived rest days, NBA only)
  - injury_leverage: ❌ not wired — always 0
  - motivation: ❌ not wired — always 0
  - matchup_score: ❌ not wired — always 0
- Do NOT add narrative-driven inputs (home crowd, "hostile environment", "young roster") to any scoring component. These are rat poison.

## API Notes
- Key: `os.environ.get("ODDS_API_KEY")` — never hardcode
- Regions: `us`, Format: `american`, Book: DraftKings first
- All sports: `fetch_batch_odds()` with `h2h,spreads,totals` only
- Player props (player_points, player_pass_yds etc.) NOT supported on current API tier — confirmed 422 Feb 2026
- NHL sparse coverage (h2h only, few books) is normal for games >3 days out; spreads/totals open closer to game day

## Session Workflow
- State which file you're working on and what the last working state was
- One function at a time. Write a test before building the next function.
- If code breaks: describe behavior ("returns empty list"), not "fix it"
- Never push to GitHub without checking the deployment checklist
- Module-level caches (e.g. `_OPEN_PRICE_CACHE`) need `setup_method` teardown in tests — call clear function before each test or tests bleed state
- Pass `raw_games` into `calculate_edges(sport, raw_games=raw_games)` to avoid double API call — it skips internal fetch when provided
- Never import `edge_calculator` from `odds_fetcher.py` — circular import (`edge_calculator` already imports `odds_fetcher`)
- Before removing a function parameter, grep all call sites first: `grep -rn "function_name(" .` — easy to miss cross-file callers (e.g. `sharp_to_size` had callers in `bet_ranker.py`)
- End every session: `/sc:save` → `/claude-md-management:revise-claude-md` → `git commit`
- End responses with a "Loading screen tip" — one relevant `/sc:` command or tool reminder for the user

## Session Progress Log
| Session | Status | What was built |
|---------|--------|----------------|
| 1 | ✅ Done | File structure, CLAUDE.md, requirements.txt, all scaffolds |
| 2 | ✅ Done | odds_fetcher.py fetch_batch_odds() — live-tested, 20/20 tests passing |
| 3 | ✅ Done | odds_fetcher upgrade, originator_engine (Trinity MC), ncaab_parser, consensus edge detection |
| 4 | ✅ Done | bet_ranker.py, Sharp Score, run_nemesis, BetCandidate updated, full pipeline live-tested |
| 5–10 | ✅ Done | efficiency_feed, kill switches, UI, multi-page scaffold, NCAAB expansion, Streamlit Cloud |
| 11 | ✅ Done | compute_rest_days_from_schedule(), _apply_nba_kill() live rest, st.navigation() scaffold |
| 12 | ✅ Done | Nemesis demoted to display-only, rest_edge wired to Sharp Score (NBA), NCAAB 3P to 80 teams, tempo sourced from efficiency_feed |
| 13 | ✅ Done | SHARP_THRESHOLD 40→45, compute_rlm() (passive RLM, 3% implied prob, zero API cost), wired into run_pipeline() — 85/85 tests |

## R&D → V36 Promotion Rules
- R&D sandbox: /Users/matthewshields/Projects/titanium-experimental
- **HANDOFF.md at that path is the authoritative spec** — read it directly, don't rely solely on user's chat summary
- Only promote code that has been live-tested in R&D
- Known R&D bugs — DO NOT promote until fixed:
  - run_trinity_simulation receives bet.line as mean instead of projected margin (unfixed)
  - RLM Sharp Score component: passive RLM now wired (Session 13). Activates when open-price cache
    has data AND a 3% implied prob shift is detected. Will score 0 on first run (cold cache).
- Fixed in R&D, ready for promotion review:
  - Props edge bug: fixed (consensus fair_prob across books, same pattern as game lines)
- Edge detection method (PROVEN): consensus vig-free mean across all books = model.
  Best single-book price = betting price. Edge = consensus_prob - implied(best_price)

## Key Architecture Decisions (do not reverse)
- Multi-book consensus is the edge signal — NOT single-book comparison
- louisiana_mode is a flag in parse_prop_markets, not a separate file
- Soccer bulk markets: h2h,totals only (btts/h2h_3_way cause 422 on bulk endpoint)
- All sports use fetch_batch_odds() — no per-event prop calls (API tier limitation)
- `_KILL_ROUTER` has no "nba" entry by design — NBA needs `schedule_rest` kwarg, handled by explicit branch in `calculate_edges()` before the router is hit. Do not add it back.

## If Starting a New Chat Session
1. Paste the contents of `SESSION_STATE.md` into the chat (this is the resume document)
2. Say: "Resume Session [N]. Read CLAUDE.md and SESSION_STATE.md. Run: pytest tests/ -v and confirm all tests pass before we start."
3. Wait for test confirmation, then state what you want to build
4. For fast orientation: read `PROJECT_INDEX.md` first — covers all modules, functions, Sharp Score formula, kill switches. 94% token reduction vs reading source files.

## Deployment Checklist
- [ ] No API keys in code
- [ ] `requirements.txt` updated if new packages added
- [ ] App runs locally without errors
- [ ] All tests passing: pytest tests/ -v
- [ ] git commit before starting any new session
