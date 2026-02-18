"""
ncaab_parser.py — TITANIUM V36.1
===================================
NCAAB game line parser. Session 3 deliverable.

Parses raw Odds API NCAAB game data into structured bet opportunities.
Applies odds collar filter. Returns all bets passing collar for pipeline.
Edge logic (KenPom AdjEM, Barttorvik, etc.) is wired in Session 4.

Louisiana rule: NO college player props. Game lines (spreads/totals/ML) are fine.
"""

from dataclasses import dataclass
from typing import Optional

from edge_calculator import passes_collar, _implied_probability as implied_probability, no_vig_probability
from odds_fetcher import fetch_game_lines, preferred_book, all_books, get_quota_status


@dataclass
class NCAABBetOpportunity:
    matchup: str
    home_team: str
    away_team: str
    bet_type: str           # "spread", "total", "moneyline"
    team: str               # Which team/side (e.g. "Duke Blue Devils" or "Over")
    line: Optional[float]   # Point value (spread or total); None for moneylines
    odds: int               # American odds (best price found across all books)
    implied_prob: float     # Raw implied probability (vig-inclusive)
    fair_prob: float        # Vig-free probability for this side
    book: str               # Name of book offering best price
    event_id: str
    commence_time: str


def parse_ncaab_games(raw_games: list) -> list[NCAABBetOpportunity]:
    """
    Parse raw NCAAB games from Odds API into bet opportunities.

    Applies:
    - Odds collar: -180 to +150 (rejects extreme lines)
    - Extracts all three market types: spread, total, moneyline
    - Uses best available price across all books for each side
    - Computes vig-free fair probability from the best-price book pair

    Does NOT apply edge calculation or minimum edge filter —
    that happens in edge_calculator.parse_game_markets() (Session 4).

    Args:
        raw_games: List of game dicts from fetch_game_lines("basketball_ncaab").

    Returns:
        List of NCAABBetOpportunity objects where odds pass the collar.
    """
    opportunities = []

    for game in raw_games:
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        matchup = f"{away} @ {home}"
        event_id = game.get("id", "")
        commence_time = game.get("commence_time", "")
        bookmakers = game.get("bookmakers", [])

        if not bookmakers:
            continue

        # Sort all books by preference order (DraftKings first, etc.)
        sorted_books = all_books(bookmakers)

        # -----------------------------------------------------------------
        # Spreads — one opportunity per team side
        # -----------------------------------------------------------------
        for team_name in [home, away]:
            best_price = None
            best_line = None
            best_book = ""
            opp_price = None

            for book in sorted_books:
                mmap = {m["key"]: m for m in book.get("markets", [])}
                if "spreads" not in mmap:
                    continue
                outcomes = mmap["spreads"].get("outcomes", [])
                if len(outcomes) != 2:
                    continue

                target = next((o for o in outcomes if o.get("name") == team_name), None)
                other = next((o for o in outcomes if o.get("name") != team_name), None)
                if not target or not other:
                    continue

                price = target.get("price", 0)
                line = target.get("point", 0.0)
                if not passes_collar(price):
                    continue

                # Highest price (most favourable for bettor) wins
                if best_price is None or price > best_price:
                    best_price = price
                    best_line = line
                    best_book = book.get("title", book.get("key", ""))
                    opp_price = other.get("price", 0)

            if best_price is not None and opp_price is not None:
                fair, _ = no_vig_probability(best_price, opp_price)
                opportunities.append(NCAABBetOpportunity(
                    matchup=matchup,
                    home_team=home,
                    away_team=away,
                    bet_type="spread",
                    team=team_name,
                    line=best_line,
                    odds=best_price,
                    implied_prob=implied_probability(best_price),
                    fair_prob=fair,
                    book=best_book,
                    event_id=event_id,
                    commence_time=commence_time,
                ))

        # -----------------------------------------------------------------
        # Moneylines — one opportunity per team side
        # -----------------------------------------------------------------
        for team_name in [home, away]:
            best_price = None
            best_book = ""
            opp_price = None

            for book in sorted_books:
                mmap = {m["key"]: m for m in book.get("markets", [])}
                if "h2h" not in mmap:
                    continue
                outcomes = mmap["h2h"].get("outcomes", [])
                if len(outcomes) != 2:
                    continue

                target = next((o for o in outcomes if o.get("name") == team_name), None)
                other = next((o for o in outcomes if o.get("name") != team_name), None)
                if not target or not other:
                    continue

                price = target.get("price", 0)
                if not passes_collar(price):
                    continue

                if best_price is None or price > best_price:
                    best_price = price
                    best_book = book.get("title", book.get("key", ""))
                    opp_price = other.get("price", 0)

            if best_price is not None and opp_price is not None:
                fair, _ = no_vig_probability(best_price, opp_price)
                opportunities.append(NCAABBetOpportunity(
                    matchup=matchup,
                    home_team=home,
                    away_team=away,
                    bet_type="moneyline",
                    team=team_name,
                    line=None,
                    odds=best_price,
                    implied_prob=implied_probability(best_price),
                    fair_prob=fair,
                    book=best_book,
                    event_id=event_id,
                    commence_time=commence_time,
                ))

        # -----------------------------------------------------------------
        # Totals — Over and Under separately
        # -----------------------------------------------------------------
        for side in ["Over", "Under"]:
            best_price = None
            best_line = None
            best_book = ""
            opp_price = None

            for book in sorted_books:
                mmap = {m["key"]: m for m in book.get("markets", [])}
                if "totals" not in mmap:
                    continue
                outcomes = mmap["totals"].get("outcomes", [])
                if len(outcomes) != 2:
                    continue

                target = next((o for o in outcomes if o.get("name") == side), None)
                other = next((o for o in outcomes if o.get("name") != side), None)
                if not target or not other:
                    continue

                price = target.get("price", 0)
                line = target.get("point", 0.0)
                if not passes_collar(price):
                    continue

                if best_price is None or price > best_price:
                    best_price = price
                    best_line = line
                    best_book = book.get("title", book.get("key", ""))
                    opp_price = other.get("price", 0)

            if best_price is not None and opp_price is not None:
                fair, _ = no_vig_probability(best_price, opp_price)
                opportunities.append(NCAABBetOpportunity(
                    matchup=matchup,
                    home_team=home,
                    away_team=away,
                    bet_type="total",
                    team=side,
                    line=best_line,
                    odds=best_price,
                    implied_prob=implied_probability(best_price),
                    fair_prob=fair,
                    book=best_book,
                    event_id=event_id,
                    commence_time=commence_time,
                ))

    return opportunities


# ---------------------------------------------------------------------------
# Session 3 pipeline test — run directly to validate end-to-end
# ---------------------------------------------------------------------------

def run_pipeline_test() -> None:
    """
    Session 3 pipeline test:
    1. Fetch live NCAAB data (1 API call)
    2. Parse through collar filter
    3. Print: games fetched, bets passing collar, breakdown by type, sample rows
    """
    print("=" * 60)
    print("NCAAB PIPELINE TEST — SESSION 3")
    print("=" * 60)

    print("\nFetching live NCAAB data...")
    raw_games = fetch_game_lines("basketball_ncaab")
    print(f"Games fetched: {len(raw_games)}")

    if not raw_games:
        print("No games found. Check API key or season dates.")
        return

    # Count raw market outcomes via single preferred book (for reference)
    total_outcomes = 0
    for game in raw_games:
        book = preferred_book(game.get("bookmakers", []))
        if not book:
            continue
        for market in book.get("markets", []):
            total_outcomes += len(market.get("outcomes", []))

    # Parse with collar filter applied
    opportunities = parse_ncaab_games(raw_games)

    # Breakdown by market type
    by_type: dict[str, int] = {}
    for opp in opportunities:
        by_type[opp.bet_type] = by_type.get(opp.bet_type, 0) + 1

    print(f"\nTotal raw market outcomes (preferred book): {total_outcomes}")
    print(f"Bets passing collar (-180 to +150):        {len(opportunities)}")
    print(f"\nBreakdown by type:")
    for bt, count in sorted(by_type.items()):
        print(f"  {bt.upper():12s}: {count}")

    print(f"\nSample opportunities (first 10):")
    hdr = f"  {'Matchup':<40} {'Type':<10} {'Team/Side':<30} {'Line':>6} {'Odds':>6} {'Implied':>8} {'Fair':>8}"
    print(hdr)
    print(f"  {'-'*40} {'-'*10} {'-'*30} {'-'*6} {'-'*6} {'-'*8} {'-'*8}")
    for opp in opportunities[:10]:
        line_str = f"{opp.line:+.1f}" if opp.line is not None else "  N/A"
        print(
            f"  {opp.matchup[:40]:<40} {opp.bet_type:<10} "
            f"{opp.team[:30]:<30} {line_str:>6} {opp.odds:>+6d} "
            f"{opp.implied_prob:>7.1%} {opp.fair_prob:>7.1%}"
        )

    print(f"\n{get_quota_status()}")
    print("\nncaab_parser DONE — collar filter working. Edge logic next in Session 4.")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline_test()
