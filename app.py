"""
app.py — TITANIUM V36.1
========================
Streamlit UI ONLY. No business logic lives here.

Responsibilities:
- Render sport selector (toggle-style, grouped)
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
from data.efficiency_feed import build_efficiency_data
from odds_fetcher import fetch_game_lines, get_quota_status


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

TIER_COLORS = {
    "NUCLEAR_2.0U":  "#F59E0B",
    "STANDARD_1.0U": "#0D9488",
    "LEAN_0.5U":     "#475569",
    "PASS":          "#475569",
}

TIER_LABELS = {
    "NUCLEAR_2.0U":  "NUCLEAR",
    "STANDARD_1.0U": "STANDARD",
    "LEAN_0.5U":     "LEAN",
    "PASS":          "PASS",
}

TIER_SIZES = {
    "NUCLEAR_2.0U":  "2.0U",
    "STANDARD_1.0U": "1.0U",
    "LEAN_0.5U":     "0.5U",
    "PASS":          "–",
}


# ---------------------------------------------------------------------------
# CSS injection
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');

:root {
    --bg-root:    #0A0A0F;
    --bg-card:    #12121A;
    --bg-card-2:  #1A1A26;
    --amber:      #F59E0B;
    --amber-dim:  #92620A;
    --teal:       #0D9488;
    --slate:      #475569;
    --text-pri:   #E2E8F0;
    --text-dim:   #94A3B8;
    --text-muted: #64748B;
    --mono:       'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
}

/* Root */
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background-color: var(--bg-root) !important;
    color: var(--text-pri) !important;
}

[data-testid="stHeader"] { background-color: var(--bg-root) !important; }
[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }

/* Main content width */
.block-container {
    max-width: 720px !important;
    padding-top: 2rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

/* Typography */
h1, h2, h3, h4 {
    font-family: var(--mono) !important;
    color: var(--text-pri) !important;
    letter-spacing: 0.08em !important;
}

p, span, label, div {
    color: var(--text-pri) !important;
}

/* Header block */
.t-header {
    font-family: var(--mono);
    margin-bottom: 0.25rem;
}
.t-header .t-title {
    font-size: 1.6rem;
    font-weight: 700;
    letter-spacing: 0.35em;
    color: var(--text-pri);
}
.t-header .t-rule {
    border: none;
    border-top: 1px solid var(--amber);
    margin: 6px 0 4px 0;
    opacity: 0.6;
}
.t-header .t-sub {
    font-size: 0.72rem;
    letter-spacing: 0.22em;
    color: var(--text-dim);
}

/* Sport group label */
.sport-group-label {
    font-family: var(--mono);
    font-size: 0.62rem;
    letter-spacing: 0.2em;
    color: var(--text-muted);
    text-transform: uppercase;
    margin-bottom: 2px;
    margin-top: 10px;
}

/* Execute button */
[data-testid="stButton"] > button {
    width: 100%;
    background-color: var(--amber) !important;
    color: #0A0A0F !important;
    border: none !important;
    border-radius: 0 !important;
    font-family: var(--mono) !important;
    font-size: 0.85rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.25em !important;
    padding: 0.75rem 1rem !important;
    text-transform: uppercase !important;
    transition: opacity 0.15s ease !important;
}
[data-testid="stButton"] > button:hover { opacity: 0.88 !important; }
[data-testid="stButton"] > button:disabled {
    background-color: var(--amber-dim) !important;
    color: #3D2E0A !important;
    cursor: not-allowed !important;
}

/* Checkboxes — sport toggles */
[data-testid="stCheckbox"] label {
    font-family: var(--mono) !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.04em !important;
    color: var(--text-dim) !important;
}
[data-testid="stCheckbox"] input:checked + div {
    color: var(--amber) !important;
}

/* Progress */
[data-testid="stProgressBar"] > div > div {
    background-color: var(--amber) !important;
}

/* Status / spinner */
[data-testid="stStatusWidget"] {
    background-color: var(--bg-card-2) !important;
    border: 1px solid var(--slate) !important;
    border-radius: 0 !important;
    font-family: var(--mono) !important;
    font-size: 0.78rem !important;
}

/* Divider */
hr {
    border-color: #1E1E2E !important;
    margin: 1rem 0 !important;
}

/* Info / warning / error alerts */
[data-testid="stAlert"] {
    background-color: var(--bg-card-2) !important;
    border-radius: 0 !important;
    font-family: var(--mono) !important;
    font-size: 0.8rem !important;
    border-left: 3px solid var(--slate) !important;
}

/* Bet card styles */
.bet-card {
    background: var(--bg-card);
    border-radius: 4px;
    padding: 14px 16px;
    margin-bottom: 10px;
    font-family: var(--mono);
    position: relative;
}
.bet-card.nuclear {
    border-left: 3px solid #F59E0B;
    box-shadow: -2px 0 12px rgba(245, 158, 11, 0.12);
}
.bet-card.standard {
    border-left: 3px solid #0D9488;
    box-shadow: -2px 0 8px rgba(13, 148, 136, 0.08);
}
.bet-card.lean {
    border-left: 3px solid #475569;
}

.bc-rank {
    font-size: 0.62rem;
    letter-spacing: 0.18em;
    color: var(--text-muted);
    margin-bottom: 4px;
}
.bc-tier-nuclear { color: #F59E0B; font-weight: 700; font-size: 0.7rem; letter-spacing: 0.18em; }
.bc-tier-standard { color: #0D9488; font-weight: 700; font-size: 0.7rem; letter-spacing: 0.18em; }
.bc-tier-lean { color: #475569; font-weight: 700; font-size: 0.7rem; letter-spacing: 0.18em; }

.bc-matchup {
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--text-pri);
    margin: 4px 0 2px 0;
    letter-spacing: 0.02em;
}
.bc-target {
    font-size: 0.82rem;
    color: var(--text-dim);
    margin-bottom: 8px;
}
.bc-meta {
    font-size: 0.72rem;
    color: var(--text-muted);
    letter-spacing: 0.04em;
    margin-top: 2px;
}
.bc-stats {
    display: flex;
    gap: 16px;
    margin-top: 8px;
    flex-wrap: wrap;
}
.bc-stat {
    display: flex;
    flex-direction: column;
    gap: 1px;
}
.bc-stat-label {
    font-size: 0.58rem;
    letter-spacing: 0.15em;
    color: var(--text-muted);
    text-transform: uppercase;
}
.bc-stat-value {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text-pri);
}
.bc-stat-value.amber { color: #F59E0B; }
.bc-stat-value.teal  { color: #0D9488; }

.bc-nemesis {
    margin-top: 10px;
    padding: 7px 10px;
    background: #0D0D16;
    border-left: 2px solid #1E293B;
    font-size: 0.7rem;
    color: var(--text-muted);
    letter-spacing: 0.02em;
    font-style: italic;
}
.bc-flag {
    display: inline-block;
    margin-top: 8px;
    padding: 3px 8px;
    background: rgba(245, 158, 11, 0.12);
    border: 1px solid rgba(245, 158, 11, 0.3);
    border-radius: 2px;
    font-size: 0.65rem;
    letter-spacing: 0.1em;
    color: #F59E0B;
    text-transform: uppercase;
}

/* Timestamp / quota */
.t-footer {
    font-family: var(--mono);
    font-size: 0.68rem;
    color: var(--text-muted);
    letter-spacing: 0.06em;
    margin-top: 1.5rem;
    padding-top: 0.75rem;
    border-top: 1px solid #1E1E2E;
}

/* Mobile */
@media (max-width: 640px) {
    .bc-stats { gap: 10px; }
    .bc-matchup { font-size: 0.85rem; }
    .t-header .t-title { font-size: 1.25rem; letter-spacing: 0.22em; }
}
</style>
"""


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _tier_class(signal: str) -> str:
    if "NUCLEAR" in signal:
        return "nuclear"
    if "STANDARD" in signal:
        return "standard"
    return "lean"


def _tier_label_html(signal: str) -> str:
    tier = TIER_LABELS.get(signal, "LEAN")
    size = TIER_SIZES.get(signal, "0.5U")
    css_class = f"bc-tier-{_tier_class(signal)}"
    return f'<span class="{css_class}">{tier} &nbsp;{size}</span>'


def render_bet_card(rank: int, bet) -> str:
    """Build an HTML bet card from a BetCandidate object."""
    tier_class = _tier_class(bet.signal)
    tier_html  = _tier_label_html(bet.signal)

    edge_pct   = f"{bet.edge_pct * 100:.1f}%"
    sharp      = f"{bet.sharp_score:.0f}"
    kelly      = f"{bet.kelly_size:.2f}u"
    price      = f"{bet.price:+d}"
    win_prob   = f"{bet.win_prob * 100:.1f}%"

    edge_color = "amber" if bet.edge_pct >= 0.07 else ("teal" if bet.edge_pct >= 0.05 else "")
    sharp_color = "amber" if bet.sharp_score >= 90 else ("teal" if bet.sharp_score >= 80 else "")

    nemesis_html = ""
    if bet.nemesis and bet.nemesis.get("counter"):
        nem = bet.nemesis
        prob_str = f"{nem.get('probability', 0) * 100:.0f}%"
        counter  = nem.get("counter", "")
        adj      = nem.get("adjustment", 0)
        adj_str  = f"{adj:+d}pts" if adj else "—"
        nemesis_html = (
            f'<div class="bc-nemesis">'
            f'NEMESIS ({prob_str} counter probability, {adj_str}) &mdash; {counter}'
            f'</div>'
        )

    flag_html = ""
    if bet.kill_reason and bet.kill_reason.startswith("FLAG"):
        flag_text = bet.kill_reason.replace("FLAG: ", "").replace("FLAG:", "")
        flag_html = f'<div class="bc-flag">&#9888; {flag_text}</div>'

    book_short = bet.book.split("(")[0].strip() if bet.book else "—"

    card = f"""
<div class="bet-card {tier_class}">
  <div class="bc-rank">#{rank} &nbsp;&bull;&nbsp; {bet.sport} &nbsp;&bull;&nbsp; {bet.market_type.upper()}</div>
  {tier_html}
  <div class="bc-matchup">{bet.matchup}</div>
  <div class="bc-target">{bet.target} &nbsp;&nbsp;{price} &nbsp;&mdash;&nbsp; {book_short}</div>
  <div class="bc-stats">
    <div class="bc-stat">
      <span class="bc-stat-label">Edge</span>
      <span class="bc-stat-value {edge_color}">{edge_pct}</span>
    </div>
    <div class="bc-stat">
      <span class="bc-stat-label">Sharp</span>
      <span class="bc-stat-value {sharp_color}">{sharp}/100</span>
    </div>
    <div class="bc-stat">
      <span class="bc-stat-label">Win Prob</span>
      <span class="bc-stat-value">{win_prob}</span>
    </div>
    <div class="bc-stat">
      <span class="bc-stat-label">Kelly</span>
      <span class="bc-stat-value">{kelly}</span>
    </div>
  </div>
  {nemesis_html}
  {flag_html}
  <div class="bc-meta">{bet.commence_time or ""}</div>
</div>
"""
    return card


def render_header():
    st.markdown("""
<div class="t-header">
  <div class="t-title">T &nbsp; I &nbsp; T &nbsp; A &nbsp; N &nbsp; I &nbsp; U &nbsp; M</div>
  <hr class="t-rule">
  <div class="t-sub">V 3 6 . 1 &nbsp;&nbsp;//&nbsp;&nbsp; E D G E &nbsp; D E T E C T I O N &nbsp; E N G I N E</div>
</div>
""", unsafe_allow_html=True)


def render_sport_selector() -> list[str]:
    """Render grouped sport checkboxes. Returns list of selected sport keys."""
    selected = []
    for group_name, sports in SPORT_GROUPS.items():
        st.markdown(f'<div class="sport-group-label">{group_name}</div>', unsafe_allow_html=True)
        cols = st.columns(len(sports))
        for i, sport in enumerate(sports):
            default_on = sport in DEFAULT_SPORTS
            if cols[i].checkbox(sport, value=default_on, key=f"sport_{sport}"):
                selected.append(sport)
    return selected


# ---------------------------------------------------------------------------
# Pipeline execution
# ---------------------------------------------------------------------------

def run_pipeline(selected_sports: list[str]):
    """Execute the full edge-detection pipeline for selected sports."""
    all_candidates = []
    eff_data = {}

    progress = st.progress(0)
    n = len(selected_sports)

    for idx, sport in enumerate(selected_sports):
        pct = int((idx / n) * 100)
        progress.progress(pct, text=f"Scanning {sport}...")

        with st.status(f"Fetching {sport} odds...", expanded=False):
            try:
                candidates = calculate_edges(sport)
                st.write(f"{sport}: {len(candidates)} candidates after collar + edge filter")
                all_candidates.extend(candidates)

                if sport == "NCAAB":
                    routing = _SPORT_ROUTING.get("NCAAB", {})
                    sport_key = routing.get("sport_key", "basketball_ncaab")
                    raw_ncaab = fetch_game_lines(sport_key)
                    eff_data = build_efficiency_data(raw_ncaab)
                    st.write(f"NCAAB efficiency data: {len(eff_data)} games mapped")

            except ValueError as e:
                st.warning(f"{sport}: {e}")
            except Exception as e:
                err = str(e)
                if "401" in err or "403" in err or "Unauthorized" in err:
                    st.error("API key error — check ODDS_API_KEY in .streamlit/secrets.toml")
                    progress.empty()
                    return
                st.warning(f"{sport} fetch error: {err}")

    progress.progress(100, text="Ranking bets...")

    ranked = rank_bets(all_candidates, efficiency_data=eff_data)

    st.session_state["results"]     = ranked
    st.session_state["last_run"]    = datetime.now()
    st.session_state["last_sports"] = selected_sports
    st.session_state["running"]     = False

    progress.empty()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="TITANIUM",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    # Inject CSS
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # Session state defaults
    if "results"     not in st.session_state:
        st.session_state["results"]     = []
    if "last_run"    not in st.session_state:
        st.session_state["last_run"]    = None
    if "last_sports" not in st.session_state:
        st.session_state["last_sports"] = []
    if "running"     not in st.session_state:
        st.session_state["running"]     = False

    # --- Header ---
    render_header()
    st.markdown("---")

    # --- API key guard ---
    api_key = os.environ.get("ODDS_API_KEY") or st.secrets.get("ODDS_API_KEY", "")
    if not api_key:
        st.error(
            "ODDS_API_KEY not found. "
            "Add it to .streamlit/secrets.toml or set it as an environment variable."
        )
        return

    # --- Sport selector ---
    selected_sports = render_sport_selector()
    st.markdown("")

    # --- Execute button ---
    execute_disabled = st.session_state["running"] or len(selected_sports) == 0
    execute_label    = "SCANNING..." if st.session_state["running"] else "EXECUTE SCAN"

    if st.button(execute_label, disabled=execute_disabled, use_container_width=True):
        st.session_state["running"] = True
        run_pipeline(selected_sports)

    # --- Results ---
    st.markdown("---")
    ranked = st.session_state["results"]

    if st.session_state["last_run"] is not None:
        run_time    = st.session_state["last_run"].strftime("%H:%M:%S")
        sport_str   = " · ".join(st.session_state["last_sports"])
        result_count = len(ranked)

        if result_count == 0:
            st.info(
                "Market is well-priced today. No edges found.\n\n"
                f"Scanned: {sport_str}  ·  {run_time}"
            )
        else:
            st.markdown(
                f'<div class="bc-meta" style="margin-bottom:8px;">'
                f'{result_count} bet{"s" if result_count != 1 else ""} &nbsp;&bull;&nbsp; '
                f'{sport_str} &nbsp;&bull;&nbsp; {run_time}'
                f'</div>',
                unsafe_allow_html=True,
            )
            for i, bet in enumerate(ranked, 1):
                card_html = render_bet_card(i, bet)
                st.markdown(card_html, unsafe_allow_html=True)

    elif not st.session_state["running"]:
        st.markdown(
            '<div class="bc-meta" style="text-align:center; padding: 2rem 0;">'
            'Select sports above and press EXECUTE SCAN.'
            '</div>',
            unsafe_allow_html=True,
        )

    # --- Footer: quota status ---
    try:
        quota_str = get_quota_status()
    except Exception:
        quota_str = "quota status unavailable"

    st.markdown(
        f'<div class="t-footer">API QUOTA &nbsp;// &nbsp;{quota_str}</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
