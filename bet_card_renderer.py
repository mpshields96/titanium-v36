"""
bet_card_renderer.py — TITANIUM V36.1
======================================
HTML rendering for BetCandidate objects. No API calls, no math.

Produces self-contained HTML strings suitable for use with
Streamlit's st.markdown(..., unsafe_allow_html=True).

Public API:
    render_bet_card(bet: BetCandidate, rank: int = 0) -> str
        Returns a complete HTML card string for one bet.

    render_bet_slate(bets: list[BetCandidate], title: str = "Today's Slate") -> str
        Returns a full slate — header + cards + footer summary.

Design decisions:
    - Pure stdlib. No CSS framework dependencies.
    - Inline styles only — Streamlit strips <style> tags from markdown.
    - Tier colour coding:
        NUCLEAR_2.0U      → amber   (#F59E0B)
        STANDARD_1.0U     → blue    (#3B82F6)
        LEAN_0.5U         → teal    (#14B8A6)
        SPECULATIVE_0.25U → orange  (#F97316)  [sub-threshold, 0.25u cap, shown when calibration retry fires]
        PASS              → grey    (#6B7280)  [below threshold — not normally rendered]
    - RLM badge: only shown when sharp_breakdown["rlm"] > 0.
    - FLAG warnings: always shown (amber banner).
    - Nemesis: always shown when nemesis dict is non-empty (display-only per Session 12).
    - Kill_reason prefix logic:
        "KILL:" or "FORCE_UNDER:"  → should never reach card (filtered upstream)
                                     but render a red error banner if it does
        "FLAG:"                    → amber advisory banner
        ""                         → no banner (clean)

Promoted from R&D Session 14 to v36 Session 14.
"""

import html as _html

from edge_calculator import BetCandidate, sharp_to_size


# ---------------------------------------------------------------------------
# Tier configuration
# ---------------------------------------------------------------------------

_TIER_CONFIG = {
    "NUCLEAR_2.0U": {
        "label":       "⚡ NUCLEAR",
        "size_label":  "2.0u",
        "bg":          "#1C1917",       # near-black
        "accent":      "#F59E0B",       # amber
        "text":        "#FEF3C7",       # amber-50
        "border":      "#F59E0B",
        "badge_bg":    "#F59E0B",
        "badge_text":  "#1C1917",
    },
    "STANDARD_1.0U": {
        "label":       "▲ STANDARD",
        "size_label":  "1.0u",
        "bg":          "#0F172A",       # slate-900
        "accent":      "#3B82F6",       # blue-500
        "text":        "#E0F2FE",       # sky-100
        "border":      "#3B82F6",
        "badge_bg":    "#3B82F6",
        "badge_text":  "#FFFFFF",
    },
    "LEAN_0.5U": {
        "label":       "→ LEAN",
        "size_label":  "0.5u",
        "bg":          "#0F1F1E",       # very dark teal
        "accent":      "#14B8A6",       # teal-500
        "text":        "#CCFBF1",       # teal-100
        "border":      "#14B8A6",
        "badge_bg":    "#14B8A6",
        "badge_text":  "#0F1F1E",
    },
    "SPECULATIVE_0.25U": {
        "label":       "⚠ SPEC",
        "size_label":  "0.25u MAX",
        "bg":          "#1A0F00",       # very dark orange
        "accent":      "#F97316",       # orange-500
        "text":        "#FFEDD5",       # orange-100
        "border":      "#F97316",
        "badge_bg":    "#F97316",
        "badge_text":  "#1A0F00",
    },
    "PASS": {
        "label":       "— PASS",
        "size_label":  "—",
        "bg":          "#1F2937",       # grey-800
        "accent":      "#6B7280",       # grey-500
        "text":        "#D1D5DB",       # grey-300
        "border":      "#6B7280",
        "badge_bg":    "#6B7280",
        "badge_text":  "#FFFFFF",
    },
}

_DEFAULT_TIER = _TIER_CONFIG["PASS"]


def _tier_config(signal: str) -> dict:
    """Return the display config for a signal string."""
    return _TIER_CONFIG.get(signal, _DEFAULT_TIER)


# ---------------------------------------------------------------------------
# Helper renderers
# ---------------------------------------------------------------------------

def _fmt_price(price: int) -> str:
    """Format American odds with explicit sign."""
    return f"{price:+d}"


def _fmt_pct(val: float) -> str:
    return f"{val:.1%}"


def _fmt_score(val: float) -> str:
    return f"{val:.0f}"


def _rlm_badge_html(breakdown: dict) -> str:
    """Return RLM badge HTML if RLM contributed points, else empty string."""
    rlm_pts = breakdown.get("rlm", 0)
    if rlm_pts <= 0:
        return ""
    return (
        '<span style="'
        'display:inline-block;'
        'background:#8B5CF6;'       # violet-500
        'color:#EDE9FE;'            # violet-100
        'font-size:0.65rem;'
        'font-weight:700;'
        'letter-spacing:0.08em;'
        'padding:2px 7px;'
        'border-radius:4px;'
        'margin-left:6px;'
        'vertical-align:middle;'
        '">RLM</span>'
    )


def _kill_reason_banner_html(kill_reason: str, accent: str) -> str:
    """
    Render a kill_reason banner.
    FLAG: → amber advisory.
    KILL:/FORCE_UNDER: → red error (shouldn't happen but defensive).
    "" → empty string.
    """
    if not kill_reason:
        return ""

    if kill_reason.startswith("FLAG:"):
        msg = kill_reason[len("FLAG:"):].strip()
        bg, border, text = "#78350F", "#F59E0B", "#FEF3C7"
        icon = "⚠"
    elif kill_reason.startswith("KILL:") or kill_reason.startswith("FORCE_UNDER:"):
        msg = kill_reason
        bg, border, text = "#7F1D1D", "#EF4444", "#FEE2E2"
        icon = "✕"
    else:
        msg = kill_reason
        bg, border, text = "#1E3A5F", "#60A5FA", "#DBEAFE"
        icon = "ℹ"

    return (
        f'<div style="'
        f'background:{bg};'
        f'border-left:3px solid {border};'
        f'color:{text};'
        f'font-size:0.72rem;'
        f'padding:5px 10px;'
        f'margin-top:8px;'
        f'border-radius:0 4px 4px 0;'
        f'">{icon} {msg}</div>'
    )


def _nemesis_html(nemesis: dict, text_color: str) -> str:
    """Render Nemesis counter-thesis block. Display-only (Session 12)."""
    if not nemesis:
        return ""

    counter = nemesis.get("counter", "")
    prob = nemesis.get("probability", 0.0)
    adj = nemesis.get("adjustment", 0)

    if not counter:
        return ""

    adj_str = f"{adj:+d}pts" if adj != 0 else "no adj"
    prob_str = f"{prob:.0%}"

    return (
        f'<div style="'
        f'margin-top:10px;'
        f'padding:7px 10px;'
        f'background:rgba(255,255,255,0.04);'
        f'border-left:2px solid #4B5563;'
        f'border-radius:0 4px 4px 0;'
        f'">'
        f'<div style="font-size:0.65rem;color:#9CA3AF;letter-spacing:0.06em;'
        f'text-transform:uppercase;margin-bottom:3px;">Nemesis</div>'
        f'<div style="font-size:0.75rem;color:{text_color};line-height:1.4;">'
        f'{counter}'
        f'</div>'
        f'<div style="font-size:0.65rem;color:#9CA3AF;margin-top:3px;">'
        f'Prob {prob_str} · {adj_str}'
        f'</div>'
        f'</div>'
    )


def _consensus_badge_html(std_dev: float) -> str:
    """
    Return consensus-width badge HTML based on std_dev of vig-free probs across books.

    Thresholds (probability units, 0–1 scale):
        < 0.02  → TIGHT   (green)  — books agree, high confidence
        0.02–0.04 → MODERATE (amber) — normal spread
        > 0.04  → WIDE    (red)   — books disagree, one outlier may be the edge source

    Returns empty string when std_dev == 0.0 (unknown / not captured).

    Note: High std_dev does NOT mean the bet is bad — it often means one book disagrees
    and that book IS the source of the edge (R&D Session 15 validated). Badge is
    informational only. Zero score impact.
    """
    if std_dev <= 0.0:
        return ""

    if std_dev < 0.02:
        label, bg, color = "TIGHT", "#14532D", "#86EFAC"      # green
    elif std_dev <= 0.04:
        label, bg, color = "MODERATE", "#78350F", "#FCD34D"   # amber
    else:
        label, bg, color = "WIDE", "#7F1D1D", "#FCA5A5"       # red

    return (
        f'<span style="'
        f'display:inline-block;'
        f'background:{bg};'
        f'color:{color};'
        f'font-size:0.62rem;'
        f'font-weight:700;'
        f'letter-spacing:0.07em;'
        f'padding:2px 6px;'
        f'border-radius:3px;'
        f'margin-left:6px;'
        f'vertical-align:middle;'
        f'">BOOKS: {label}</span>'
    )


def _score_bar_html(score: float, breakdown: dict, accent: str) -> str:
    """
    Mini score decomposition bar.
    Shows: edge / rlm / eff / sit as labelled segments, total score prominent.
    """
    edge_pts = breakdown.get("edge", 0)
    rlm_pts  = breakdown.get("rlm", 0)
    eff_pts  = breakdown.get("efficiency", 0) if "efficiency" in breakdown else breakdown.get("eff", 0)
    sit_pts  = breakdown.get("situational", 0) if "situational" in breakdown else breakdown.get("sit", 0)

    def seg(pts, max_pts, label, color):
        if pts <= 0:
            return ""
        width = max(4, int((pts / 100) * 200))  # pixel width proportional to 100-pt scale
        return (
            f'<div title="{label}: {pts:.0f}pts" style="'
            f'display:inline-block;'
            f'width:{width}px;'
            f'height:6px;'
            f'background:{color};'
            f'margin-right:1px;'
            f'border-radius:2px;'
            f'vertical-align:middle;'
            f'"></div>'
        )

    bar = (
        seg(edge_pts, 40, "Edge",        "#10B981")  # green
        + seg(rlm_pts,  25, "RLM",         "#8B5CF6")  # violet
        + seg(eff_pts,  20, "Efficiency",  "#3B82F6")  # blue
        + seg(sit_pts,  15, "Situational", "#F59E0B")  # amber
    )
    # Empty portion of 100pt bar
    used = edge_pts + rlm_pts + eff_pts + sit_pts
    empty = 100 - used
    if empty > 0:
        empty_w = max(1, int((empty / 100) * 200))
        bar += (
            f'<div style="display:inline-block;width:{empty_w}px;height:6px;'
            f'background:rgba(255,255,255,0.08);margin-right:1px;'
            f'border-radius:2px;vertical-align:middle;"></div>'
        )

    return (
        f'<div style="margin-top:8px;">'
        f'<div style="font-size:0.65rem;color:#9CA3AF;'
        f'letter-spacing:0.06em;text-transform:uppercase;margin-bottom:4px;">'
        f'Sharp Score: {_fmt_score(score)}/100 '
        f'<span style="font-size:0.6rem;color:#6B7280;">'
        f'Edge:{edge_pts:.0f} RLM:{rlm_pts:.0f} Eff:{eff_pts:.0f} Sit:{sit_pts:.0f}'
        f'</span>'
        f'</div>'
        f'<div>{bar}</div>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Main card renderer
# ---------------------------------------------------------------------------

def render_bet_card(bet: BetCandidate, rank: int = 0) -> str:
    """
    Render one BetCandidate as a self-contained HTML card string.

    Args:
        bet:   A BetCandidate with sharp_score, signal, nemesis populated
               (i.e. post-rank_bets() or manually set for testing).
        rank:  Display rank number (1-indexed). 0 = omit rank display.

    Returns:
        HTML string. Safe for st.markdown(..., unsafe_allow_html=True).

    Tier colours:
        NUCLEAR_2.0U  → amber / dark
        STANDARD_1.0U → blue / dark
        LEAN_0.5U     → teal / dark
        PASS          → grey / dark
    """
    # Determine tier — use bet.signal if set (post-rank_bets), else derive
    signal = bet.signal if bet.signal else sharp_to_size(bet.sharp_score, bet.market_type == "prop")
    cfg = _tier_config(signal)

    bg       = cfg["bg"]
    accent   = cfg["accent"]
    text     = cfg["text"]
    border   = cfg["border"]
    bb       = cfg["badge_bg"]
    bt       = cfg["badge_text"]
    tier_lbl = cfg["label"]
    size_lbl = cfg["size_label"]

    # Rank prefix
    rank_html = f'<span style="color:#6B7280;font-size:0.85rem;margin-right:6px;">#{rank}</span>' if rank else ""

    # RLM badge
    rlm_html = _rlm_badge_html(bet.sharp_breakdown)

    # Consensus-width badge
    consensus_badge = _consensus_badge_html(getattr(bet, "std_dev", 0.0))

    # Price display
    price_display = _fmt_price(bet.price)

    # Edge stats row
    edge_html = (
        f'<div style="font-size:0.78rem;color:#9CA3AF;margin-top:6px;">'
        f'Model <span style="color:{text};font-weight:600;">{_fmt_pct(bet.win_prob)}</span>'
        f' vs Market <span style="color:{text};">{_fmt_pct(bet.market_implied)}</span>'
        f' &nbsp;·&nbsp; Edge '
        f'<span style="color:#10B981;font-weight:700;">{_fmt_pct(bet.edge_pct)}</span>'
        f'</div>'
    )

    # Kelly size row
    kelly_html = (
        f'<div style="font-size:0.78rem;color:#9CA3AF;margin-top:3px;">'
        f'Kelly <span style="color:{text};font-weight:600;">{bet.kelly_size:.2f}u</span>'
        f'&nbsp;&nbsp;'
        f'Book <span style="color:#9CA3AF;">{_html.escape(str(bet.book or ""))}</span>'
        f'</div>'
    )

    # Game time (if available)
    time_html = ""
    if bet.commence_time:
        # Parse ISO to a readable format: "2026-02-18T19:10:00Z" → "Feb 18 · 19:10 UTC"
        ct = bet.commence_time
        try:
            parts = ct.replace("Z", "").split("T")
            date_parts = parts[0].split("-")
            months = ["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
            month = months[int(date_parts[1])] if len(date_parts) >= 2 else ""
            day   = date_parts[2] if len(date_parts) >= 3 else ""
            time  = parts[1][:5] if len(parts) >= 2 else ""
            readable = f"{month} {day} · {time} UTC" if month else ct
        except (IndexError, ValueError):
            readable = ct
        time_html = (
            f'<div style="font-size:0.68rem;color:#6B7280;margin-top:5px;">'
            f'🕐 {readable}</div>'
        )

    # Score bar
    score_bar = _score_bar_html(bet.sharp_score, bet.sharp_breakdown, accent)

    # Kill reason banner
    kill_banner = _kill_reason_banner_html(bet.kill_reason, accent)

    # Nemesis block
    nemesis_block = _nemesis_html(bet.nemesis, "#9CA3AF")

    # Simulation (if available)
    sim_html = ""
    if bet.simulation:
        sim = bet.simulation
        sim_html = (
            f'<div style="font-size:0.72rem;color:#9CA3AF;margin-top:6px;">'
            f'Monte Carlo: Cover '
            f'<span style="color:{text};">{sim.cover_probability:.1%}</span>'
            f' &nbsp;·&nbsp; CI [{sim.ci_10:+.1f}, {sim.ci_90:+.1f}]'
            f' &nbsp;·&nbsp; Vol {sim.volatility:.1f}'
            f'</div>'
        )

    # Sport / market badge
    sport_badge = (
        f'<span style="'
        f'font-size:0.62rem;'
        f'color:{accent};'
        f'border:1px solid {accent};'
        f'padding:1px 6px;'
        f'border-radius:3px;'
        f'letter-spacing:0.07em;'
        f'margin-right:6px;'
        f'">{_html.escape(bet.sport)}</span>'
        f'<span style="'
        f'font-size:0.62rem;'
        f'color:#6B7280;'
        f'border:1px solid #374151;'
        f'padding:1px 6px;'
        f'border-radius:3px;'
        f'letter-spacing:0.07em;'
        f'">{_html.escape(bet.market_type).upper()}</span>'
    )

    html = f"""<div style="
        background:{bg};
        border:1px solid {border};
        border-left:4px solid {border};
        border-radius:8px;
        padding:14px 16px;
        margin-bottom:12px;
        font-family: 'IBM Plex Mono', 'Fira Code', monospace;
    ">

      <!-- Header row: rank + tier badge + size -->
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
        <div style="display:flex;align-items:center;">
          {rank_html}
          <span style="
            background:{bb};
            color:{bt};
            font-size:0.68rem;
            font-weight:800;
            letter-spacing:0.1em;
            padding:3px 9px;
            border-radius:4px;
          ">{tier_lbl}</span>
          {rlm_html}
          {consensus_badge}
        </div>
        <span style="
          font-size:0.78rem;
          font-weight:700;
          color:{accent};
        ">{size_lbl}</span>
      </div>

      <!-- Matchup -->
      <div style="font-size:0.72rem;color:#6B7280;margin-bottom:2px;">
        {_html.escape(bet.matchup)}
      </div>

      <!-- Target (main bet line) -->
      <div style="
        font-size:1.05rem;
        font-weight:700;
        color:{text};
        margin-bottom:4px;
        line-height:1.3;
      ">
        {_html.escape(bet.target)}
        <span style="
          font-size:0.88rem;
          font-weight:600;
          color:{accent};
          margin-left:8px;
        ">{price_display}</span>
      </div>

      <!-- Sport / market type badges -->
      <div style="margin-bottom:6px;">{sport_badge}</div>

      <!-- Edge stats -->
      {edge_html}

      <!-- Kelly + book -->
      {kelly_html}

      <!-- Simulation -->
      {sim_html}

      <!-- Score bar -->
      {score_bar}

      <!-- Kill reason banner -->
      {kill_banner}

      <!-- Nemesis -->
      {nemesis_block}

      <!-- Game time -->
      {time_html}

    </div>"""

    return html


# ---------------------------------------------------------------------------
# Slate header / footer (for per-card loop pattern in app.py)
# ---------------------------------------------------------------------------

def render_slate_header(bets: list, title: str = "Today's Slate") -> str:
    """
    Return the slate header HTML (count + tier summary).
    Use with render_bet_card() in a loop + render_slate_footer().
    """
    if not bets:
        return ""

    tier_counts: dict = {}
    for b in bets:
        sig = b.signal or sharp_to_size(b.sharp_score, b.market_type == "prop")
        tier_counts[sig] = tier_counts.get(sig, 0) + 1

    tier_summary_parts = []
    for sig in ["NUCLEAR_2.0U", "STANDARD_1.0U", "LEAN_0.5U"]:
        count = tier_counts.get(sig, 0)
        if count:
            cfg = _tier_config(sig)
            short = sig.split("_")[0]
            tier_summary_parts.append(
                f'<span style="color:{cfg["accent"]};font-weight:700;">'
                f'{count} {short}</span>'
            )

    tier_summary = " &nbsp;·&nbsp; ".join(tier_summary_parts) if tier_summary_parts else "0 bets"

    return (
        f'<div style="'
        f'font-family:\'IBM Plex Mono\',monospace;'
        f'margin-bottom:16px;'
        f'">'
        f'<div style="font-size:1.1rem;font-weight:800;color:#F9FAFB;">{title}</div>'
        f'<div style="font-size:0.75rem;color:#6B7280;margin-top:3px;">'
        f'{len(bets)} bet{"s" if len(bets) != 1 else ""} &nbsp;·&nbsp; '
        f'{tier_summary}'
        f'</div>'
        f'</div>'
    )


def render_slate_footer(bets: list) -> str:
    """Return the total Kelly footer HTML."""
    total_kelly = sum(b.kelly_size for b in bets)
    return (
        f'<div style="'
        f'font-size:0.72rem;color:#6B7280;'
        f'border-top:1px solid #1F2937;'
        f'padding-top:10px;margin-top:4px;'
        f'">'
        f'Total Kelly exposure: '
        f'<span style="color:#D1D5DB;font-weight:600;">{total_kelly:.2f}u</span>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
# Slate renderer
# ---------------------------------------------------------------------------

def render_bet_slate(bets: list, title: str = "Today's Slate") -> str:
    """
    Render a full ranked slate as HTML.
    Includes header with count/tier summary and footer with total Kelly.

    Args:
        bets:  Ranked list from rank_bets(). Already sorted, signal set.
        title: Section heading.

    Returns:
        HTML string.
    """
    if not bets:
        return (
            '<div style="color:#6B7280;font-size:0.9rem;padding:20px 0;">'
            'No bets passed all filters today.'
            '</div>'
        )

    # Tier summary for header
    tier_counts: dict = {}
    for b in bets:
        sig = b.signal or sharp_to_size(b.sharp_score, b.market_type == "prop")
        tier_counts[sig] = tier_counts.get(sig, 0) + 1

    tier_summary_parts = []
    for sig in ["NUCLEAR_2.0U", "STANDARD_1.0U", "LEAN_0.5U"]:
        count = tier_counts.get(sig, 0)
        if count:
            cfg = _tier_config(sig)
            short = sig.split("_")[0]
            tier_summary_parts.append(
                f'<span style="color:{cfg["accent"]};font-weight:700;">'
                f'{count} {short}</span>'
            )

    tier_summary = " &nbsp;·&nbsp; ".join(tier_summary_parts) if tier_summary_parts else "0 bets"

    total_kelly = sum(b.kelly_size for b in bets)

    header = (
        f'<div style="'
        f'font-family:\'IBM Plex Mono\',monospace;'
        f'margin-bottom:16px;'
        f'">'
        f'<div style="font-size:1.1rem;font-weight:800;color:#F9FAFB;">{title}</div>'
        f'<div style="font-size:0.75rem;color:#6B7280;margin-top:3px;">'
        f'{len(bets)} bet{"s" if len(bets) != 1 else ""} &nbsp;·&nbsp; '
        f'{tier_summary}'
        f'</div>'
        f'</div>'
    )

    cards = "\n".join(render_bet_card(bet, rank=i + 1) for i, bet in enumerate(bets))

    footer = (
        f'<div style="'
        f'font-size:0.72rem;color:#6B7280;'
        f'border-top:1px solid #1F2937;'
        f'padding-top:10px;margin-top:4px;'
        f'">'
        f'Total Kelly exposure: '
        f'<span style="color:#D1D5DB;font-weight:600;">{total_kelly:.2f}u</span>'
        f'</div>'
    )

    return header + cards + footer
