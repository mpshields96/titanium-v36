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
  - injury_leverage: ❌ stubs exist (kill_switch_feed.py) — always 0.0, data_live=False. ESPN B2 (R&D Session 16): usage% scoring resolved, remaining gate = 2-week stability log (~2026-03-04). NCAAB: no ESPN endpoint — permanently stub.
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
- `data/price_history_store.py`: `from odds_fetcher import _extract_open_prices` must stay deferred (inside function body) — same circular import reason
- Before removing a function parameter, grep all call sites first: `grep -rn "function_name(" .` — easy to miss cross-file callers (e.g. `sharp_to_size` had callers in `bet_ranker.py`)
- Edit tool `old_string` failures: if a file was already partially edited this session, grep for current text before editing — the previously-matched string may no longer exist exactly
- End every session: `/sc:save` → `/claude-md-management:revise-claude-md` → `git commit`
- **MANDATORY — Loading screen tip:** End EVERY response (not just session-end) with a one-line tip in the format `Loading screen tip: ...` — one relevant `/sc:` command or tool reminder. This is a non-negotiable UX behavior. New sessions must not wait to be reminded of this rule.

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
| 14 | ✅ Done | bet_card_renderer.py promoted (R&D), render_bet_slate() wired, .streamlit/config.toml, data/__init__.py fix, UI polish — 85/85 tests |
| 15 | ✅ Done | Feature backlog saved to SESSION_STATE.md, /sc:estimate B+C+F, session transition prep |
| 16 | ✅ Done | Injury leverage stubs (kill_switch_feed.py), std_dev field on BetCandidate, BOOKS badge on card — 93/93 tests |
| 17 | ✅ Done | NHL efficiency data (32 teams, GF60-GA60 × 10 AdjEM proxy) — 95/95 tests |
| 17-post | ✅ Done | eff_data all-sports fix, st.html() card rendering fix, header padding fix, Supabase MCP setup |
| 18 | ✅ Done | page_bet_history() full impl (P&L strip, Pending, History Log + MARK RESULT), + TRACK BET on Live Analysis cards, render_slate_header/footer helpers — 95/95 tests |
| 19 | ✅ Done | efficiency_feed.py MLB/MLS/NFL promotion (234 teams total), Hawks alias collision fix, 11 new tests — 106/106 tests |
| 20 | ✅ Done | docs/MASTER_ROADMAP.md created, page_pnl_tracker() fully built, RLM 2.0: data/price_history_store.py + Supabase price_history table + _extract_open_prices() refactor — 116/116 tests |

## R&D → V36 Promotion Rules
- R&D sandbox: /Users/matthewshields/Projects/titanium-experimental
- **HANDOFF.md at that path is the authoritative spec** — read it directly, don't rely solely on user's chat summary
- Only promote code that has been live-tested in R&D
- **Import path diff when promoting:** R&D uses `from core.edge_calculator import` / `from core.odds_fetcher import` — v36 is root-level, use `from edge_calculator import` / `from odds_fetcher import`. Also strip `sys.path.insert(0, ...)` blocks.
- **R&D promotion schema check:** R&D POC dicts may use different key formats than v36 (e.g. R&D `price_history_store.py` used `{TeamName: price}`; v36 uses `{"home": price, "away": price}`). Always read BOTH files before promoting — never assume schemas match.
- **efficiency_feed.py new-sport promotion checklist:**
  1. Run `/sc:analyze data/efficiency_feed.py` BEFORE starting — catch collision risks early
  2. For every bare alias in the R&D _ALIASES block: grep v36 _ALIASES for the same key. If it exists pointing to a different sport, use a qualified form instead (e.g. "Blackhawks" not "Hawks", "NY Jets" not "Jets")
  3. After promotion: add `test_X_alias_resolves_to_Y_not_Z()` tests for every collision-risk alias
  4. Update the collision table in the file docstring
- **SHARP_THRESHOLD raise gate (45→50):** Do NOT raise until `RLM live sessions observed` counter in SESSION_STATE.md CURRENT STATE reaches ≥5. Increment manually each session RLM fires on live data.
- **`std_dev` in `BetCandidate`:** ✅ Done Session 16. `std_dev: float = 0.0` field on BetCandidate. Passed from `_consensus_fair_prob()` at 3 call sites. BOOKS: TIGHT/MODERATE/WIDE badge in `bet_card_renderer.py`. Display-only, zero score impact. F2 (Sharp Score component) **permanently rejected** — R&D validated r=+0.020, no linear relationship. High std_dev = one outlier book = source of edge. Do not add to scoring.
- Known R&D bugs — DO NOT promote until fixed:
  - run_trinity_simulation receives bet.line as mean instead of projected margin (unfixed in v36;
    R&D Session 17 fixed call site in `core/titanium.py` — same pattern applies to v36 when simulation is used for sizing)
  - RLM Sharp Score component: passive RLM now wired (Session 13). Activates when open-price cache
    has data AND a 3% implied prob shift is detected. Will score 0 on first run (cold cache).
    RLM 2.0: `data/price_history_store.py` live (Session 20) — multi-day open prices now persisted in Supabase.
    True first-ever-seen price injected into cache on session start. RLM now fires on overnight moves.
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
- `data/__init__.py` must stay — Streamlit Cloud requires it for subpackage imports
- `bet_card_renderer.py` uses inline styles only — Streamlit strips `<style>` tags from `st.markdown()` HTML
- `st.Page(icon=...)` requires real emoji or Material shortcodes — Unicode geometric chars (◈ ◇) crash the app
- **Streamlit 1.54+:** `st.markdown(unsafe_allow_html=True)` sandboxes large HTML into a `<code>` block. Use `st.html()` for full HTML documents/slates. `st.markdown` is safe only for small inline fragments.
- **eff_data multi-sport:** call `eff_data.update(build_efficiency_data(raw_games))` unconditionally per sport — never gate inside `if sport == "X"` or efficiency data silently won't reach rank_bets() for other sports.
- **Equity curve charts:** `st.line_chart(df, color="#14B8A6", height=180)` — pass pd.DataFrame with named index. Works on Streamlit Cloud, no extra deps. Used in `page_pnl_tracker()`.
- **P&L session cache:** `"pnl_data"` key is independent of `"bet_history_data"` — bust with `st.session_state.pop("pnl_data", None)` + `st.rerun()` after any outcome write.

## If Starting a New Chat Session
1. Paste the contents of `SESSION_STATE.md` into the chat (this is the resume document)
2. Say: "Resume Session [N]. Read CLAUDE.md and SESSION_STATE.md. Run: pytest tests/ -v and confirm all tests pass before we start."
3. Wait for test confirmation, then state what you want to build
4. For fast orientation: read `PROJECT_INDEX.md` first — covers all modules, functions, Sharp Score formula, kill switches. 94% token reduction vs reading source files.
5. For backlog and roadmap: read `docs/MASTER_ROADMAP.md` — authoritative to-do list covering math gaps, structural ceiling fixes, R&D backlog, and UI work. In-repo file, readable by R&D chat too.

## Chat Roles & File Access (non-negotiable)
Two Claude Code chats exist for this project. File permissions are STRICTLY enforced:

| Chat | titanium-v36/ | titanium-experimental/ |
|------|--------------|------------------------|
| **v36 chat (this chat)** | Full read + write | Full read + write |
| **R&D chat** | READ ONLY — never modifies | Full read + write |

Rules:
- **v36 chat is the promotion gate.** Nothing lands in v36 unless explicitly written here.
- **R&D chat CANNOT modify any v36 files.** Not CLAUDE.md, not SESSION_STATE.md, not any .py files.
- When promoting R&D code to v36: v36 chat reads R&D files, then writes v36 files. Never the reverse.
- HANDOFF.md in `titanium-experimental/` is the communication channel. R&D writes it; v36 reads it.
- SESSION_STATE.md in `titanium-v36/` is v36-only. R&D reads it for context only.

## Deployment Checklist
- [ ] No API keys in code
- [ ] `requirements.txt` updated if new packages added
- [ ] App runs locally without errors
- [ ] All tests passing: pytest tests/ -v
- [ ] git commit before starting any new session
