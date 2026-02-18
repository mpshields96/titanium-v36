"""
app.py — TITANIUM V36.1
========================
Streamlit UI ONLY. No business logic lives here.

Responsibilities:
- Render sidebar sport selector
- Render EXECUTE button
- Call odds_fetcher, edge_calculator, bet_ranker in sequence
- Display the final ranked bet table

DO NOT add API calls, math, or betting logic to this file.
"""

import streamlit as st


def main():
    st.set_page_config(page_title="TITANIUM V36.1", layout="wide")
    st.title("TITANIUM V36.1")
    st.caption("Sports Betting Analysis Tool")

    # Sidebar — sport selector
    sport = st.sidebar.selectbox(
        "Select Sport",
        ["NBA", "NFL", "NCAAB", "NHL", "Soccer"],
    )

    # Execute button
    if st.sidebar.button("EXECUTE"):
        st.info(f"Running analysis for {sport}... (logic not yet implemented)")

        # TODO Session 2+: Wire up the pipeline:
        # raw_odds = odds_fetcher.fetch_batch_odds(sport)
        # edges = edge_calculator.calculate_edges(raw_odds, sport)
        # ranked = bet_ranker.rank_bets(edges)
        # st.dataframe(ranked)


if __name__ == "__main__":
    main()
