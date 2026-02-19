"""
tests/test_clv_store.py — TITANIUM V36.1
==========================================
Tests for data/clv_store.py (CLV Supabase persistence layer).

All Supabase I/O is mocked — no real DB calls, zero credentials required.
Tests cover:
  - is_configured() with and without secrets
  - _implied() and _compute_clv_pct() pure math
  - record_clv_open() writes correct row, handles duplicate gracefully
  - update_clv_close() fetches open_price, computes clv_pct, writes update
  - fetch_clv_for_events() returns keyed dict
  - get_clv_summary() aggregates correctly and applies verdict thresholds

Run with: pytest tests/test_clv_store.py -v
"""

import sys
import os
from unittest.mock import patch, MagicMock, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_st_secrets(configured: bool = True):
    secrets = MagicMock()
    if configured:
        secrets.get = lambda key, default="": (
            "https://fake.supabase.co" if key == "SUPABASE_URL" else "fake-key"
        )
    else:
        secrets.get = lambda key, default="": default
    return patch("streamlit.secrets", secrets)


def _make_mock_client():
    """Return a mock Supabase client + the table mock for assertions."""
    mock_response = MagicMock()
    mock_response.data = []

    mock_table = MagicMock()
    mock_table.upsert.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.in_.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.not_ = mock_table
    mock_table.is_.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.execute.return_value = mock_response

    mock_client = MagicMock()
    mock_client.table.return_value = mock_table
    return mock_client, mock_table, mock_response


# ---------------------------------------------------------------------------
# is_configured
# ---------------------------------------------------------------------------

class TestIsConfigured:
    def test_returns_true_when_both_secrets_present(self):
        with _mock_st_secrets(configured=True):
            from data.clv_store import is_configured
            assert is_configured() is True

    def test_returns_false_when_secrets_missing(self):
        with _mock_st_secrets(configured=False):
            from data.clv_store import is_configured
            assert is_configured() is False


# ---------------------------------------------------------------------------
# Pure math
# ---------------------------------------------------------------------------

class TestImplied:
    def test_negative_american_odds(self):
        from data.clv_store import _implied
        result = _implied(-110)
        assert abs(result - 110 / 210) < 0.0001

    def test_positive_american_odds(self):
        from data.clv_store import _implied
        result = _implied(110)
        assert abs(result - 100 / 210) < 0.0001

    def test_zero_returns_half(self):
        from data.clv_store import _implied
        assert _implied(0) == 0.5


class TestComputeClvPct:
    def test_positive_clv_line_loosened(self):
        """Open -150, close -120 → market moved against us → positive CLV."""
        from data.clv_store import _compute_clv_pct
        clv = _compute_clv_pct(-150, -120)
        # open_implied(-150) = 0.600, close_implied(-120) = 0.545
        # clv_pct = (0.600 - 0.545) * 100 = ~5.5pp
        assert clv > 0

    def test_negative_clv_line_shortened(self):
        """Open -110, close -130 → market agreed side was cheap → negative CLV."""
        from data.clv_store import _compute_clv_pct
        clv = _compute_clv_pct(-110, -130)
        assert clv < 0

    def test_zero_clv_no_movement(self):
        from data.clv_store import _compute_clv_pct
        assert _compute_clv_pct(-110, -110) == 0.0

    def test_result_is_in_percentage_points(self):
        """Result should be in pp range (e.g. ±10), not raw probability (0.10)."""
        from data.clv_store import _compute_clv_pct
        clv = _compute_clv_pct(-110, -130)
        assert abs(clv) < 20   # sanity: never > 20pp for reasonable odds
        assert abs(clv) > 0.1  # sanity: not a raw 0.0x float


# ---------------------------------------------------------------------------
# record_clv_open
# ---------------------------------------------------------------------------

class TestRecordClvOpen:
    def test_writes_correct_row(self):
        mock_client, mock_table, mock_response = _make_mock_client()
        mock_response.data = [{"id": "uuid-1", "event_id": "e1"}]

        with _mock_st_secrets(configured=True):
            with patch("data.clv_store._client", return_value=mock_client):
                from data.clv_store import record_clv_open
                result = record_clv_open(
                    event_id="e1",
                    target="Boston Celtics",
                    market_type="spreads",
                    open_price=-108,
                    sport="NBA",
                    matchup="Celtics vs Nets",
                )

        mock_table.upsert.assert_called_once()
        upsert_row = mock_table.upsert.call_args[0][0]
        assert upsert_row["event_id"] == "e1"
        assert upsert_row["target"] == "Boston Celtics"
        assert upsert_row["market_type"] == "spreads"
        assert upsert_row["open_price"] == -108
        assert upsert_row["sport"] == "NBA"
        assert "open_implied" in upsert_row
        assert result is not None

    def test_returns_none_on_duplicate_conflict(self):
        """When upsert returns empty data (ignore_duplicates hit), returns None."""
        mock_client, mock_table, mock_response = _make_mock_client()
        mock_response.data = []  # no rows returned = conflict ignored

        with _mock_st_secrets(configured=True):
            with patch("data.clv_store._client", return_value=mock_client):
                from data.clv_store import record_clv_open
                result = record_clv_open("e2", "Over", "totals", -115)

        assert result is None

    def test_open_implied_derived_correctly(self):
        """open_implied stored as percentage (0-100 scale)."""
        mock_client, mock_table, mock_response = _make_mock_client()
        mock_response.data = [{"id": "uuid-2"}]

        with _mock_st_secrets(configured=True):
            with patch("data.clv_store._client", return_value=mock_client):
                from data.clv_store import record_clv_open
                record_clv_open("e3", "Team A", "h2h", -110)

        upsert_row = mock_table.upsert.call_args[0][0]
        # _implied(-110) = 110/210 ≈ 0.5238, × 100 ≈ 52.38
        assert 52 < upsert_row["open_implied"] < 53


# ---------------------------------------------------------------------------
# update_clv_close
# ---------------------------------------------------------------------------

class TestUpdateClvClose:
    def test_fetches_open_price_and_computes_clv(self):
        """update_clv_close reads existing row, computes clv_pct, writes update."""
        mock_client, mock_table, mock_response = _make_mock_client()

        # First call (select): return existing row with open_price
        select_response = MagicMock()
        select_response.data = [{"id": "uuid-99", "open_price": -150}]

        update_response = MagicMock()
        update_response.data = [{"id": "uuid-99", "clv_pct": 5.5}]

        # Chain: select → eq × 3 → limit → execute returns select_response
        # Then update → eq → execute returns update_response
        call_count = {"n": 0}

        def execute_side_effect():
            call_count["n"] += 1
            if call_count["n"] == 1:
                return select_response
            return update_response

        mock_table.execute.side_effect = execute_side_effect

        with _mock_st_secrets(configured=True):
            with patch("data.clv_store._client", return_value=mock_client):
                from data.clv_store import update_clv_close
                result = update_clv_close("e1", "Boston Celtics", "spreads", -120)

        # Two execute() calls: one select, one update
        assert call_count["n"] == 2
        # Update was called with clv_pct
        update_call_data = mock_table.update.call_args[0][0]
        assert "clv_pct" in update_call_data
        assert update_call_data["closing_price"] == -120

    def test_returns_none_when_row_not_found(self):
        """If no existing CLV row, update_clv_close returns None."""
        mock_client, mock_table, mock_response = _make_mock_client()
        mock_response.data = []  # not found

        with _mock_st_secrets(configured=True):
            with patch("data.clv_store._client", return_value=mock_client):
                from data.clv_store import update_clv_close
                result = update_clv_close("missing", "Team X", "h2h", -110)

        assert result is None


# ---------------------------------------------------------------------------
# fetch_clv_for_events
# ---------------------------------------------------------------------------

class TestFetchClvForEvents:
    def test_returns_keyed_dict(self):
        """Results are keyed by (event_id, target, market_type) tuple."""
        mock_client, mock_table, mock_response = _make_mock_client()
        mock_response.data = [
            {"event_id": "e1", "target": "Celtics", "market_type": "spreads", "clv_pct": 2.3},
            {"event_id": "e2", "target": "Over",    "market_type": "totals",  "clv_pct": None},
        ]

        with _mock_st_secrets(configured=True):
            with patch("data.clv_store._client", return_value=mock_client):
                from data.clv_store import fetch_clv_for_events
                result = fetch_clv_for_events(["e1", "e2"])

        assert ("e1", "Celtics", "spreads") in result
        assert ("e2", "Over", "totals") in result
        assert result[("e1", "Celtics", "spreads")]["clv_pct"] == 2.3

    def test_returns_empty_dict_for_empty_input(self):
        mock_client, mock_table, mock_response = _make_mock_client()

        with _mock_st_secrets(configured=True):
            with patch("data.clv_store._client", return_value=mock_client):
                from data.clv_store import fetch_clv_for_events
                result = fetch_clv_for_events([])

        assert result == {}
        mock_table.in_.assert_not_called()


# ---------------------------------------------------------------------------
# get_clv_summary
# ---------------------------------------------------------------------------

class TestGetClvSummary:
    def test_returns_insufficient_data_on_no_rows(self):
        mock_client, mock_table, mock_response = _make_mock_client()
        mock_response.data = []

        with _mock_st_secrets(configured=True):
            with patch("data.clv_store._client", return_value=mock_client):
                from data.clv_store import get_clv_summary
                result = get_clv_summary()

        assert result["n"] == 0
        assert result["verdict"] == "INSUFFICIENT DATA"

    def test_edge_confirmed_verdict(self):
        """avg >= 1.5 AND pos_rate >= 0.55 → EDGE CONFIRMED."""
        mock_client, mock_table, mock_response = _make_mock_client()
        mock_response.data = [
            {"clv_pct": 2.0}, {"clv_pct": 3.0}, {"clv_pct": 1.5},
            {"clv_pct": 1.8}, {"clv_pct": -0.5},
        ]

        with _mock_st_secrets(configured=True):
            with patch("data.clv_store._client", return_value=mock_client):
                from data.clv_store import get_clv_summary
                result = get_clv_summary()

        assert result["verdict"] == "EDGE CONFIRMED"
        assert result["n"] == 5
        assert result["avg_clv_pct"] > 0

    def test_no_edge_verdict(self):
        """Negative avg → NO EDGE DETECTED."""
        mock_client, mock_table, mock_response = _make_mock_client()
        mock_response.data = [
            {"clv_pct": -2.0}, {"clv_pct": -1.5}, {"clv_pct": -0.8},
        ]

        with _mock_st_secrets(configured=True):
            with patch("data.clv_store._client", return_value=mock_client):
                from data.clv_store import get_clv_summary
                result = get_clv_summary()

        assert result["verdict"] == "NO EDGE DETECTED"
        assert result["positive_rate"] == 0.0
