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
from datetime import datetime

import streamlit as st

from edge_calculator import calculate_edges, _SPORT_ROUTING
from bet_ranker import rank_bets, format_bet_table
from bet_card_renderer import render_bet_slate
from data.efficiency_feed import build_efficiency_data
from odds_fetcher import fetch_game_lines, get_quota_status, cache_open_prices, compute_rlm


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
# Use: from bet_card_renderer import render_bet_slate


# ---------------------------------------------------------------------------
# Pipeline execution
# ---------------------------------------------------------------------------

def run_pipeline(selected_sports: list[str]):
    """Execute the full edge-detection pipeline for selected sports."""
    all_candidates = []
    eff_data       = {}
    rlm_data       = {}   # event_id → bool: True = RLM confirmed
    n              = len(selected_sports)

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

    progress.progress(100, text="Ranking...")
    ranked = rank_bets(all_candidates, efficiency_data=eff_data, rlm_data=rlm_data)

    st.session_state["results"]     = ranked
    st.session_state["last_run"]    = datetime.now()
    st.session_state["last_sports"] = selected_sports
    st.session_state["running"]     = False
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
            st.markdown(f"""
<div class="results-meta">
  <span class="results-count">{result_count} bet{"s" if result_count != 1 else ""} found</span>
  <span class="results-info">{sport_str} &nbsp;·&nbsp; {run_time}</span>
</div>
""", unsafe_allow_html=True)

            st.html(render_bet_slate(ranked, title=""))

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
    """Bet History — log of past bets and outcomes. (Coming soon)"""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown("""
<div class="empty-state" style="padding-top: 5rem;">
  <div class="empty-state-icon">—</div>
  <div class="empty-state-text">Bet History<br><br>Track recorded bets and outcomes.<br>Coming in a future session.</div>
</div>
""", unsafe_allow_html=True)


def page_pnl_tracker():
    """P&L Tracker — running profit/loss by sport and bet type. (Coming soon)"""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown("""
<div class="empty-state" style="padding-top: 5rem;">
  <div class="empty-state-icon">—</div>
  <div class="empty-state-text">P&amp;L Tracker<br><br>Running profit and loss by sport and bet type.<br>Coming in a future session.</div>
</div>
""", unsafe_allow_html=True)


def page_odds_comparison():
    """Odds Comparison — side-by-side line shopping across books. (Coming soon)"""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown("""
<div class="empty-state" style="padding-top: 5rem;">
  <div class="empty-state-icon">—</div>
  <div class="empty-state-text">Odds Comparison<br><br>Side-by-side line shopping across all books.<br>Coming in a future session.</div>
</div>
""", unsafe_allow_html=True)


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
        st.Page(page_live_analysis, title="Live Analysis",    icon="📡", default=True),
        st.Page(page_bet_history,   title="Bet History",      icon="📋"),
        st.Page(page_pnl_tracker,   title="P&L Tracker",      icon="📈"),
        st.Page(page_odds_comparison, title="Odds Comparison", icon="⚖️"),
    ])
    pg.run()


if __name__ == "__main__":
    main()
