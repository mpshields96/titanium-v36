"""
app.py — TITANIUM V36.1
========================
Streamlit UI ONLY. No business logic lives here.

Responsibilities:
- Render sport selector (toggle-style chip grid)
- Render EXECUTE button
- Call calculate_edges, rank_bets, build_efficiency_data in sequence
- Display ranked bet cards with tier color coding
- Surface kill switch flags as inline warnings

DO NOT add API calls, math, or betting logic to this file.
"""

import os
import json
import time
import html as _html
from datetime import datetime
from pathlib import Path

import streamlit as st

from edge_calculator import calculate_edges, _SPORT_ROUTING
from bet_ranker import rank_bets
from bet_card_renderer import render_bet_card, render_slate_header, render_slate_footer
from data.efficiency_feed import build_efficiency_data
from odds_fetcher import fetch_game_lines, get_quota_status, cache_open_prices, compute_rlm


# ---------------------------------------------------------------------------
# Activity tracking — inactivity auto-stop pattern
# Writes last_activity.json on every page load. No scheduler in v36 reads this
# yet, but the file is available if a scheduler is ever added.
# ---------------------------------------------------------------------------

_ACTIVITY_FILE = Path(__file__).resolve().parent / "data" / "last_activity.json"


def _touch_activity() -> None:
    """Update last-user-activity timestamp. Called on every Streamlit page load."""
    try:
        _ACTIVITY_FILE.parent.mkdir(exist_ok=True)
        _ACTIVITY_FILE.write_text(json.dumps({"ts": time.time()}))
    except OSError:
        pass


_touch_activity()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPORT_GROUPS = {
    "Basketball": ["NBA", "NCAAB"],
    "Football":   ["NFL", "NCAAF"],
    "Other":      ["NHL", "MLB"],
    "Soccer":     ["EPL", "LIGUE1", "BUNDESLIGA", "SERIE_A", "LA_LIGA", "MLS"],
}

DEFAULT_SPORTS = {"NBA", "NCAAB"}


# ---------------------------------------------------------------------------
# CSS — Precision Instrument aesthetic
# IBM Plex Mono: authoritative data font, designed for terminals and dashboards
# Palette: slate navy base, warm gold accent, cool teal secondary
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600;700&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

:root {
    /* Base */
    --bg-root:       #0D1117;
    --bg-card:       #161B22;
    --bg-card-2:     #1C2433;
    --bg-chip:       #1C2433;
    --bg-chip-on:    #1E2D1A;

    /* Accent */
    --gold:          #E8A020;
    --gold-dim:      #7A4A10;
    --gold-glow:     rgba(232, 160, 32, 0.15);
    --teal:          #14B8A6;
    --teal-dim:      rgba(20, 184, 166, 0.15);
    --green:         #22C55E;

    /* Text */
    --text-pri:      #E6EDF3;
    --text-sec:      #8B949E;
    --text-dim:      #6E7681;
    --text-on-gold:  #0D0D0D;

    /* Border */
    --border:        #21262D;
    --border-strong: #30363D;

    /* Fonts */
    --mono: 'IBM Plex Mono', 'Fira Code', 'Cascadia Code', monospace;
    --sans: 'IBM Plex Sans', system-ui, sans-serif;
}

/* ── Reset & Root ─────────────────────────────────────────────── */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    background-color: var(--bg-root) !important;
    color: var(--text-pri) !important;
    font-family: var(--mono) !important;
}

[data-testid="stHeader"]         { background-color: var(--bg-root) !important; }
[data-testid="stSidebar"]        { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
[data-testid="stDecoration"]     { display: none !important; }
footer                           { display: none !important; }

/* ── Layout ───────────────────────────────────────────────────── */
.block-container {
    max-width: 680px !important;
    padding: 3.5rem 1.25rem 3rem !important;
}

/* ── Typography base ──────────────────────────────────────────── */
h1, h2, h3, h4, p, span, label, div {
    font-family: var(--mono) !important;
    color: var(--text-pri) !important;
}

/* ── TITANIUM Wordmark ────────────────────────────────────────── */
/* Each letter is an individual span — no word-wrap, no letter-spacing break */
.tm-wordmark {
    display: flex;
    align-items: baseline;
    gap: 0;
    white-space: nowrap;
    overflow: hidden;
    margin: 0;
    padding: 0;
}
.tm-letter {
    font-family: var(--mono);
    font-size: clamp(1.6rem, 6vw, 2.4rem);
    font-weight: 700;
    color: var(--text-pri);
    display: inline-block;
    width: 1ch;
    text-align: center;
    line-height: 1;
}
.tm-letter-space {
    display: inline-block;
    width: 0.38em;
}
.tm-rule {
    height: 1px;
    background: linear-gradient(90deg, var(--gold) 0%, transparent 100%);
    margin: 8px 0 6px;
    opacity: 0.7;
    border: none;
}
.tm-sub {
    font-family: var(--mono);
    font-size: 0.65rem;
    font-weight: 300;
    letter-spacing: 0.28em;
    color: var(--text-dim);
    text-transform: uppercase;
}
.tm-badge {
    display: inline-block;
    font-size: 0.55rem;
    font-weight: 600;
    letter-spacing: 0.15em;
    color: var(--gold);
    border: 1px solid var(--gold-dim);
    padding: 1px 6px 1px;
    margin-left: 10px;
    vertical-align: middle;
    position: relative;
    top: -2px;
}

/* ── Section label ────────────────────────────────────────────── */
.t-section-label {
    font-size: 0.58rem;
    font-weight: 600;
    letter-spacing: 0.22em;
    color: var(--text-dim);
    text-transform: uppercase;
    margin-bottom: 8px;
    margin-top: 20px;
}

/* ── Sport chip grid ──────────────────────────────────────────── */
/* We render chips via HTML + checkbox hack */
.chip-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 4px;
}
.chip {
    font-family: var(--mono);
    font-size: 0.7rem;
    font-weight: 500;
    letter-spacing: 0.08em;
    padding: 5px 12px;
    border: 1px solid var(--border-strong);
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.12s ease;
    color: var(--text-sec);
    background: var(--bg-chip);
    user-select: none;
}
.chip.active {
    background: var(--bg-chip-on);
    border-color: var(--green);
    color: var(--green);
}

/* ── Streamlit checkbox — hidden but functional ───────────────── */
[data-testid="stCheckbox"] {
    display: inline-flex !important;
    margin: 0 !important;
    padding: 0 !important;
}
[data-testid="stCheckbox"] > label {
    display: flex !important;
    align-items: center !important;
    gap: 6px !important;
    padding: 5px 12px !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 3px !important;
    background: var(--bg-chip) !important;
    cursor: pointer !important;
    transition: all 0.12s ease !important;
    font-family: var(--mono) !important;
    font-size: 0.7rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.08em !important;
    color: var(--text-sec) !important;
    line-height: 1.2 !important;
    min-height: unset !important;
    margin: 0 !important;
}
[data-testid="stCheckbox"] > label:has(input:checked) {
    background: var(--bg-chip-on) !important;
    border-color: var(--green) !important;
    color: var(--green) !important;
}
/* Hide the actual checkbox widget, keep it clickable */
[data-testid="stCheckbox"] input[type="checkbox"] {
    position: absolute !important;
    opacity: 0 !important;
    width: 0 !important;
    height: 0 !important;
}
/* Remove the Streamlit checkbox box graphic */
[data-testid="stCheckbox"] div[data-baseweb="checkbox"] > div:first-child {
    display: none !important;
}
[data-testid="stCheckbox"] .st-emotion-cache-1kyxreq,
[data-testid="stCheckbox"] [class*="checkbox"] > div:first-child {
    display: none !important;
}

/* ── Execute Button ───────────────────────────────────────────── */
[data-testid="stButton"] > button {
    width: 100% !important;
    background: var(--gold) !important;
    color: var(--text-on-gold) !important;
    border: none !important;
    border-radius: 2px !important;
    font-family: var(--mono) !important;
    font-size: 0.82rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.3em !important;
    padding: 0.85rem 1rem !important;
    text-transform: uppercase !important;
    cursor: pointer !important;
    transition: opacity 0.15s ease, background 0.15s ease !important;
    margin-top: 12px !important;
}
[data-testid="stButton"] > button:hover:not(:disabled) {
    opacity: 0.9 !important;
}
[data-testid="stButton"] > button:disabled {
    background: #2A2010 !important;
    color: #5A4A20 !important;
    cursor: not-allowed !important;
}
/* Scanning animation */
[data-testid="stButton"] > button[aria-disabled="true"].scanning {
    background: #1A1500 !important;
    color: var(--gold) !important;
    border: 1px solid var(--gold-dim) !important;
    animation: pulse-border 1.5s ease infinite !important;
}
@keyframes pulse-border {
    0%, 100% { box-shadow: 0 0 0 0 var(--gold-glow); }
    50%       { box-shadow: 0 0 0 6px transparent; }
}

/* ── Progress bar ─────────────────────────────────────────────── */
[data-testid="stProgressBar"] > div > div {
    background-color: var(--gold) !important;
    border-radius: 1px !important;
}
[data-testid="stProgressBar"] > div {
    background-color: var(--border) !important;
    border-radius: 1px !important;
    height: 2px !important;
}

/* ── Status widget ────────────────────────────────────────────── */
[data-testid="stStatusWidget"],
[data-testid="stExpander"] {
    background-color: var(--bg-card-2) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: 2px !important;
    font-family: var(--mono) !important;
    font-size: 0.75rem !important;
    color: var(--text-sec) !important;
}

/* ── Alert / Info blocks ──────────────────────────────────────── */
[data-testid="stAlert"] {
    background-color: var(--bg-card) !important;
    border-radius: 2px !important;
    border: 1px solid var(--border-strong) !important;
    border-left: 3px solid var(--border-strong) !important;
    font-family: var(--mono) !important;
    font-size: 0.78rem !important;
    color: var(--text-sec) !important;
}
[data-testid="stAlert"][data-type="info"] {
    border-left-color: var(--teal) !important;
}
[data-testid="stAlert"][data-type="error"] {
    border-left-color: #EF4444 !important;
}
[data-testid="stAlert"][data-type="warning"] {
    border-left-color: var(--gold) !important;
}

/* ── Horizontal rule ──────────────────────────────────────────── */
hr {
    border: none !important;
    border-top: 1px solid var(--border) !important;
    margin: 1.25rem 0 !important;
}

/* ── Bet cards ────────────────────────────────────────────────── */
.bet-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 16px 18px 14px;
    margin-bottom: 10px;
    font-family: var(--mono);
    position: relative;
    overflow: hidden;
    transition: border-color 0.15s ease;
}
.bet-card::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
    border-radius: 4px 0 0 4px;
}
.bet-card.nuclear::before  { background: var(--gold); }
.bet-card.standard::before { background: var(--teal); }
.bet-card.lean::before     { background: var(--border-strong); }

.bet-card.nuclear  { border-color: rgba(232, 160, 32, 0.18); }
.bet-card.standard { border-color: rgba(20, 184, 166, 0.15); }

/* Card header row */
.bc-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
}
.bc-rank-meta {
    font-size: 0.6rem;
    font-weight: 500;
    letter-spacing: 0.18em;
    color: var(--text-dim);
    text-transform: uppercase;
}
.bc-tier {
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    padding: 2px 8px;
    border-radius: 2px;
}
.bc-tier.nuclear  {
    background: rgba(232, 160, 32, 0.12);
    color: var(--gold);
    border: 1px solid rgba(232, 160, 32, 0.3);
}
.bc-tier.standard {
    background: rgba(20, 184, 166, 0.1);
    color: var(--teal);
    border: 1px solid rgba(20, 184, 166, 0.25);
}
.bc-tier.lean {
    background: transparent;
    color: var(--text-dim);
    border: 1px solid var(--border-strong);
}

/* Matchup */
.bc-matchup {
    font-size: 1.0rem;
    font-weight: 600;
    color: var(--text-pri);
    margin-bottom: 3px;
    line-height: 1.3;
}
.bc-target-line {
    font-size: 0.8rem;
    color: var(--text-sec);
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.bc-price {
    font-weight: 600;
    color: var(--text-pri);
}
.bc-book {
    font-size: 0.68rem;
    color: var(--text-dim);
    padding: 1px 6px;
    border: 1px solid var(--border-strong);
    border-radius: 2px;
}

/* Stats grid */
.bc-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px 4px;
    padding: 10px 0 8px;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    margin-bottom: 8px;
}
.bc-stat-label {
    font-size: 0.55rem;
    font-weight: 500;
    letter-spacing: 0.15em;
    color: var(--text-dim);
    text-transform: uppercase;
    margin-bottom: 3px;
}
.bc-stat-value {
    font-size: 0.88rem;
    font-weight: 600;
    color: var(--text-pri);
    line-height: 1.1;
}
.bc-stat-value.v-gold  { color: var(--gold); }
.bc-stat-value.v-teal  { color: var(--teal); }
.bc-stat-value.v-green { color: var(--green); }

/* Nemesis */
.bc-nemesis {
    font-size: 0.68rem;
    color: var(--text-dim);
    line-height: 1.4;
    margin-top: 6px;
    padding: 7px 10px;
    background: #0D1117;
    border: 1px solid var(--border);
    border-radius: 2px;
}
.bc-nemesis::before {
    content: '▶ ';
    color: var(--text-dim);
    font-size: 0.55rem;
}

/* Flag warning */
.bc-flag {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    margin-top: 8px;
    padding: 4px 9px;
    background: rgba(232, 160, 32, 0.08);
    border: 1px solid rgba(232, 160, 32, 0.25);
    border-radius: 2px;
    font-size: 0.63rem;
    font-weight: 500;
    letter-spacing: 0.1em;
    color: var(--gold);
    text-transform: uppercase;
}
.bc-flag::before { content: '⚑ '; }

/* ── Results header ───────────────────────────────────────────── */
.results-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
}
.results-count {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    color: var(--text-pri);
}
.results-info {
    font-size: 0.62rem;
    color: var(--text-dim);
    letter-spacing: 0.06em;
}

/* ── Empty state ──────────────────────────────────────────────── */
.empty-state {
    text-align: center;
    padding: 3rem 1rem;
}
.empty-state-icon {
    font-size: 1.5rem;
    margin-bottom: 12px;
    opacity: 0.3;
}
.empty-state-text {
    font-size: 0.75rem;
    font-weight: 400;
    letter-spacing: 0.08em;
    color: var(--text-dim);
    line-height: 1.6;
}

/* ── Well-priced state ────────────────────────────────────────── */
.well-priced {
    padding: 1.5rem;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 4px;
    border-left: 3px solid var(--teal);
    text-align: center;
}
.well-priced-main {
    font-size: 0.82rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    color: var(--teal);
    margin-bottom: 6px;
}
.well-priced-sub {
    font-size: 0.65rem;
    color: var(--text-dim);
    letter-spacing: 0.06em;
}

/* ── Footer ───────────────────────────────────────────────────── */
.t-footer {
    margin-top: 2rem;
    padding-top: 12px;
    border-top: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
}
.t-footer-item {
    font-size: 0.6rem;
    font-weight: 400;
    letter-spacing: 0.1em;
    color: var(--text-dim);
    text-transform: uppercase;
}
.t-footer-dot {
    color: var(--border-strong);
    margin: 0 4px;
}

/* ── Mobile refinements ───────────────────────────────────────── */
@media (max-width: 600px) {
    .block-container {
        padding: 1.25rem 0.85rem 3rem !important;
    }
    .bc-stats {
        grid-template-columns: repeat(2, 1fr);
        gap: 10px 8px;
    }
    .bc-matchup { font-size: 0.9rem; }
    .tm-letter  { font-size: clamp(1.3rem, 6vw, 1.8rem); }
}

/* ── Column layout flush ──────────────────────────────────────── */
[data-testid="stHorizontalBlock"] {
    gap: 6px !important;
    flex-wrap: wrap !important;
}
[data-testid="column"] {
    min-width: 0 !important;
    flex: 0 0 auto !important;
}
</style>
"""


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def render_header():
    """Render the TITANIUM wordmark — letters as individual spans to prevent wrapping."""
    letters = list("TITANIUM")
    letter_spans = ""
    for letter in letters:
        letter_spans += f'<span class="tm-letter">{letter}</span><span class="tm-letter-space"></span>'
    # Remove trailing space span
    letter_spans = letter_spans.rstrip('<span class="tm-letter-space"></span>')

    st.markdown(f"""
<div style="margin-bottom: 0.5rem;">
  <div class="tm-wordmark">
    {letter_spans}
    <span class="tm-badge">V36.1</span>
  </div>
  <hr class="tm-rule">
  <div class="tm-sub">Edge Detection Engine</div>
</div>
""", unsafe_allow_html=True)


def render_sport_selector() -> list[str]:
    """Render grouped sport toggle chips. Returns list of selected sport keys."""
    selected = []
    for group_name, sports in SPORT_GROUPS.items():
        st.markdown(f'<div class="t-section-label">{group_name}</div>', unsafe_allow_html=True)
        # Cap at 3 per row so soccer labels (e.g. BUNDESLIGA) never truncate
        cols_per_row = min(3, len(sports))
        rows = [sports[i:i + cols_per_row] for i in range(0, len(sports), cols_per_row)]
        for row in rows:
            cols = st.columns(cols_per_row)
            for i, sport in enumerate(row):
                default_on = sport in DEFAULT_SPORTS
                if cols[i].checkbox(sport, value=default_on, key=f"sport_{sport}"):
                    selected.append(sport)
    return selected


# render_bet_card() removed — promoted to bet_card_renderer.py (Session 14).


# ---------------------------------------------------------------------------
# Pipeline execution
# ---------------------------------------------------------------------------

def run_pipeline(selected_sports: list[str]):
    """Execute the full edge-detection pipeline for selected sports."""
    all_candidates = []
    all_raw_games  = {}   # event_id → raw game dict — for Odds Comparison page
    eff_data       = {}
    rlm_data       = {}   # event_id → bool: True = RLM confirmed
    n              = len(selected_sports)

    # Clear per-card tracked state from prior run so stale ✓ TRACKED labels
    # don't reappear for the same event_id on a fresh scan.
    for k in [k for k in st.session_state if k.startswith("tracked_") or k.startswith("track_")]:
        del st.session_state[k]

    progress = st.progress(0, text="")

    for idx, sport in enumerate(selected_sports):
        pct = int((idx / n) * 90)
        progress.progress(pct, text=f"Scanning {sport}...")

        with st.status(f"{sport}", expanded=False) as status:
            try:
                # Fetch raw games once — reuse for RLM detection + calculate_edges
                routing   = _SPORT_ROUTING.get(sport, {})
                sport_key = routing.get("sport_key", "")
                raw_games = fetch_game_lines(sport_key) if sport_key else []

                # Accumulate for Odds Comparison page (zero extra API calls)
                for g in raw_games:
                    all_raw_games[g["id"]] = g

                # RLM 2.0: persist first-ever-seen prices to Supabase so multi-day
                # line movement is visible across sessions, not just intra-session.
                from data.price_history_store import (
                    is_configured as _ph_configured,
                    record_new_events,
                    inject_into_cache,
                )
                if _ph_configured():
                    record_new_events(raw_games)   # write first-seen prices for new event_ids
                    inject_into_cache(raw_games)   # pre-seed _OPEN_PRICE_CACHE with historical prices

                # Passive RLM: freeze open prices on first fetch; detect movement on refresh
                cache_open_prices(raw_games)
                sport_rlm = compute_rlm(raw_games)
                rlm_data.update(sport_rlm)

                # Pass pre-fetched games so calculate_edges doesn't call the API again
                candidates = calculate_edges(sport, raw_games=raw_games)
                all_candidates.extend(candidates)
                status.update(
                    label=f"{sport} — {len(candidates)} candidates",
                    state="complete",
                    expanded=False,
                )

                eff_data.update(build_efficiency_data(raw_games))

            except ValueError as exc:
                status.update(label=f"{sport} — {exc}", state="error")
            except Exception as exc:
                err = str(exc)
                if "401" in err or "403" in err or "Unauthorized" in err:
                    progress.empty()
                    st.session_state["running"] = False
                    st.error(
                        "API key error — verify ODDS_API_KEY in .streamlit/secrets.toml"
                    )
                    return
                status.update(label=f"{sport} — fetch error: {err}", state="error")

    try:
        progress.progress(100, text="Ranking...")
        ranked = rank_bets(all_candidates, efficiency_data=eff_data, rlm_data=rlm_data)

        st.session_state["results"]     = ranked
        st.session_state["last_run"]    = datetime.now()
        st.session_state["last_sports"] = selected_sports
        st.session_state["raw_games"]   = all_raw_games  # event_id → game dict
    finally:
        st.session_state["running"] = False
        progress.empty()


# ---------------------------------------------------------------------------
# Page: Live Analysis (current working app — fully functional)
# ---------------------------------------------------------------------------

def page_live_analysis():
    """Live edge-detection analysis — the core product."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # Session defaults
    for key, default in [
        ("results",     []),
        ("last_run",    None),
        ("last_sports", []),
        ("running",     False),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # ── Header ──────────────────────────────────────────────────
    render_header()
    st.markdown("---")

    # ── API key guard ────────────────────────────────────────────
    api_key = os.environ.get("ODDS_API_KEY") or st.secrets.get("ODDS_API_KEY", "")
    if not api_key:
        st.error(
            "ODDS_API_KEY not found — add it to .streamlit/secrets.toml"
        )
        return

    # ── Sport selector ───────────────────────────────────────────
    st.markdown('<div class="t-section-label">Select Markets</div>', unsafe_allow_html=True)
    selected_sports = render_sport_selector()
    st.markdown("")

    # ── Execute button ───────────────────────────────────────────
    is_running     = st.session_state["running"]
    no_selection   = len(selected_sports) == 0
    btn_disabled   = is_running or no_selection
    btn_label      = "SCANNING..." if is_running else "EXECUTE SCAN"

    if st.button(
        btn_label,
        disabled=btn_disabled,
        use_container_width=True,
    ):
        st.session_state["running"] = True
        run_pipeline(selected_sports)
        st.rerun()

    # ── Results ──────────────────────────────────────────────────
    st.markdown("---")
    ranked = st.session_state["results"]
    last_run = st.session_state["last_run"]

    if last_run is not None:
        run_time    = last_run.strftime("%H:%M")
        sport_str   = " · ".join(st.session_state["last_sports"])
        result_count = len(ranked)

        if result_count == 0:
            st.markdown(f"""
<div class="well-priced">
  <div class="well-priced-main">Market is well-priced today</div>
  <div class="well-priced-sub">No edges found &nbsp;·&nbsp; {sport_str} &nbsp;·&nbsp; {run_time}</div>
</div>
""", unsafe_allow_html=True)

        else:
            from data.bet_history_store import insert_bet, is_configured as _is_configured

            st.markdown(f"""
<div class="results-meta">
  <span class="results-count">{result_count} bet{"s" if result_count != 1 else ""} found</span>
  <span class="results-info">{sport_str} &nbsp;·&nbsp; {run_time}</span>
</div>
""", unsafe_allow_html=True)

            # Slate header (tier summary)
            st.html(render_slate_header(ranked, title=""))

            # Per-card loop: card HTML + Track Bet button
            _track_enabled = _is_configured()
            for i, bet in enumerate(ranked):
                st.html(render_bet_card(bet, rank=i + 1))

                if _track_enabled:
                    track_key = f"track_{bet.event_id}_{bet.market_type}_{i}"
                    tracked_key = f"tracked_{bet.event_id}_{bet.market_type}_{i}"

                    if st.session_state.get(tracked_key):
                        st.markdown(
                            '<div style="font-size:0.65rem;color:#22C55E;'
                            'letter-spacing:0.1em;margin:-6px 0 8px 2px;">✓ TRACKED</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        if st.button(
                            "+ TRACK BET",
                            key=track_key,
                            use_container_width=False,
                        ):
                            try:
                                insert_bet(
                                    sport=bet.sport,
                                    matchup=bet.matchup,
                                    market_type=bet.market_type,
                                    target=bet.target,
                                    line=bet.line,
                                    price=bet.price,
                                    edge_pct=bet.edge_pct,
                                    sharp_score=int(bet.sharp_score),
                                    signal=bet.signal,
                                    kelly_size=bet.kelly_size,
                                )
                                # Record CLV open price. Use bet.price — NOT get_open_price()
                                # (R&D Session 22: get_open_price has team-name key collision
                                # across h2h/spreads markets; bet.price is always correct).
                                from data.clv_store import (
                                    record_clv_open,
                                    is_configured as _clv_configured,
                                )
                                if _clv_configured():
                                    record_clv_open(
                                        event_id=bet.event_id,
                                        target=bet.target,
                                        market_type=bet.market_type,
                                        open_price=bet.price,
                                        sport=bet.sport,
                                        matchup=bet.matchup,
                                    )
                                st.session_state[tracked_key] = True
                                # Bust bet history cache so the History page reflects it
                                st.session_state.pop("bet_history_data", None)
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Track failed: {exc}")

            # Slate footer (total Kelly)
            st.html(render_slate_footer(ranked))

    else:
        st.markdown("""
<div class="empty-state">
  <div class="empty-state-icon">—</div>
  <div class="empty-state-text">Select markets above<br>and press EXECUTE SCAN</div>
</div>
""", unsafe_allow_html=True)

    # ── Footer ───────────────────────────────────────────────────
    try:
        quota_str = get_quota_status()
    except Exception:
        quota_str = "unavailable"

    run_ts = (
        last_run.strftime("%b %d · %H:%M") if last_run else "—"
    )
    st.markdown(f"""
<div class="t-footer">
  <span class="t-footer-item">API Quota &nbsp;// &nbsp;{quota_str}</span>
  <span class="t-footer-item">Last run {run_ts}</span>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Page stubs — future sessions
# ---------------------------------------------------------------------------

def page_bet_history():
    """Bet History — log of tracked bets and outcomes."""
    from data.bet_history_store import (
        is_configured,
        fetch_bets,
        compute_pnl_summary,
        update_outcome,
    )

    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # ── Page header ──────────────────────────────────────────────
    render_header()
    st.markdown("---")
    st.markdown('<div class="t-section-label">Bet History</div>', unsafe_allow_html=True)

    # ── Config guard ─────────────────────────────────────────────
    if not is_configured():
        st.html("""
<div style="
  padding: 20px 22px;
  background: #161B22;
  border: 1px solid #30363D;
  border-left: 3px solid #EF4444;
  border-radius: 4px;
  margin-top: 16px;
  font-family: 'IBM Plex Mono', monospace;
">
  <div style="font-size: 0.7rem; font-weight: 700; letter-spacing: 0.18em; color: #EF4444; text-transform: uppercase; margin-bottom: 8px;">
    SUPABASE NOT CONFIGURED
  </div>
  <div style="font-size: 0.75rem; color: #8B949E; line-height: 1.6;">
    Add <span style="color: #E8A020;">SUPABASE_URL</span> and <span style="color: #E8A020;">SUPABASE_KEY</span>
    to <span style="color: #E6EDF3;">.streamlit/secrets.toml</span> to enable bet tracking.
  </div>
</div>
""")
        return

    # ── Fetch + cache ─────────────────────────────────────────────
    if "bet_history_data" not in st.session_state:
        st.session_state["bet_history_data"] = fetch_bets()

    all_bets     = st.session_state["bet_history_data"]
    pending_bets = [b for b in all_bets if b.get("outcome") is None]
    resolved_bets = [b for b in all_bets if b.get("outcome") in ("WIN", "LOSS", "PUSH")]
    summary      = compute_pnl_summary(all_bets)

    # Batch-fetch CLV data for all displayed bets (one query)
    from data.clv_store import fetch_clv_for_events, is_configured as _clv_configured
    _clv_data: dict = {}
    if _clv_configured() and all_bets:
        _event_ids = list({b["event_id"] for b in all_bets if b.get("event_id")})
        _clv_data = fetch_clv_for_events(_event_ids)

    # ── P&L Summary strip ────────────────────────────────────────
    net   = summary["net_units"]
    net_color = "#22C55E" if net > 0 else ("#EF4444" if net < 0 else "#6E7681")
    net_sign  = "+" if net > 0 else ""

    st.html(f"""
<div style="
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin: 14px 0 20px;
">
  <div style="
    background: #161B22;
    border: 1px solid #21262D;
    border-radius: 4px;
    padding: 12px 14px;
    font-family: 'IBM Plex Mono', monospace;
  ">
    <div style="font-size: 0.55rem; font-weight: 500; letter-spacing: 0.15em; color: #6E7681; text-transform: uppercase; margin-bottom: 5px;">Tracked</div>
    <div style="font-size: 1.1rem; font-weight: 600; color: #E6EDF3;">{summary['total_tracked']}</div>
  </div>
  <div style="
    background: #161B22;
    border: 1px solid #21262D;
    border-radius: 4px;
    padding: 12px 14px;
    font-family: 'IBM Plex Mono', monospace;
  ">
    <div style="font-size: 0.55rem; font-weight: 500; letter-spacing: 0.15em; color: #6E7681; text-transform: uppercase; margin-bottom: 5px;">Win Rate</div>
    <div style="font-size: 1.1rem; font-weight: 600; color: #E6EDF3;">{summary['win_rate'] * 100:.0f}%</div>
  </div>
  <div style="
    background: #161B22;
    border: 1px solid #21262D;
    border-radius: 4px;
    padding: 12px 14px;
    font-family: 'IBM Plex Mono', monospace;
  ">
    <div style="font-size: 0.55rem; font-weight: 500; letter-spacing: 0.15em; color: #6E7681; text-transform: uppercase; margin-bottom: 5px;">Net Units</div>
    <div style="font-size: 1.1rem; font-weight: 600; color: {net_color};">{net_sign}{net:.2f}u</div>
  </div>
  <div style="
    background: #161B22;
    border: 1px solid #21262D;
    border-radius: 4px;
    padding: 12px 14px;
    font-family: 'IBM Plex Mono', monospace;
  ">
    <div style="font-size: 0.55rem; font-weight: 500; letter-spacing: 0.15em; color: #6E7681; text-transform: uppercase; margin-bottom: 5px;">Pending</div>
    <div style="font-size: 1.1rem; font-weight: 600; color: #E8A020;">{len(pending_bets)}</div>
  </div>
</div>
""")

    # ── Pending bets ─────────────────────────────────────────────
    st.markdown('<div class="t-section-label" style="margin-top: 8px;">Pending Results</div>', unsafe_allow_html=True)

    if not pending_bets:
        st.html("""
<div style="
  padding: 18px 20px;
  background: #161B22;
  border: 1px solid #21262D;
  border-radius: 4px;
  font-family: 'IBM Plex Mono', monospace;
  text-align: center;
  margin-bottom: 6px;
">
  <div style="font-size: 0.7rem; color: #6E7681; letter-spacing: 0.1em;">No pending bets</div>
</div>
""")
    else:
        for bet in pending_bets:
            # Signal badge colour
            sig = bet.get("signal", "")
            if "NUCLEAR" in sig:
                sig_color = "#E8A020"
                sig_bg    = "rgba(232,160,32,0.1)"
                sig_bd    = "rgba(232,160,32,0.3)"
            elif "STANDARD" in sig:
                sig_color = "#3B82F6"
                sig_bg    = "rgba(59,130,246,0.1)"
                sig_bd    = "rgba(59,130,246,0.25)"
            else:
                sig_color = "#14B8A6"
                sig_bg    = "rgba(20,184,166,0.1)"
                sig_bd    = "rgba(20,184,166,0.25)"

            price_raw = bet.get("price", 0)
            price_fmt = f"+{price_raw}" if price_raw > 0 else str(price_raw)
            edge_fmt  = f"{bet.get('edge_pct', 0) * 100:.1f}%"
            score_fmt = str(int(bet.get("sharp_score", 0)))

            # Left: bet info card
            col_info, col_ctrl = st.columns([3, 2])
            with col_info:
                st.html(f"""
<div style="
  background: #161B22;
  border: 1px solid #21262D;
  border-radius: 4px;
  padding: 12px 14px;
  font-family: 'IBM Plex Mono', monospace;
  height: 100%;
">
  <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
    <span style="font-size: 0.62rem; font-weight: 500; letter-spacing: 0.08em; color: #8B949E;">{_html.escape(bet.get('sport',''))}</span>
    <span style="
      font-size: 0.58rem; font-weight: 700; letter-spacing: 0.12em;
      color: {sig_color}; background: {sig_bg}; border: 1px solid {sig_bd};
      padding: 1px 6px; border-radius: 2px;
    ">{sig}</span>
  </div>
  <div style="font-size: 0.9rem; font-weight: 600; color: #E6EDF3; margin-bottom: 4px; line-height: 1.3;">
    {_html.escape(bet.get('matchup',''))}
  </div>
  <div style="font-size: 0.72rem; color: #8B949E; margin-bottom: 8px;">
    {_html.escape(bet.get('market_type',''))} &nbsp;·&nbsp; {_html.escape(bet.get('target',''))}
  </div>
  <div style="display: flex; gap: 14px;">
    <span style="font-size: 0.68rem; color: #6E7681;">Price &nbsp;<span style="color: #E6EDF3; font-weight: 600;">{price_fmt}</span></span>
    <span style="font-size: 0.68rem; color: #6E7681;">Edge &nbsp;<span style="color: #14B8A6; font-weight: 600;">{edge_fmt}</span></span>
    <span style="font-size: 0.68rem; color: #6E7681;">Score &nbsp;<span style="color: #E8A020; font-weight: 600;">{score_fmt}</span></span>
  </div>
</div>
""")

            with col_ctrl:
                outcome_key = f"outcome_{bet['id']}"
                chosen = st.selectbox(
                    "Result",
                    options=["WIN", "LOSS", "PUSH"],
                    key=outcome_key,
                    label_visibility="collapsed",
                )
                if st.button("MARK RESULT", key=f"mark_{bet['id']}", use_container_width=True):
                    kelly = float(bet.get("kelly_size") or 0.5)
                    pnl   = kelly if chosen == "WIN" else (-kelly if chosen == "LOSS" else 0.0)
                    try:
                        update_outcome(bet["id"], chosen, pnl)
                        # Bust the cache so the page refreshes from DB
                        st.session_state.pop("bet_history_data", None)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Failed to update: {exc}")

    # ── History log ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="t-section-label">History Log</div>', unsafe_allow_html=True)

    if not resolved_bets:
        st.html("""
<div style="
  padding: 28px 20px;
  font-family: 'IBM Plex Mono', monospace;
  text-align: center;
">
  <div style="font-size: 0.7rem; color: #6E7681; letter-spacing: 0.1em;">No resolved bets yet</div>
</div>
""")
    else:
        # Build rows HTML
        rows_html = ""
        for i, bet in enumerate(resolved_bets):
            row_bg    = "#161B22" if i % 2 == 0 else "#1C2433"
            outcome   = bet.get("outcome", "")
            if outcome == "WIN":
                out_color = "#22C55E"
                out_bg    = "rgba(34,197,94,0.1)"
                out_bd    = "rgba(34,197,94,0.25)"
            elif outcome == "LOSS":
                out_color = "#EF4444"
                out_bg    = "rgba(239,68,68,0.1)"
                out_bd    = "rgba(239,68,68,0.25)"
            else:
                out_color = "#6E7681"
                out_bg    = "rgba(110,118,129,0.1)"
                out_bd    = "rgba(110,118,129,0.25)"

            pnl_val   = bet.get("pnl_units") or 0.0
            pnl_color = "#22C55E" if pnl_val > 0 else ("#EF4444" if pnl_val < 0 else "#6E7681")
            pnl_sign  = "+" if pnl_val > 0 else ""

            price_raw = bet.get("price", 0)
            price_fmt = f"+{price_raw}" if price_raw > 0 else str(price_raw)
            edge_fmt  = f"{bet.get('edge_pct', 0) * 100:.1f}%"
            score_fmt = str(int(bet.get("sharp_score", 0)))

            # Date: trim to MM/DD HH:MM
            raw_dt = bet.get("created_at", "")
            try:
                from datetime import datetime as _dt
                dt_obj  = _dt.fromisoformat(raw_dt.replace("Z", "+00:00"))
                date_fmt = dt_obj.strftime("%m/%d %H:%M")
            except Exception:
                date_fmt = raw_dt[:10] if raw_dt else "—"

            matchup_short = _html.escape(bet.get("matchup", ""))
            market_str    = _html.escape(bet.get("market_type", ""))

            # CLV lookup — keyed by (event_id, target, market_type)
            _clv_key = (bet.get("event_id", ""), bet.get("target", ""), bet.get("market_type", ""))
            _clv_row = _clv_data.get(_clv_key)
            if _clv_row and _clv_row.get("clv_pct") is not None:
                _clv_val = _clv_row["clv_pct"]
                clv_fmt   = f"{_clv_val:+.1f}pp"
                clv_color = "#22C55E" if _clv_val > 0 else ("#EF4444" if _clv_val < 0 else "#6E7681")
            else:
                clv_fmt   = "—"
                clv_color = "#6E7681"

            rows_html += f"""
<div style="
  display: grid;
  grid-template-columns: 64px 1fr 52px 44px 40px 36px 46px 52px 46px;
  gap: 0 6px;
  align-items: center;
  padding: 9px 12px;
  background: {row_bg};
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.68rem;
  border-bottom: 1px solid #21262D;
">
  <span style="color: #6E7681; white-space: nowrap;">{date_fmt}</span>
  <span style="color: #E6EDF3; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{matchup_short}</span>
  <span style="color: #8B949E; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{market_str}</span>
  <span style="color: #8B949E;">{price_fmt}</span>
  <span style="color: #14B8A6;">{edge_fmt}</span>
  <span style="color: #E8A020;">{score_fmt}</span>
  <span style="color: {clv_color}; font-weight: 600;">{clv_fmt}</span>
  <span style="
    text-align: center;
    font-size: 0.6rem; font-weight: 700; letter-spacing: 0.1em;
    color: {out_color}; background: {out_bg}; border: 1px solid {out_bd};
    padding: 2px 5px; border-radius: 2px;
  ">{outcome}</span>
  <span style="color: {pnl_color}; font-weight: 600;">{pnl_sign}{pnl_val:.2f}u</span>
</div>
"""

        st.html(f"""
<div style="
  border: 1px solid #21262D;
  border-radius: 4px;
  overflow: hidden;
  margin-top: 8px;
">
  <!-- Column headers -->
  <div style="
    display: grid;
    grid-template-columns: 64px 1fr 52px 44px 40px 36px 46px 52px 46px;
    gap: 0 6px;
    padding: 7px 12px;
    background: #0D1117;
    border-bottom: 1px solid #30363D;
    font-family: 'IBM Plex Mono', monospace;
  ">
    <span style="font-size: 0.52rem; font-weight: 600; letter-spacing: 0.15em; color: #6E7681; text-transform: uppercase;">Date</span>
    <span style="font-size: 0.52rem; font-weight: 600; letter-spacing: 0.15em; color: #6E7681; text-transform: uppercase;">Matchup</span>
    <span style="font-size: 0.52rem; font-weight: 600; letter-spacing: 0.15em; color: #6E7681; text-transform: uppercase;">Type</span>
    <span style="font-size: 0.52rem; font-weight: 600; letter-spacing: 0.15em; color: #6E7681; text-transform: uppercase;">Price</span>
    <span style="font-size: 0.52rem; font-weight: 600; letter-spacing: 0.15em; color: #6E7681; text-transform: uppercase;">Edge</span>
    <span style="font-size: 0.52rem; font-weight: 600; letter-spacing: 0.15em; color: #6E7681; text-transform: uppercase;">Score</span>
    <span style="font-size: 0.52rem; font-weight: 600; letter-spacing: 0.15em; color: #6E7681; text-transform: uppercase;">CLV</span>
    <span style="font-size: 0.52rem; font-weight: 600; letter-spacing: 0.15em; color: #6E7681; text-transform: uppercase;">Result</span>
    <span style="font-size: 0.52rem; font-weight: 600; letter-spacing: 0.15em; color: #6E7681; text-transform: uppercase;">P&amp;L</span>
  </div>
  {rows_html}
</div>
""")

    # ── Footer ───────────────────────────────────────────────────
    st.markdown(f"""
<div class="t-footer">
  <span class="t-footer-item">{summary['wins']}W &nbsp;{summary['losses']}L &nbsp;{summary['pushes']}P</span>
  <span class="t-footer-item">{summary['resolved']} resolved of {summary['total_tracked']} tracked</span>
</div>
""", unsafe_allow_html=True)


def page_pnl_tracker():
    """P&L Tracker — equity curve, ROI by sport, win rate by market type."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────
    st.html("""
<div style="margin-bottom:2rem;">
  <div style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;font-weight:600;
              letter-spacing:0.18em;color:#8B949E;text-transform:uppercase;
              margin-bottom:0.35rem;">TITANIUM V36.1</div>
  <div style="font-family:'IBM Plex Mono',monospace;font-size:1.4rem;font-weight:700;
              color:#E6EDF3;letter-spacing:0.04em;">P&amp;L TRACKER</div>
  <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;color:#8B949E;
              margin-top:0.25rem;">Running profit/loss — equity, sport breakdown, market type</div>
</div>
""")

    # ── Guard ─────────────────────────────────────────────────────
    from data.bet_history_store import is_configured, fetch_bets, compute_pnl_summary

    if not is_configured():
        st.html("""
<div style="padding:2.5rem 1.5rem;background:#161B22;border:1px solid #21262D;
            border-radius:8px;text-align:center;margin-top:2rem;">
  <div style="font-family:'IBM Plex Mono',monospace;font-size:0.85rem;color:#8B949E;">
    Supabase not configured — bet tracking unavailable.
  </div>
</div>
""")
        return

    # ── Fetch data ────────────────────────────────────────────────
    if "pnl_data" not in st.session_state:
        st.session_state["pnl_data"] = fetch_bets(limit=500)

    bets = st.session_state["pnl_data"]
    summary = compute_pnl_summary(bets)
    resolved = [b for b in bets if b.get("outcome") in ("WIN", "LOSS", "PUSH")]

    if not bets:
        st.html("""
<div style="padding:2.5rem 1.5rem;background:#161B22;border:1px solid #21262D;
            border-radius:8px;text-align:center;margin-top:2rem;">
  <div style="font-family:'IBM Plex Mono',monospace;font-size:0.85rem;color:#8B949E;">
    No bets tracked yet — use Live Analysis to track bets.
  </div>
</div>
""")
        return

    # ── Net units color ───────────────────────────────────────────
    net = summary["net_units"]
    net_color = "#22C55E" if net >= 0 else "#F87171"
    net_sign  = "+" if net >= 0 else ""
    win_rate_pct = f"{summary['win_rate'] * 100:.1f}%"

    # ── Summary strip ─────────────────────────────────────────────
    st.html(f"""
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.75rem;margin-bottom:1.5rem;">
  <div style="background:#161B22;border:1px solid #21262D;border-radius:8px;
              padding:1rem 0.75rem;text-align:center;">
    <div style="font-family:'IBM Plex Mono',monospace;font-size:1.4rem;font-weight:700;
                color:{net_color};">{net_sign}{net:.2f}u</div>
    <div style="font-family:'IBM Plex Mono',monospace;font-size:0.58rem;font-weight:600;
                letter-spacing:0.12em;color:#8B949E;text-transform:uppercase;margin-top:0.3rem;">Net Units</div>
  </div>
  <div style="background:#161B22;border:1px solid #21262D;border-radius:8px;
              padding:1rem 0.75rem;text-align:center;">
    <div style="font-family:'IBM Plex Mono',monospace;font-size:1.4rem;font-weight:700;
                color:#E8A020;">{win_rate_pct}</div>
    <div style="font-family:'IBM Plex Mono',monospace;font-size:0.58rem;font-weight:600;
                letter-spacing:0.12em;color:#8B949E;text-transform:uppercase;margin-top:0.3rem;">Win Rate</div>
  </div>
  <div style="background:#161B22;border:1px solid #21262D;border-radius:8px;
              padding:1rem 0.75rem;text-align:center;">
    <div style="font-family:'IBM Plex Mono',monospace;font-size:1.4rem;font-weight:700;
                color:#E6EDF3;">{summary['resolved']}</div>
    <div style="font-family:'IBM Plex Mono',monospace;font-size:0.58rem;font-weight:600;
                letter-spacing:0.12em;color:#8B949E;text-transform:uppercase;margin-top:0.3rem;">Resolved</div>
  </div>
  <div style="background:#161B22;border:1px solid #21262D;border-radius:8px;
              padding:1rem 0.75rem;text-align:center;">
    <div style="font-family:'IBM Plex Mono',monospace;font-size:1.4rem;font-weight:700;
                color:#E6EDF3;">{summary['total_tracked']}</div>
    <div style="font-family:'IBM Plex Mono',monospace;font-size:0.58rem;font-weight:600;
                letter-spacing:0.12em;color:#8B949E;text-transform:uppercase;margin-top:0.3rem;">Tracked</div>
  </div>
</div>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0.75rem;margin-bottom:2rem;">
  <div style="background:#161B22;border:1px solid #21262D;border-radius:8px;
              padding:0.75rem;text-align:center;">
    <div style="font-family:'IBM Plex Mono',monospace;font-size:1.1rem;font-weight:600;
                color:#22C55E;">{summary['wins']}W</div>
  </div>
  <div style="background:#161B22;border:1px solid #21262D;border-radius:8px;
              padding:0.75rem;text-align:center;">
    <div style="font-family:'IBM Plex Mono',monospace;font-size:1.1rem;font-weight:600;
                color:#F87171;">{summary['losses']}L</div>
  </div>
  <div style="background:#161B22;border:1px solid #21262D;border-radius:8px;
              padding:0.75rem;text-align:center;">
    <div style="font-family:'IBM Plex Mono',monospace;font-size:1.1rem;font-weight:600;
                color:#8B949E;">{summary['pushes']}P</div>
  </div>
</div>
""")

    # ── Equity curve ──────────────────────────────────────────────
    if resolved:
        # Sort resolved by created_at ascending for cumulative curve
        sorted_resolved = sorted(resolved, key=lambda b: b.get("created_at", ""))
        running = 0.0
        curve_data = []
        for i, b in enumerate(sorted_resolved):
            running += b.get("pnl_units") or 0.0
            curve_data.append({"Bet #": i + 1, "Cumulative Units": round(running, 3)})

        import pandas as pd
        df = pd.DataFrame(curve_data).set_index("Bet #")

        st.html("""
<div style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;font-weight:600;
            letter-spacing:0.14em;color:#8B949E;text-transform:uppercase;
            margin-bottom:0.5rem;">EQUITY CURVE</div>
""")
        # Use Streamlit native chart — works reliably in Streamlit Cloud
        st.line_chart(df, color="#14B8A6", height=180)

    # ── ROI by sport ──────────────────────────────────────────────
    sport_stats: dict[str, dict] = {}
    for b in resolved:
        sport = b.get("sport", "UNKNOWN")
        if sport not in sport_stats:
            sport_stats[sport] = {"w": 0, "l": 0, "p": 0, "units": 0.0}
        o = b.get("outcome")
        if o == "WIN":
            sport_stats[sport]["w"] += 1
        elif o == "LOSS":
            sport_stats[sport]["l"] += 1
        elif o == "PUSH":
            sport_stats[sport]["p"] += 1
        sport_stats[sport]["units"] += b.get("pnl_units") or 0.0

    if sport_stats:
        rows_html = ""
        for sport, s in sorted(sport_stats.items()):
            u = s["units"]
            u_color = "#22C55E" if u >= 0 else "#F87171"
            u_sign  = "+" if u >= 0 else ""
            wl = s["w"] + s["l"]
            wr = f"{s['w']/wl*100:.0f}%" if wl > 0 else "—"
            rows_html += f"""
<div style="display:grid;grid-template-columns:3fr 1fr 1fr 1.5fr;
            gap:0.5rem;padding:0.6rem 0.75rem;border-bottom:1px solid #21262D;
            align-items:center;">
  <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
              color:#E6EDF3;font-weight:500;">{sport}</div>
  <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
              color:#8B949E;">{s['w']}W-{s['l']}L</div>
  <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
              color:#E8A020;">{wr}</div>
  <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
              color:{u_color};font-weight:600;text-align:right;">{u_sign}{u:.2f}u</div>
</div>"""

        st.html(f"""
<div style="margin-bottom:2rem;">
  <div style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;font-weight:600;
              letter-spacing:0.14em;color:#8B949E;text-transform:uppercase;
              margin-bottom:0.5rem;">ROI BY SPORT</div>
  <div style="background:#161B22;border:1px solid #21262D;border-radius:8px;overflow:hidden;">
    <div style="display:grid;grid-template-columns:3fr 1fr 1fr 1.5fr;gap:0.5rem;
                padding:0.5rem 0.75rem;border-bottom:1px solid #30363D;background:#1C2433;">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:0.58rem;font-weight:600;
                  letter-spacing:0.1em;color:#6E7681;text-transform:uppercase;">Sport</div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:0.58rem;font-weight:600;
                  letter-spacing:0.1em;color:#6E7681;text-transform:uppercase;">Record</div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:0.58rem;font-weight:600;
                  letter-spacing:0.1em;color:#6E7681;text-transform:uppercase;">Win%</div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:0.58rem;font-weight:600;
                  letter-spacing:0.1em;color:#6E7681;text-transform:uppercase;text-align:right;">Units</div>
    </div>
    {rows_html}
  </div>
</div>
""")

    # ── Win rate by market type ────────────────────────────────────
    market_stats: dict[str, dict] = {}
    for b in resolved:
        mkt = b.get("market_type", "UNKNOWN")
        if mkt not in market_stats:
            market_stats[mkt] = {"w": 0, "l": 0, "p": 0, "units": 0.0}
        o = b.get("outcome")
        if o == "WIN":
            market_stats[mkt]["w"] += 1
        elif o == "LOSS":
            market_stats[mkt]["l"] += 1
        elif o == "PUSH":
            market_stats[mkt]["p"] += 1
        market_stats[mkt]["units"] += b.get("pnl_units") or 0.0

    if market_stats:
        mkt_rows = ""
        for mkt, s in sorted(market_stats.items()):
            u = s["units"]
            u_color = "#22C55E" if u >= 0 else "#F87171"
            u_sign  = "+" if u >= 0 else ""
            wl = s["w"] + s["l"]
            wr = f"{s['w']/wl*100:.0f}%" if wl > 0 else "—"
            mkt_rows += f"""
<div style="display:grid;grid-template-columns:3fr 1fr 1fr 1.5fr;
            gap:0.5rem;padding:0.6rem 0.75rem;border-bottom:1px solid #21262D;
            align-items:center;">
  <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
              color:#E6EDF3;font-weight:500;">{mkt}</div>
  <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
              color:#8B949E;">{s['w']}W-{s['l']}L</div>
  <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
              color:#E8A020;">{wr}</div>
  <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
              color:{u_color};font-weight:600;text-align:right;">{u_sign}{u:.2f}u</div>
</div>"""

        st.html(f"""
<div style="margin-bottom:2rem;">
  <div style="font-family:'IBM Plex Mono',monospace;font-size:0.6rem;font-weight:600;
              letter-spacing:0.14em;color:#8B949E;text-transform:uppercase;
              margin-bottom:0.5rem;">WIN RATE BY MARKET</div>
  <div style="background:#161B22;border:1px solid #21262D;border-radius:8px;overflow:hidden;">
    <div style="display:grid;grid-template-columns:3fr 1fr 1fr 1.5fr;gap:0.5rem;
                padding:0.5rem 0.75rem;border-bottom:1px solid #30363D;background:#1C2433;">
      <div style="font-family:'IBM Plex Mono',monospace;font-size:0.58rem;font-weight:600;
                  letter-spacing:0.1em;color:#6E7681;text-transform:uppercase;">Market</div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:0.58rem;font-weight:600;
                  letter-spacing:0.1em;color:#6E7681;text-transform:uppercase;">Record</div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:0.58rem;font-weight:600;
                  letter-spacing:0.1em;color:#6E7681;text-transform:uppercase;">Win%</div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:0.58rem;font-weight:600;
                  letter-spacing:0.1em;color:#6E7681;text-transform:uppercase;text-align:right;">Units</div>
    </div>
    {mkt_rows}
  </div>
</div>
""")

    # ── Refresh button ─────────────────────────────────────────────
    if st.button("↻  Refresh P&L", key="pnl_refresh"):
        st.session_state.pop("pnl_data", None)
        st.rerun()


def page_odds_comparison():
    """Odds Comparison — side-by-side line shopping across all books."""
    from data.odds_comparator import build_odds_comparison, to_dataframes

    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────
    render_header()
    st.markdown("---")
    st.markdown('<div class="t-section-label">Odds Comparison</div>', unsafe_allow_html=True)

    # ── No data state ─────────────────────────────────────────────
    raw_games: dict = st.session_state.get("raw_games", {})
    if not raw_games:
        st.html("""
<div class="empty-state" style="padding-top: 3rem;">
  <div class="empty-state-icon">⚖️</div>
  <div class="empty-state-text">No slate loaded.<br><br>Run a scan on the Live Analysis page first,<br>then return here to compare book prices.</div>
</div>
""")
        return

    # ── Game selector ─────────────────────────────────────────────
    game_list = list(raw_games.values())
    game_labels = [
        f"{g.get('away_team', '?')} @ {g.get('home_team', '?')}"
        for g in game_list
    ]
    selected_label = st.selectbox(
        "Select game",
        options=game_labels,
        key="odds_comp_game",
        label_visibility="collapsed",
    )
    selected_idx   = game_labels.index(selected_label)
    selected_game  = game_list[selected_idx]

    comp = build_odds_comparison(selected_game)
    h2h_rows, spread_rows, total_rows = to_dataframes(comp)

    books     = comp["books"]
    home      = comp["home_team"]
    away      = comp["away_team"]
    best      = comp["best_price"]
    sp_mkts   = comp["markets"]["spreads"]
    tot_mkts  = comp["markets"]["totals"]

    # ── Helper: best-price badge ──────────────────────────────────
    def _best_badge(info: dict | None) -> str:
        if not info:
            return ""
        return (
            f'<span style="font-size:0.65rem;color:#14B8A6;'
            f'letter-spacing:0.06em;margin-left:0.4rem;">'
            f'BEST {info["price"]:+d} @ {info["book"].upper()}</span>'
        )

    def _split_badge(split: bool) -> str:
        if not split:
            return ""
        return (
            '<span style="font-size:0.65rem;color:#F59E0B;'
            'letter-spacing:0.06em;margin-left:0.5rem;">⚠ LINE SPLIT</span>'
        )

    # ── Moneyline ─────────────────────────────────────────────────
    st.html(
        f'<div style="font-size:0.7rem;color:#8B949E;letter-spacing:0.12em;'
        f'text-transform:uppercase;margin:1.2rem 0 0.4rem 0;">Moneyline'
        + _best_badge(best.get("h2h_home"))
        + f'</div>'
    )
    if h2h_rows:
        import pandas as pd
        df_h2h = pd.DataFrame(h2h_rows).set_index("Book")
        st.dataframe(df_h2h, use_container_width=True)
    else:
        st.caption("No moneyline data available.")

    # ── Spreads ───────────────────────────────────────────────────
    spread_label = (
        f"Spreads — consensus {sp_mkts['line_consensus']:+g}"
        if sp_mkts["line_consensus"] is not None
        else "Spreads"
    )
    st.html(
        f'<div style="font-size:0.7rem;color:#8B949E;letter-spacing:0.12em;'
        f'text-transform:uppercase;margin:1.2rem 0 0.4rem 0;">{spread_label}'
        + _split_badge(sp_mkts["line_split"])
        + _best_badge(best.get("spread_home"))
        + f'</div>'
    )
    if spread_rows:
        df_spread = pd.DataFrame(spread_rows).set_index("Book")
        st.dataframe(df_spread, use_container_width=True)
    else:
        st.caption("No spread data available.")

    # ── Totals ────────────────────────────────────────────────────
    total_label = (
        f"Totals — consensus {tot_mkts['line_consensus']:g}"
        if tot_mkts["line_consensus"] is not None
        else "Totals"
    )
    st.html(
        f'<div style="font-size:0.7rem;color:#8B949E;letter-spacing:0.12em;'
        f'text-transform:uppercase;margin:1.2rem 0 0.4rem 0;">{total_label}'
        + _split_badge(tot_mkts["line_split"])
        + _best_badge(best.get("total_over"))
        + f'</div>'
    )
    if total_rows:
        df_total = pd.DataFrame(total_rows).set_index("Book")
        st.dataframe(df_total, use_container_width=True)
    else:
        st.caption("No totals data available.")

    # ── Books coverage note ───────────────────────────────────────
    st.html(
        f'<div style="font-size:0.6rem;color:#6B7280;margin-top:1rem;">'
        f'{len(books)} book{"s" if len(books) != 1 else ""} with data: '
        f'{", ".join(b.upper() for b in books)}'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Page: Parlay Builder (UI 4 — EXP 5 promoted Session 24)
# ---------------------------------------------------------------------------

def page_parlay_builder():
    """Parlay Builder — find positive-EV 2-leg parlay combos from current slate."""
    from data.parlay_builder import build_parlay_combos, format_parlay_table

    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────
    render_header()
    st.markdown("---")
    st.markdown('<div class="t-section-label">Parlay Builder</div>', unsafe_allow_html=True)

    # ── No data state ─────────────────────────────────────────────
    ranked: list = st.session_state.get("results", [])
    if not ranked:
        st.html("""
<div class="empty-state" style="padding-top: 3rem;">
  <div class="empty-state-icon">🔗</div>
  <div class="empty-state-text">No slate loaded.<br><br>Run a scan on the Live Analysis page first,<br>then return here to find positive-EV parlay combos.</div>
</div>
""")
        return

    # Convert BetCandidate dataclasses → dicts for parlay_builder
    bets_as_dicts = [vars(b) for b in ranked]
    combos = build_parlay_combos(bets_as_dicts)

    # ── Summary strip ─────────────────────────────────────────────
    st.html(
        f'<div style="font-size:0.7rem;color:#8B949E;letter-spacing:0.12em;'
        f'text-transform:uppercase;margin-bottom:1rem;">'
        f'{len(ranked)} ranked bet{"s" if len(ranked) != 1 else ""} → '
        f'{len(combos)} positive-EV combo{"s" if len(combos) != 1 else ""} found'
        f'</div>'
    )

    if not combos:
        st.html("""
<div class="empty-state" style="padding-top: 1rem;">
  <div class="empty-state-text">No positive-EV 2-leg parlays on current slate.<br>
  Parlay EV requires both legs to have sufficient edge to overcome the parlay's compounded vig.</div>
</div>
""")
        return

    # ── Combo table ───────────────────────────────────────────────
    for i, combo in enumerate(combos, start=1):
        a = combo["leg_a"]
        b = combo["leg_b"]
        ev_color = "#22C55E" if combo["parlay_ev"] > 0 else "#EF4444"

        st.html(
            f'<div style="background:#161B22;border:1px solid #21262D;border-radius:4px;'
            f'padding:1rem 1.2rem;margin-bottom:0.75rem;font-family:\'IBM Plex Mono\',monospace;">'

            # Row 1: combo number + EV
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'margin-bottom:0.6rem;">'
            f'<span style="font-size:0.65rem;color:#8B949E;letter-spacing:0.12em;">#{i} PARLAY</span>'
            f'<span style="font-size:0.85rem;font-weight:700;color:{ev_color};">'
            f'EV {combo["parlay_ev"]:+.4f}</span>'
            f'</div>'

            # Row 2: Leg A
            f'<div style="font-size:0.75rem;color:#E6EDF3;margin-bottom:0.3rem;">'
            f'<span style="color:#8B949E;">LEG A &nbsp;</span>'
            f'{a["target"]} &nbsp;'
            f'<span style="color:#8B949E;">{a["market_type"].upper()} @ </span>'
            f'<span style="color:#F5A623;">{a["price"]:+d}</span>'
            f'</div>'

            # Row 3: Leg B
            f'<div style="font-size:0.75rem;color:#E6EDF3;margin-bottom:0.6rem;">'
            f'<span style="color:#8B949E;">LEG B &nbsp;</span>'
            f'{b["target"]} &nbsp;'
            f'<span style="color:#8B949E;">{b["market_type"].upper()} @ </span>'
            f'<span style="color:#F5A623;">{b["price"]:+d}</span>'
            f'</div>'

            # Row 4: metrics
            f'<div style="display:flex;gap:1.5rem;font-size:0.65rem;color:#8B949E;">'
            f'<span>P(WIN) {combo["parlay_prob"]:.1%}</span>'
            f'<span>PAYOUT {combo["parlay_payout"]:.3f}u</span>'
            f'<span>{a["matchup"]}</span>'
            f'</div>'

            f'</div>'
        )

    # ── Disclosure ────────────────────────────────────────────────
    st.html(
        '<div style="font-size:0.6rem;color:#6B7280;margin-top:1.5rem;line-height:1.6;">'
        'Parlay EV = P(both win) × parlay payout − P(at least one loses). '
        'Only positive-EV combos shown. Assumes leg independence (different games only). '
        'Not a recommendation to bet parlays.'
        '</div>'
    )


# ---------------------------------------------------------------------------
# Entry point — st.navigation() multi-page scaffold (Streamlit 1.36+)
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="TITANIUM",
        layout="centered",
        initial_sidebar_state="expanded",
    )

    pg = st.navigation([
        st.Page(page_live_analysis,   title="Live Analysis",    icon="📡", default=True),
        st.Page(page_bet_history,     title="Bet History",      icon="📋"),
        st.Page(page_pnl_tracker,     title="P&L Tracker",      icon="📈"),
        st.Page(page_odds_comparison, title="Odds Comparison",  icon="⚖️"),
        st.Page(page_parlay_builder,  title="Parlay Builder",   icon="🔗"),
    ])
    pg.run()


if __name__ == "__main__":
    main()
