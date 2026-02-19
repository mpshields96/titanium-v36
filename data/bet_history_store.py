"""
data/bet_history_store.py — TITANIUM V36.1
===========================================
Supabase persistence layer for bet history.
All database I/O lives here. app.py calls these functions — never touches Supabase directly.

Responsibilities:
- Insert a bet record when user clicks "Track Bet"
- Fetch bet history for display
- Update outcome + pnl_units when user marks result
- Compute P&L summary (total tracked, win rate, net units)

NOT responsible for:
- UI rendering
- Edge calculation
- Kelly sizing
"""

from __future__ import annotations

from typing import Optional
import streamlit as st


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def _client():
    """Return a Supabase client using credentials from st.secrets."""
    try:
        from supabase import create_client
    except ImportError:
        raise ImportError(
            "supabase-py not installed. Add 'supabase' to requirements.txt."
        )

    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")

    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_KEY must be set in .streamlit/secrets.toml"
        )

    return create_client(url, key)


def is_configured() -> bool:
    """Return True if Supabase credentials are present in secrets."""
    url = st.secrets.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "")
    return bool(url and key)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def insert_bet(
    sport: str,
    matchup: str,
    market_type: str,
    target: str,
    line: float,
    price: int,
    edge_pct: float,
    sharp_score: int,
    signal: str,
    kelly_size: float,
) -> dict:
    """
    Insert a new pending bet record.
    Returns the inserted row dict on success, raises on error.
    """
    row = {
        "sport": sport,
        "matchup": matchup,
        "market_type": market_type,
        "target": target,
        "line": line,
        "price": price,
        "edge_pct": round(edge_pct, 4),
        "sharp_score": int(sharp_score),
        "signal": signal,
        "kelly_size": round(kelly_size, 3),
        "outcome": None,
        "pnl_units": None,
        "notes": None,
    }
    response = _client().table("bet_history").insert(row).execute()
    return response.data[0]


def update_outcome(bet_id: str, outcome: str, pnl_units: float) -> dict:
    """
    Set outcome (WIN/LOSS/PUSH) and P&L on an existing bet record.
    Returns updated row dict.
    """
    if outcome not in ("WIN", "LOSS", "PUSH"):
        raise ValueError(f"Invalid outcome '{outcome}'. Must be WIN, LOSS, or PUSH.")

    response = (
        _client()
        .table("bet_history")
        .update({"outcome": outcome, "pnl_units": round(pnl_units, 3)})
        .eq("id", bet_id)
        .execute()
    )
    return response.data[0]


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def fetch_bets(limit: int = 100, sport: Optional[str] = None) -> list[dict]:
    """
    Fetch bet history, newest first.
    Optionally filter by sport.
    Returns list of row dicts.
    """
    query = (
        _client()
        .table("bet_history")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if sport:
        query = query.eq("sport", sport)

    response = query.execute()
    return response.data


def fetch_pending_bets() -> list[dict]:
    """Return all bets with outcome = null (not yet resolved)."""
    response = (
        _client()
        .table("bet_history")
        .select("*")
        .is_("outcome", "null")
        .order("created_at", desc=True)
        .execute()
    )
    return response.data


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def compute_pnl_summary(bets: list[dict]) -> dict:
    """
    Compute P&L summary from a list of bet row dicts.
    Returns:
      total_tracked    int    — all bets including pending
      resolved         int    — WIN + LOSS + PUSH
      wins             int
      losses           int
      pushes           int
      win_rate         float  — wins / (wins + losses), 0 if none
      net_units        float  — sum of pnl_units on resolved bets
    """
    resolved = [b for b in bets if b.get("outcome") in ("WIN", "LOSS", "PUSH")]
    wins     = sum(1 for b in resolved if b["outcome"] == "WIN")
    losses   = sum(1 for b in resolved if b["outcome"] == "LOSS")
    pushes   = sum(1 for b in resolved if b["outcome"] == "PUSH")
    net      = sum(b["pnl_units"] or 0.0 for b in resolved)

    win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0.0

    return {
        "total_tracked": len(bets),
        "resolved": len(resolved),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "win_rate": round(win_rate, 3),
        "net_units": round(net, 2),
    }
