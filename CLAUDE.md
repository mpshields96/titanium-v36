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
Threshold: 40 pts pre-nemesis (temporary — raise to 75 when KenPom/Barttorvik wired in Session 5+)

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

## Session Progress Log
| Session | Status | What was built |
|---------|--------|----------------|
| 1 | ✅ Done | File structure, CLAUDE.md, requirements.txt, all scaffolds |
| 2 | ✅ Done | odds_fetcher.py fetch_batch_odds() — live-tested, 20/20 tests passing |
| 3 | ✅ Done | odds_fetcher upgrade, originator_engine (Trinity MC), ncaab_parser, consensus edge detection |
| 4 | ✅ Done | bet_ranker.py, Sharp Score, run_nemesis, BetCandidate updated, full pipeline live-tested |
| 5 | 🔲 Next | efficiency_feed.py (KenPom mock), Streamlit UI wired, kill switches, Streamlit Cloud deploy |

## R&D → V36 Promotion Rules
- R&D sandbox: /Users/matthewshields/Projects/titanium-experimental
- Only promote code that has been live-tested in R&D
- Known R&D bugs — DO NOT promote until fixed:
  - run_trinity_simulation receives bet.line as mean instead of projected margin (unfixed)
  - RLM component of Sharp Score always returns 0 (unfixed — no line movement data source)
- Fixed in R&D, ready for promotion review:
  - Props edge bug: fixed (consensus fair_prob across books, same pattern as game lines)
- Edge detection method (PROVEN): consensus vig-free mean across all books = model.
  Best single-book price = betting price. Edge = consensus_prob - implied(best_price)

## Key Architecture Decisions (do not reverse)
- Multi-book consensus is the edge signal — NOT single-book comparison
- louisiana_mode is a flag in parse_prop_markets, not a separate file
- Soccer bulk markets: h2h,totals only (btts/h2h_3_way cause 422 on bulk endpoint)
- All sports use fetch_batch_odds() — no per-event prop calls (API tier limitation)

## If Starting a New Chat Session
1. Paste the contents of `SESSION_STATE.md` into the chat (this is the resume document)
2. Say: "Resume Session [N]. Read CLAUDE.md and SESSION_STATE.md. Run: pytest tests/ -v and confirm all tests pass before we start."
3. Wait for test confirmation, then state what you want to build

## Deployment Checklist
- [ ] No API keys in code
- [ ] `requirements.txt` updated if new packages added
- [ ] App runs locally without errors
- [ ] All tests passing: pytest tests/ -v
- [ ] git commit before starting any new session
