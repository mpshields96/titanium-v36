"""
odds_comparator.py — TITANIUM V36.1
=====================================
Data layer for the Odds Comparison page (UI 2).
Promoted from R&D core/odds_comparator.py (Session 21).

Single public function:
    build_odds_comparison(game: dict) -> dict

Pure transformation — no API calls. Input is a raw game dict already fetched
by fetch_game_lines(). Output is a structured dict ready for Streamlit display.

Design decisions:
- All books are captured (not just preferred). The whole point of an odds
  comparison view is to see every available book side-by-side.
- Spread lines: only the home side's point value is stored per book. The away
  side is always the mirror (-point). This avoids half-point inconsistencies
  across books creating false "different lines" — we flag when they diverge.
- Totals: only "Over" line stored per book; "Under" is always the mirror.
- If a book doesn't offer a market, its entry for that market is None.
- Prices are stored as raw American integers (matching the rest of the pipeline).

NOTE: _BOOK_PREFERENCE mirrors odds_fetcher.PREFERRED_BOOKS. If Pinnacle or
other books are ever added to PREFERRED_BOOKS in odds_fetcher.py, update this
list to match.

Output shape:
{
  "event_id":  str,
  "matchup":   str,             # "Away @ Home"
  "home_team": str,
  "away_team": str,
  "books":     list[str],       # all book keys present, preference-sorted
  "markets": {
    "h2h": {
      "home": {book_key: price_int | None, ...},
      "away": {book_key: price_int | None, ...},
    },
    "spreads": {
      "home": {book_key: {"line": float | None, "price": int | None}, ...},
      "away": {book_key: {"line": float | None, "price": int | None}, ...},
      "line_consensus": float | None,   # modal home spread line across books
      "line_split": bool,               # True if books disagree on the number
    },
    "totals": {
      "over":  {book_key: {"line": float | None, "price": int | None}, ...},
      "under": {book_key: {"line": float | None, "price": int | None}, ...},
      "line_consensus": float | None,
      "line_split": bool,
    },
  },
  "best_price": {               # best available price per side/market
    "h2h_home": {"book": str, "price": int} | None,
    "h2h_away": {"book": str, "price": int} | None,
    "spread_home": {"book": str, "price": int} | None,
    "spread_away": {"book": str, "price": int} | None,
    "total_over":  {"book": str, "price": int} | None,
    "total_under": {"book": str, "price": int} | None,
  },
}
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Preference order — mirrors odds_fetcher.PREFERRED_BOOKS (no import to avoid
# circular dependency risk). Keep in sync if PREFERRED_BOOKS changes.
# ---------------------------------------------------------------------------

_BOOK_PREFERENCE = ["draftkings", "fanduel", "betmgm", "betrivers", "caesars"]


def _sort_books(keys: list[str]) -> list[str]:
    """Sort book keys: preferred books first (in order), then alphabetical."""
    preferred = [k for k in _BOOK_PREFERENCE if k in keys]
    others = sorted(k for k in keys if k not in _BOOK_PREFERENCE)
    return preferred + others


def _best_price(book_price_map: dict[str, int | None]) -> dict | None:
    """
    Return {"book": key, "price": int} for the best (highest) American odds
    available across books. Higher = better for the bettor.
    Returns None if no prices available.
    """
    candidates = [(book, price) for book, price in book_price_map.items()
                  if price is not None]
    if not candidates:
        return None
    best_book, best_price_val = max(candidates, key=lambda x: x[1])
    return {"book": best_book, "price": best_price_val}


def _modal_line(lines: list[float]) -> tuple[float | None, bool]:
    """
    Return (most_common_line, split_flag).
    split_flag=True when books disagree on the number (e.g. -6.5 vs -7).
    """
    if not lines:
        return None, False
    counts: dict[float, int] = {}
    for line in lines:
        counts[line] = counts.get(line, 0) + 1
    modal = max(counts, key=lambda k: counts[k])
    split = len(counts) > 1
    return modal, split


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_odds_comparison(game: dict) -> dict:
    """
    Transform a raw Odds API game dict into a structured odds comparison dict.

    Args:
        game: One element from the list returned by fetch_game_lines().
              Must have keys: id, home_team, away_team, bookmakers.

    Returns:
        Structured comparison dict (see module docstring for full shape).
        Empty markets are included with None prices — never omitted.
    """
    event_id  = game.get("id", "")
    home_team = game.get("home_team", "")
    away_team = game.get("away_team", "")
    matchup   = f"{away_team} @ {home_team}"

    bookmakers    = game.get("bookmakers", [])
    all_book_keys = _sort_books([b["key"] for b in bookmakers if b.get("key")])
    book_map      = {b["key"]: b for b in bookmakers}

    # --- h2h ---
    h2h_home: dict[str, int | None] = {k: None for k in all_book_keys}
    h2h_away: dict[str, int | None] = {k: None for k in all_book_keys}

    for key in all_book_keys:
        book = book_map[key]
        for market in book.get("markets", []):
            if market.get("key") != "h2h":
                continue
            for outcome in market.get("outcomes", []):
                name  = outcome.get("name")
                price = outcome.get("price")
                if not isinstance(price, int):
                    continue
                if name == home_team:
                    h2h_home[key] = price
                elif name == away_team:
                    h2h_away[key] = price

    # --- spreads ---
    spread_home: dict[str, dict] = {k: {"line": None, "price": None} for k in all_book_keys}
    spread_away: dict[str, dict] = {k: {"line": None, "price": None} for k in all_book_keys}
    spread_home_lines: list[float] = []

    for key in all_book_keys:
        book = book_map[key]
        for market in book.get("markets", []):
            if market.get("key") != "spreads":
                continue
            for outcome in market.get("outcomes", []):
                name  = outcome.get("name")
                price = outcome.get("price")
                point = outcome.get("point")
                if not isinstance(price, int):
                    continue
                if name == home_team and point is not None:
                    spread_home[key] = {"line": float(point), "price": price}
                    spread_home_lines.append(float(point))
                elif name == away_team and point is not None:
                    spread_away[key] = {"line": float(point), "price": price}

    spread_consensus, spread_split = _modal_line(spread_home_lines)

    # --- totals ---
    total_over:  dict[str, dict] = {k: {"line": None, "price": None} for k in all_book_keys}
    total_under: dict[str, dict] = {k: {"line": None, "price": None} for k in all_book_keys}
    total_lines: list[float] = []

    for key in all_book_keys:
        book = book_map[key]
        for market in book.get("markets", []):
            if market.get("key") != "totals":
                continue
            for outcome in market.get("outcomes", []):
                name  = outcome.get("name")
                price = outcome.get("price")
                point = outcome.get("point")
                if not isinstance(price, int):
                    continue
                if name == "Over" and point is not None:
                    total_over[key]  = {"line": float(point), "price": price}
                    total_lines.append(float(point))
                elif name == "Under" and point is not None:
                    total_under[key] = {"line": float(point), "price": price}

    total_consensus, total_split = _modal_line(total_lines)

    # --- best prices ---
    best_price = {
        "h2h_home":    _best_price(h2h_home),
        "h2h_away":    _best_price(h2h_away),
        "spread_home": _best_price({k: v["price"] for k, v in spread_home.items()}),
        "spread_away": _best_price({k: v["price"] for k, v in spread_away.items()}),
        "total_over":  _best_price({k: v["price"] for k, v in total_over.items()}),
        "total_under": _best_price({k: v["price"] for k, v in total_under.items()}),
    }

    return {
        "event_id":  event_id,
        "matchup":   matchup,
        "home_team": home_team,
        "away_team": away_team,
        "books":     all_book_keys,
        "markets": {
            "h2h": {
                "home": h2h_home,
                "away": h2h_away,
            },
            "spreads": {
                "home":           spread_home,
                "away":           spread_away,
                "line_consensus": spread_consensus,
                "line_split":     spread_split,
            },
            "totals": {
                "over":           total_over,
                "under":          total_under,
                "line_consensus": total_consensus,
                "line_split":     total_split,
            },
        },
        "best_price": best_price,
    }


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def to_dataframes(comp: dict) -> tuple:
    """
    Convert a build_odds_comparison() result into three display-ready row lists.
    No pandas dependency — returns plain list-of-dicts. Wrap in pd.DataFrame()
    or pass directly to st.table() in Streamlit.

    Returns:
        (h2h_rows, spread_rows, total_rows)

    Each is a list of row dicts, one row per book:
        h2h_rows:    [{"Book": key, home_team: price_str, away_team: price_str}, ...]
        spread_rows: [{"Book": key, "Home Line": line, "Home": price_str,
                       "Away Line": line, "Away": price_str}, ...]
        total_rows:  [{"Book": key, "O/U": line, "Over": price_str, "Under": price_str}, ...]
    """
    books = comp["books"]
    home  = comp["home_team"]
    away  = comp["away_team"]
    mkts  = comp["markets"]

    h2h_rows = []
    for b in books:
        h2h_rows.append({
            "Book": b,
            home:   _fmt_price(mkts["h2h"]["home"].get(b)),
            away:   _fmt_price(mkts["h2h"]["away"].get(b)),
        })

    spread_rows = []
    for b in books:
        sh = mkts["spreads"]["home"].get(b, {})
        sa = mkts["spreads"]["away"].get(b, {})
        spread_rows.append({
            "Book":       b,
            "Home Line":  sh.get("line"),
            "Home":       _fmt_price(sh.get("price")),
            "Away Line":  sa.get("line"),
            "Away":       _fmt_price(sa.get("price")),
        })

    total_rows = []
    for b in books:
        ov   = mkts["totals"]["over"].get(b, {})
        un   = mkts["totals"]["under"].get(b, {})
        line = ov.get("line") or un.get("line")
        total_rows.append({
            "Book":  b,
            "O/U":   line,
            "Over":  _fmt_price(ov.get("price")),
            "Under": _fmt_price(un.get("price")),
        })

    return h2h_rows, spread_rows, total_rows


def _fmt_price(price: int | None) -> str:
    """Format American odds with explicit sign. None → '—'."""
    if price is None:
        return "—"
    return f"+{price}" if price >= 0 else str(price)
