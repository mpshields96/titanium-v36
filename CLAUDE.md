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
grep -n "html.escape\|_html.escape" pages/*.py   # XSS audit — verify escape coverage after any sandbox UI page change
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

## API Quota — DO NOT BURN (non-negotiable)
- **DAILY HARD CAP: 1,000 credits/day — permanent user rule, no exceptions, ever. Includes testing and experimentation.**
- Quota is a hard finite resource. 10% → 45% burned in a single day is unacceptable.
- **R&D live API calls require explicit user approval before every run.** No exceptions.
- Default for ALL R&D probe/validation scripts: use saved fixture JSON, not live endpoints.
- Before running any script that calls `fetch_game_lines()` or any `_get()`: state the call count and ask the user to confirm.
- v36 production is fine (1 call/sport on EXECUTE SCAN only). R&D is the risk surface.
- Never run multi-sport probes, validation loops, or iterative probes without explicit per-run approval.
- **Scheduler is NOT safe to leave running** — it polls every 5 min × 11 sports = ~26 credits/cycle × 288 cycles/day = 7,488 credits/day if left unattended. Never start the scheduler without daily cap enforcement in place.

## Session Workflow
- **SESSION START**: Read `~/ClaudeCode/agentic-rd-sandbox/V37_INBOX.md` immediately after CLAUDE.md. If there's a PENDING task from the sandbox builder, complete it before other work. This is how the two-AI system coordinates without requiring the user to relay prompts. (Inbox lives in the sandbox repo — sandbox writes it, you read it. Never write to that path.)
- State which file you're working on and what the last working state was
- One function at a time. Write a test before building the next function.
- If code breaks: describe behavior ("returns empty list"), not "fix it"
- Never push to GitHub without checking the deployment checklist
- Module-level caches (e.g. `_OPEN_PRICE_CACHE`) need `setup_method` teardown in tests — call clear function before each test or tests bleed state
- `QuotaTracker` test isolation: module-level `quota` singleton bleeds state. Any test class exercising `fetch_game_lines()` or `fetch_batch_odds()` needs `setup_method` resetting `quota.remaining=18000`, `quota.session_used=0`, `quota.daily_log._data["used_today"]=0`. Without this, BILLING_RESERVE guard fires and all `_get()` calls return `[]`.
- Supabase mock `.not_` chain: `mock_table.not_` is a property (not callable), so `mock_table.not_.return_value = mock_table` does NOT work. Use `mock_table.not_ = mock_table` so `.not_.is_(...)` resolves back through the configured mock and `.execute()` returns correct test data
- Pass `raw_games` into `calculate_edges(sport, raw_games=raw_games)` to avoid double API call — it skips internal fetch when provided
- Never import `edge_calculator` from `odds_fetcher.py` — circular import (`edge_calculator` already imports `odds_fetcher`)
- `data/price_history_store.py`: `from odds_fetcher import _extract_open_prices` must stay deferred (inside function body) — same circular import reason
- Before removing a function parameter, grep all call sites first: `grep -rn "function_name(" .` — easy to miss cross-file callers (e.g. `sharp_to_size` had callers in `bet_ranker.py`)
- Edit tool `old_string` failures: if a file was already partially edited this session, grep for current text before editing — the previously-matched string may no longer exist exactly
- **V37_INBOX ✅ DONE = sandbox committed** — task has a commit hash, already pushed. Validate by grepping for the artifact + running pytest. No need to re-implement or wait.
- **Reviewer flag-clearing rule:** After writing APPROVED audit for a sandbox fix, also explicitly update REVIEW_LOG.md ACTIVE FLAGS — change 🔴/🟡 to ✅ CLEARED. The audit block alone does NOT clear the flag.
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
| 21 | ✅ Done | UI 2 Odds Comparison page, data/odds_comparator.py promoted from R&D, app.py cleanup (dead imports, del→pop fix, try/finally on pipeline) |
| 22 | ✅ Done | UI 5 CLV column in Bet History, data/clv_store.py (NEW), clv_history Supabase table, record_clv_open() wired at Track Bet, 19 new tests — 135/135 tests |
| 23 | ✅ Done | CLAUDE.md .not_ mock pattern, MASTER_ROADMAP session log, all MD files refreshed, PROJECT_INDEX.md updated |
| 24 | ✅ Done | GAP 4 soccer 3-way fix: data/soccer_consensus.py promoted, edge_calculator.py moneyline branched on _is_soccer. EXP 5: data/parlay_builder.py + page_parlay_builder() + 🔗 nav. 28 new tests — 163/163 |
| 25 | ✅ Done | Architecture: agentic sandbox (~/ClaudeCode/agentic-rd-sandbox/) promoted to primary builder. v36 chat transitions to Reviewer/Auditor role. R&D chat RETIRED. SYNC.md INBOX updated. API quota rule locked. No code changes. |
| V37 R2 | ✅ Done | XSS fix (app.py + bet_card_renderer.py _html.escape), DailyCreditLog + enforcing QuotaTracker in odds_fetcher.py (DAILY_CREDIT_CAP=1000), 22 new tests — 185/185. Quota incident root cause documented. Inactivity auto-stop spec written to REVIEW_LOG.md + V37_INBOX.md. |
| V37 R3 | ✅ Done | _touch_activity() in app.py (inactivity tracking, 5 new tests), test_app_utils.py (NEW), data/last_activity.json gitignored — 190/190 tests. Session 25 cont. audited APPROVED. originator_engine N/A (not wired). All V37_INBOX tasks resolved. |
| V37 R4 | ✅ Done | data/nhl_data.py (NEW, 35 tests), nhl_kill_switch() in edge_calculator.py, BetCandidate.calibration field, rank_bets() calibration_threshold param, SPECULATIVE tier in sharp_to_size() + bet_card_renderer.py, quota guards 1000→100/30/80, calibration→speculative banner in app.py. Session 27 audited APPROVED — 251/251 tests. |
| V37 R5 | ✅ Done | Totals dedup cross-line guard: _deduplicate_markets() key drops abs(line) for totals markets — Over 7.0 + Under 6.5 same game now share one dedup bucket. +6 TestTotalsDedupCrossLine. Session 29 audited APPROVED (Layer 1 modal line pinning + RLM direction fix + dead code deletion, sandbox 1079/1079) — 257/257 tests. |
| V37 R7 | ✅ Done | Session 30-B PRECONDITION blocks validated (all 5 present in math_engine.py), v36 stale docstrings fixed (QuotaTracker/is_daily_cap_hit/is_session_hard_stop — constant names not hardcoded values), REVIEW_LOG.md active flags cleared — 257/257 tests. |

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
- **`st.html()` XSS escaping:** Wrap all user/API strings in `_html.escape()` before f-string interpolation. Use `import html as _html` (alias required — `html` is a local variable name in app.py and bet_card_renderer.py). Streamlit 1.54+ `st.html()` runs in an allow-scripts iframe — stored XSS is live, not theoretical.
- **Pure widget pages skip `_html.escape()`:** Pages using only `st.metric`, `st.line_chart`, `st.dataframe` don't inject into HTML templates — no escape needed. Audit question: does this file call `st.html()` with API/user string interpolation?
- **eff_data multi-sport:** call `eff_data.update(build_efficiency_data(raw_games))` unconditionally per sport — never gate inside `if sport == "X"` or efficiency data silently won't reach rank_bets() for other sports.
- **Equity curve charts:** `st.line_chart(df, color="#14B8A6", height=180)` — pass pd.DataFrame with named index. Works on Streamlit Cloud, no extra deps. Used in `page_pnl_tracker()`.
- **P&L session cache:** `"pnl_data"` key is independent of `"bet_history_data"` — bust with `st.session_state.pop("pnl_data", None)` + `st.rerun()` after any outcome write.
- **CLV open_price:** Always `bet.price` (NOT `get_open_price()`). `get_open_price` uses team-name keys; `clv_history` table uses `(event_id, target, market_type)` unique key. No collision risk with `bet.price`.
- **Odds Comparison data source:** `st.session_state["raw_games"]` — zero new API calls. Page is inert until pipeline has run at least once in the session.
- **Supabase `.not_` mock pattern:** `.not_` is a property (not callable). `mock_table.not_.return_value = mock_table` DOES NOT WORK. Use `mock_table.not_ = mock_table` so `.not_.is_(...)` routes through the configured mock and `.execute()` returns correct test data.
- **MEMORY.md 200-line limit:** Detailed session learnings live in `~/.claude/projects/.../memory/session-learnings.md`. MEMORY.md stays as a concise index under 150 lines. Always link, don't duplicate.
- **Soccer 3-way vig:** `_is_soccer` check in `parse_game_markets()` uses the uppercase routing key set (`EPL`, `MLS`, etc.) — NOT `sport_key.startswith("soccer_")` (that's the API format, not available inside parse_game_markets). Draw outcome name in Odds API is exactly `"Draw"` (confirmed in soccer_3way_probe.py line 154).
- **Parlay builder call site:** `build_parlay_combos()` takes `list[dict]`, not `list[BetCandidate]`. Always convert: `[vars(b) for b in ranked_bets]`. Do NOT change parlay_builder.py to accept dataclasses — one file = one job, no v36-specific imports in data/ modules.
- **Parlay Builder data source:** `st.session_state["results"]` (the ranked BetCandidate list). Page is inert until pipeline runs. Same pattern as Odds Comparison using `st.session_state["raw_games"]`.
- **Totals dedup key excludes line:** `_deduplicate_markets()` uses `(event_id, market_type)` for totals — `abs(line)` intentionally dropped (V37 R5). Books hang different lines (6.5 vs 7.0) for same game; including the line allows Over 7.0 AND Under 6.5 to survive dedup simultaneously — a mathematical impossibility. Highest-edge side wins regardless of line. Do NOT re-add the line to totals keys.

## If Starting a New Chat Session
1. Paste the contents of `SESSION_STATE.md` into the chat (this is the resume document)
2. Say: "Resume Session [N]. Read CLAUDE.md and SESSION_STATE.md. Run: pytest tests/ -v and confirm all tests pass before we start."
3. Wait for test confirmation, then state what you want to build
4. For fast orientation: read `PROJECT_INDEX.md` first — covers all modules, functions, Sharp Score formula, kill switches. 94% token reduction vs reading source files.
5. For backlog and roadmap: read `docs/MASTER_ROADMAP.md` — authoritative to-do list covering math gaps, structural ceiling fixes, R&D backlog, and UI work. In-repo file, readable by R&D chat too.

## Chat Roles & File Access (non-negotiable)
Two Claude Code chats exist for this project. File permissions are STRICTLY enforced:
**R&D chat (titanium-experimental) RETIRED as of Session 25. Replaced by agentic sandbox.**

| Chat | titanium-v36/ | agentic-rd-sandbox/ |
|------|--------------|---------------------|
| **v36 reviewer (this chat)** | Full read + write | READ ONLY — never writes |
| **Agentic sandbox** | READ ONLY — never writes | Full read + write |

Rules:
- **v36 reviewer is the promotion gate.** Nothing lands in v36 unless explicitly written by this chat.
- **Agentic sandbox CANNOT modify any v36 files.** Not CLAUDE.md, not SESSION_STATE.md, not any .py files.
- When promoting sandbox code to v36: reviewer reads sandbox files, then writes v36 files. Never the reverse.
- **Coordination files all live in the sandbox:** V37_INBOX.md, REVIEW_LOG.md, SESSION_LOG.md.
  - V37_INBOX.md: sandbox writes pending tasks → reviewer reads and marks DONE
  - REVIEW_LOG.md: sandbox writes session summaries → reviewer appends audit blocks
  - Both chats read these files at session start. Reviewer ONLY writes audit blocks / flag notes here.
- **`titanium-experimental/` is ARCHIVED** — SYNC.md, HANDOFF.md are no longer active. Ignore.
- SESSION_STATE.md in `titanium-v36/` is reviewer-only. Sandbox reads it for context only.
- **REVIEWER_PROMPT.md** in `titanium-v36/` is the session startup document for new reviewer chats.
  Update Section 2 at every session end and commit.

## Deployment Checklist
- [ ] No API keys in code
- [ ] `requirements.txt` updated if new packages added
- [ ] App runs locally without errors
- [ ] All tests passing: pytest tests/ -v
- [ ] git commit before starting any new session
