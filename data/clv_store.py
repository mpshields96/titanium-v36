"""
data/clv_store.py — TITANIUM V36.1
====================================
Supabase persistence layer for Closing Line Value (CLV) tracking.

CLV = implied_prob(open_price) - implied_prob(closing_price)
Positive average CLV = empirical proof the edge detection method works.

Architecture:
- record_clv_open()   — called at Track Bet time; stores open_price = bet.price
- update_clv_close()  — called when closing price is available; computes + stores clv_pct
- fetch_clv_for_events() — batch fetch CLV rows for a list of event_ids
- get_clv_summary()   — aggregate stats across all resolved CLV rows
- is_configured()     — True if Supabase credentials present

Table: clv_history
  id            uuid  PK auto
  event_id      text  NOT NULL
  target        text  NOT NULL  (team name, "Over", "Under")
  market_type   text  NOT NULL  (h2h, spreads, totals)
  sport         text
  matchup       text
  open_price    int   NOT NULL  (American odds at bet-entry time = bet.price)
  closing_price int             (filled when game closes)
  open_implied  float           (derived from open_price)
  closing_implied float         (derived from closing_price)
  clv_pct       float           (percentage points; positive = good)
  recorded_at   timestamptz     DEFAULT now()

Design notes:
- UNIQUE(event_id, target, market_type): one CLV row per bet side + market.
  Prevents duplicate entries if Track Bet is clicked multiple times.
- open_price = bet.price at track time — NOT get_open_price(event_id).
  R&D Session 22 confirmed get_open_price() has a team-name key collision:
  _extract_open_prices() iterates all markets, last write wins. A team appearing
  in both h2h AND spreads will have h2h price overwritten by spreads price.
  bet.price is always the correct market-type price — use it exclusively.
- closing_price is filled externally (future feature: pipeline re-check at game time).
  Until then, CLV column shows '—' in Bet History until closing_price is recorded.
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
# Math (pure)
# ---------------------------------------------------------------------------

def _implied(american: int) -> float:
    """American odds → raw implied probability (no vig removal)."""
    if american < 0:
        return abs(american) / (abs(american) + 100)
    if american == 0:
        return 0.5
    return 100 / (american + 100)


def _compute_clv_pct(open_price: int, closing_price: int) -> float:
    """
    CLV in percentage points.
    Positive = we got a better price than market close (good).
    Negative = market moved against us (we paid too much).
    """
    return round((_implied(open_price) - _implied(closing_price)) * 100, 4)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def record_clv_open(
    event_id: str,
    target: str,
    market_type: str,
    open_price: int,
    sport: str = "",
    matchup: str = "",
) -> Optional[dict]:
    """
    Record the open price at bet-entry time.

    Call this immediately after insert_bet() in app.py.
    open_price MUST be bet.price — not get_open_price() (key collision risk).

    Returns inserted row dict, or None on conflict (duplicate tracking).
    """
    row = {
        "event_id": event_id,
        "target": target,
        "market_type": market_type,
        "sport": sport,
        "matchup": matchup,
        "open_price": open_price,
        "open_implied": round(_implied(open_price) * 100, 4),
    }
    response = (
        _client()
        .table("clv_history")
        .upsert(row, on_conflict="event_id,target,market_type", ignore_duplicates=True)
        .execute()
    )
    return response.data[0] if response.data else None


def update_clv_close(
    event_id: str,
    target: str,
    market_type: str,
    closing_price: int,
) -> Optional[dict]:
    """
    Fill the closing price and compute clv_pct on an existing CLV row.
    Call this when closing odds are available (future pipeline feature).
    Returns updated row dict, or None if row not found.
    """
    # Fetch the existing row to get open_price
    response = (
        _client()
        .table("clv_history")
        .select("id,open_price")
        .eq("event_id", event_id)
        .eq("target", target)
        .eq("market_type", market_type)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None

    row = response.data[0]
    open_price = row["open_price"]
    clv_pct = _compute_clv_pct(open_price, closing_price)
    closing_implied = round(_implied(closing_price) * 100, 4)

    update_response = (
        _client()
        .table("clv_history")
        .update({
            "closing_price": closing_price,
            "closing_implied": closing_implied,
            "clv_pct": clv_pct,
        })
        .eq("id", row["id"])
        .execute()
    )
    return update_response.data[0] if update_response.data else None


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def fetch_clv_for_events(event_ids: list[str]) -> dict[str, dict]:
    """
    Batch fetch CLV rows for a list of event_ids.
    Returns dict keyed by (event_id, target, market_type) tuple → row dict.
    Efficient for Bet History page — one query for all displayed rows.
    """
    if not event_ids:
        return {}

    response = (
        _client()
        .table("clv_history")
        .select("*")
        .in_("event_id", event_ids)
        .execute()
    )
    result = {}
    for row in (response.data or []):
        key = (row["event_id"], row["target"], row["market_type"])
        result[key] = row
    return result


def get_clv_summary() -> dict:
    """
    Aggregate CLV stats across all rows with a resolved clv_pct.
    Returns:
      n             int   — entries with closing price
      avg_clv_pct   float — mean CLV in percentage points
      positive_rate float — fraction with CLV > 0
      verdict       str   — EDGE CONFIRMED / MARGINAL / NO EDGE DETECTED / INSUFFICIENT DATA
    """
    response = (
        _client()
        .table("clv_history")
        .select("clv_pct")
        .not_.is_("clv_pct", "null")
        .execute()
    )
    rows = response.data or []
    clvs = [r["clv_pct"] for r in rows if r.get("clv_pct") is not None]
    n = len(clvs)

    if n == 0:
        return {
            "n": 0,
            "avg_clv_pct": 0.0,
            "positive_rate": 0.0,
            "verdict": "INSUFFICIENT DATA",
        }

    avg = sum(clvs) / n
    pos_rate = sum(1 for c in clvs if c > 0) / n

    if avg >= 1.5 and pos_rate >= 0.55:
        verdict = "EDGE CONFIRMED"
    elif avg >= 0.5 and pos_rate >= 0.50:
        verdict = "MARGINAL"
    else:
        verdict = "NO EDGE DETECTED"

    return {
        "n": n,
        "avg_clv_pct": round(avg, 3),
        "positive_rate": round(pos_rate, 3),
        "verdict": verdict,
    }
