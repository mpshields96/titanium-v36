"""
bet_ranker.py — TITANIUM V36.1
=================================
Diversity engine and final bet selection logic. No API calls, no math, no UI.

Responsibilities:
- Remove duplicate markets (never both sides of the same bet)
- Rank all passing bets by edge % descending
- Apply sport diversity rules so one sport doesn't dominate the slate
- Return the top 10 bets maximum for display

NON-NEGOTIABLE RULES ENFORCED HERE:
- No duplicate markets: if Patriots -3 appears, Seahawks +3 is dropped
- Maximum 10 bets returned regardless of how many pass the edge filter

DO NOT add API calls, betting math, or Streamlit calls to this file.
"""


def rank_bets(bet_candidates: list) -> list:
    """
    Main entry point called by app.py.
    Takes all bets that passed edge_calculator, deduplicates markets,
    ranks by edge %, and returns the top 10.

    Args:
        bet_candidates: List of bet dicts from edge_calculator.calculate_edges().
            Each dict has: {matchup, type, target, line, price, edge_pct,
                            win_prob, kelly_size, signal, sport}

    Returns:
        List of up to 10 bet dicts, sorted by edge_pct descending.
        Suitable for direct display as a Streamlit dataframe.
    """
    # TODO Session 4: Implement full ranking pipeline
    pass


def _deduplicate_markets(bets: list) -> list:
    """
    Remove one side of any bet where both sides of the same market appear.
    Rule: keep the side with the higher edge_pct. Drop the other.

    Example: If Patriots -3 (edge 4.2%) and Seahawks +3 (edge 3.8%) both pass,
    keep Patriots -3 and drop Seahawks +3.

    Args:
        bets: List of bet dicts, potentially containing both sides of markets.

    Returns:
        List of bet dicts with no duplicate markets.
    """
    # TODO Session 4: Implement
    pass


def _apply_diversity(bets: list, max_per_sport: int = 4) -> list:
    """
    Ensure no single sport dominates the final output.
    After deduplication and ranking, cap each sport at max_per_sport entries.

    Args:
        bets: Deduplicated, ranked list of bet dicts.
        max_per_sport: Maximum bets from any single sport (default 4).

    Returns:
        Filtered list respecting per-sport cap.
    """
    # TODO Session 4: Implement
    pass
