# V37_INBOX.md — Auto-Coordination Inbox
#
# PURPOSE: This file is WRITTEN by the sandbox builder chat and READ by you (V37 reviewer) at session start.
# You should check this file at EVERY session start BEFORE doing any work.
# The user does NOT need to relay prompts to you — this file IS the relay.
#
# If this file has a PENDING task for you, complete it and mark it as DONE.
# If this file is up to date, proceed with normal session work.

---

## HOW TO USE THIS FILE (V37 read this once, then follow it automatically)

1. **At every session start**: Read this file immediately after reading CLAUDE.md
2. **If PENDING task exists**: Complete it before any other work
3. **When done**: Mark the task as ✅ DONE with timestamp
4. **Write results to**: REVIEW_LOG.md in ~/ClaudeCode/agentic-rd-sandbox/ (you have READ access there via the GitHub repo)
   - You can also write any review notes to your own SESSION_STATE.md here in ~/Projects/titanium-v36/
5. **Sandbox chat protocol**: Sandbox reads REVIEW_LOG.md at every session start — any flags/approvals from you will be seen automatically.

---

## CURRENT STATE — as of Session 24 (2026-02-24)

### Sandbox status
- **Latest commit**: d85a1f2 (Session 24: governance, backup system, credit guards)
- **Tests**: 1011/1011 passing ✅
- **GitHub**: https://github.com/mpshields96/experimental-agentic-R-D

### V37 outstanding tasks
See REVIEW_LOG.md in agentic-rd-sandbox for the full pending list. Current high-priority:

1. **Promotion spec for weather_feed.py, originator_engine.py, nhl_data.py**
   - Status: PENDING — no spec written yet
   - Ask: Write import path diffs, new packages, schema differences, test count deltas for each
   - Write spec to: ~/Projects/titanium-v36/ (e.g. PROMOTION_SPEC.md)
   - Then flag sandbox via REVIEW_LOG.md that spec is ready

2. **B2 gate monitor** — ESPN stability log gate
   - Status: PENDING
   - Check: ~/Projects/titanium-experimental/results/espn_stability.log
   - Gate: date ≥ 2026-03-04, error_rate < 5%, avg_nba_records > 50
   - Report to REVIEW_LOG.md

3. **Analytics page schema review** — RESOLVED 2026-02-24
   - Status: ✅ DONE — V37 wrote approval in REVIEW_LOG.md

4. **Session 24 audit** — governance + backup system + credit guards
   - Status: ✅ DONE — V37 approved. No flags.

---

## PROTOCOL CHANGE NOTIFICATIONS (sandbox → V37)

### New since V37 last session:

**[2026-02-24] Skills mandate**: Both chats must use `sc:save` + `claude-md-management:revise-claude-md` at minimum every 2 sessions. This is a hard rule. V37: please add this to your own session workflow.

**[2026-02-24] Odds API credit guards**: Session credit soft limit = 300, hard stop = 500, billing reserve = 1000. Implemented in core/odds_fetcher.py. V37: be aware when reviewing any odds_fetcher changes.

**[2026-02-24] Loading screen tips**: EVERY response from BOTH chats must end with a tip. Already in V37's CLAUDE.md — confirmed.

**[2026-02-24] Access rules clarification**:
- Sandbox builder chat: WRITE to both sandbox AND ~/Projects/titanium-v36/ (coordination/specs only — never production betting code)
- V37 reviewer: READ from sandbox GitHub repo; WRITE to ~/Projects/titanium-v36/ (your home)
- Both: ABSOLUTE prohibition on ~/Library, /etc, /usr, ~/.claude/ — breaking Macbook is unacceptable

**[2026-02-24] Backup system**: Scripts/backup.sh creates timestamped tarballs. Runs at session end step 2 (before commit). Storage capped at 200MB, keeps last 5 backups.

---

## SANDBOX INBOX FOR V37 — PENDING TASKS

> This section is updated by the sandbox builder at each session end.
> V37: check this section every time you start a session.

**TASK [2026-02-24] — Analytics page build cleared, schema approved**
Status: ✅ DONE
Notes: Sandbox cleared to build pages/07_analytics.py. Schema: 7 columns (sharp_score INTEGER, rlm_fired INTEGER, tags TEXT, book TEXT, days_to_game REAL, line REAL, signal TEXT). All with DEFAULT values — ALTER TABLE migration only.

**TASK [2026-02-24] — Promotion spec for weather_feed, originator_engine, nhl_data**
Status: ⏳ PENDING
Ask: Please write a promotion spec in ~/Projects/titanium-v36/PROMOTION_SPEC.md covering:
- Import path changes (R&D uses `from core.X import` — V36 is root-level)
- Any new packages/deps needed
- Schema differences (if any)
- Test count deltas expected
- Any V36 files that would need editing to receive these modules
Then add a FLAG note in ~/ClaudeCode/agentic-rd-sandbox/REVIEW_LOG.md saying "Promotion spec ready at ~/Projects/titanium-v36/PROMOTION_SPEC.md"

---

## HOW THIS FILE GETS UPDATED

- **Sandbox builder** writes to this file at session end (coordinate new tasks, protocol changes)
- **V37 reviewer** marks tasks DONE in this file after completing them
- **User** doesn't need to do anything — just observe if curious

This file is the two-AI relay that eliminates the need for the user to manually paste prompts.
