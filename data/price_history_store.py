"""
data/price_history_store.py — TITANIUM V36.1
=============================================
Supabase persistence layer for first-ever-seen open prices (RLM 2.0).

Problem solved:
    The in-session _OPEN_PRICE_CACHE only captures the price at first fetch
    THIS session. If sharp money moved the line at 2am before you opened the
    app at 8am, the cache starts from the already-moved price — the move is
    invisible to RLM.

Solution:
    Write the FIRST-EVER-SEEN price per event_id to Supabase price_history.
    On session start, inject those stored prices into _OPEN_PRICE_CACHE before
    cache_open_prices() runs. The cache then sees the true multi-day baseline.

Wire-in pattern (app.py run_pipeline, before cache_open_prices):
    from data.price_history_store import is_configured, record_new_events, inject_into_cache
    if is_configured():
        record_new_events(raw_games)       # write first-seen prices for new event_ids
        inject_into_cache(raw_games)       # pre-seed _OPEN_PRICE_CACHE with historical prices
    cache_open_prices(raw_games)           # existing call — no change

Supabase table: price_history
    event_id      text  UNIQUE NOT NULL    -- Odds API event ID
    home_price    int   NOT NULL           -- American odds, home team h2h
    away_price    int   NOT NULL           -- American odds, away team h2h
    first_seen_at timestamptz DEFAULT now()
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

def record_new_events(games: list[dict]) -> int:
    """
    For each game in games, write home/away open prices to price_history
    if the event_id has never been seen before.

    The UNIQUE constraint on event_id at the DB level enforces no-overwrite —
    we use INSERT ... ON CONFLICT DO NOTHING so duplicate calls are safe.

    Args:
        games: Raw game dicts from fetch_game_lines(). Must include
               id, home_team, away_team, bookmakers.

    Returns:
        Number of new events written (0 if all already present).
    """
    from odds_fetcher import _extract_open_prices  # deferred — avoids circular import

    rows = []
    for game in games:
        event_id = game.get("id", "")
        if not event_id:
            continue
        prices = _extract_open_prices(game)
        if not prices:
            continue
        rows.append({
            "event_id":   event_id,
            "home_price": int(prices["home"]),
            "away_price": int(prices["away"]),
        })

    if not rows:
        return 0

    # ON CONFLICT DO NOTHING — DB unique constraint enforces no-overwrite
    response = (
        _client()
        .table("price_history")
        .upsert(rows, on_conflict="event_id", ignore_duplicates=True)
        .execute()
    )
    return len(response.data) if response.data else 0


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_historical_open_price(event_id: str) -> Optional[dict[str, int]]:
    """
    Return the stored first-seen prices for an event_id.

    Returns:
        {"home": price, "away": price} if found, None if not seen before.
    """
    response = (
        _client()
        .table("price_history")
        .select("home_price, away_price")
        .eq("event_id", event_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    row = response.data[0]
    return {"home": row["home_price"], "away": row["away_price"]}


def fetch_all_open_prices(event_ids: list[str]) -> dict[str, dict[str, int]]:
    """
    Batch fetch stored open prices for a list of event_ids.

    Returns:
        { event_id: {"home": price, "away": price} } for known events only.
    """
    if not event_ids:
        return {}

    response = (
        _client()
        .table("price_history")
        .select("event_id, home_price, away_price")
        .in_("event_id", event_ids)
        .execute()
    )
    return {
        row["event_id"]: {"home": row["home_price"], "away": row["away_price"]}
        for row in (response.data or [])
    }


# ---------------------------------------------------------------------------
# Cache injection
# ---------------------------------------------------------------------------

def inject_into_cache(games: list[dict]) -> int:
    """
    Pre-seed odds_fetcher._OPEN_PRICE_CACHE with historical open prices.

    Call BEFORE cache_open_prices(). The frozen-first-call semantics of
    _OPEN_PRICE_CACHE mean injected historical prices are protected — a
    subsequent cache_open_prices() call will skip already-cached event_ids.

    This is the key upgrade: compute_rlm() now compares against the
    TRUE multi-day open price, not just the intra-session first fetch.

    Args:
        games: Raw game list (used to enumerate event IDs to look up).

    Returns:
        Number of events injected from Supabase into the session cache.
    """
    from odds_fetcher import _OPEN_PRICE_CACHE  # direct module-level cache injection

    event_ids = [g.get("id", "") for g in games if g.get("id")]
    if not event_ids:
        return 0

    stored = fetch_all_open_prices(event_ids)
    injected = 0

    for event_id, prices in stored.items():
        if event_id not in _OPEN_PRICE_CACHE:
            _OPEN_PRICE_CACHE[event_id] = {
                "home": float(prices["home"]),
                "away": float(prices["away"]),
            }
            injected += 1

    return injected


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

def purge_old_events(days_old: int = 14) -> int:
    """
    Remove price_history rows older than days_old days.
    Prevents unbounded table growth across many sessions.

    Returns: number of rows deleted.
    """
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()

    response = (
        _client()
        .table("price_history")
        .delete()
        .lt("first_seen_at", cutoff)
        .execute()
    )
    return len(response.data) if response.data else 0


def price_history_status() -> str:
    """Return a one-line status string. Used for logging in run_pipeline()."""
    try:
        response = (
            _client()
            .table("price_history")
            .select("event_id", count="exact")
            .execute()
        )
        n = response.count or 0
        return f"price_history: {n} events stored in Supabase"
    except Exception:
        return "price_history: status unavailable"
