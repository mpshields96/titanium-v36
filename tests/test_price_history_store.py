"""
tests/test_price_history_store.py — TITANIUM V36.1
====================================================
Tests for data/price_history_store.py (RLM 2.0 Supabase persistence layer).

All Supabase I/O is mocked — no real DB calls, zero credentials required.
Tests cover:
  - is_configured() with and without secrets
  - record_new_events() writes correct rows, skips games without prices
  - inject_into_cache() pre-seeds _OPEN_PRICE_CACHE, skips already-cached events
  - _extract_open_prices() refactor (called internally)

Run with: pytest tests/test_price_history_store.py -v
"""

import sys
import os
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from odds_fetcher import clear_open_price_cache, _OPEN_PRICE_CACHE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_h2h_game(event_id: str, home: str, away: str,
                   home_price: int, away_price: int) -> dict:
    """Minimal game dict with DraftKings h2h market."""
    return {
        "id": event_id,
        "home_team": home,
        "away_team": away,
        "commence_time": "2026-02-20T23:00:00Z",
        "bookmakers": [
            {
                "key": "draftkings",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": home, "price": home_price},
                            {"name": away, "price": away_price},
                        ],
                    }
                ],
            }
        ],
    }


def _mock_st_secrets(configured: bool = True):
    """
    Return a patch for streamlit.secrets that simulates configured or
    unconfigured Supabase credentials.
    """
    secrets = MagicMock()
    if configured:
        secrets.get = lambda key, default="": (
            "https://fake.supabase.co" if key == "SUPABASE_URL" else "fake-key"
        )
    else:
        secrets.get = lambda key, default="": default
    return patch("streamlit.secrets", secrets)


# ---------------------------------------------------------------------------
# is_configured
# ---------------------------------------------------------------------------

class TestIsConfigured:
    def test_returns_true_when_both_secrets_present(self):
        with _mock_st_secrets(configured=True):
            from data.price_history_store import is_configured
            assert is_configured() is True

    def test_returns_false_when_secrets_missing(self):
        with _mock_st_secrets(configured=False):
            from data.price_history_store import is_configured
            assert is_configured() is False


# ---------------------------------------------------------------------------
# record_new_events
# ---------------------------------------------------------------------------

class TestRecordNewEvents:
    def _make_mock_client(self):
        """Build a mock Supabase client that captures upsert calls."""
        mock_response = MagicMock()
        mock_response.data = [{"event_id": "g1"}, {"event_id": "g2"}]

        mock_table = MagicMock()
        mock_table.upsert.return_value = mock_table
        mock_table.execute.return_value = mock_response

        mock_client = MagicMock()
        mock_client.table.return_value = mock_table
        return mock_client, mock_table

    def test_writes_rows_for_games_with_h2h_prices(self):
        """Games that have h2h prices produce rows written to Supabase."""
        games = [
            _make_h2h_game("g1", "Celtics", "Nets",  -130, 110),
            _make_h2h_game("g2", "Lakers",  "Suns",  -160, 140),
        ]
        mock_client, mock_table = self._make_mock_client()

        with _mock_st_secrets(configured=True):
            with patch("data.price_history_store._client", return_value=mock_client):
                from data.price_history_store import record_new_events
                result = record_new_events(games)

        # Should have upserted 2 rows
        mock_table.upsert.assert_called_once()
        call_args = mock_table.upsert.call_args[0][0]
        assert len(call_args) == 2

        event_ids = {row["event_id"] for row in call_args}
        assert event_ids == {"g1", "g2"}

        # Prices stored as integers
        row_g1 = next(r for r in call_args if r["event_id"] == "g1")
        assert row_g1["home_price"] == -130
        assert row_g1["away_price"] == 110

    def test_skips_games_without_bookmakers(self):
        """Games with empty bookmakers list produce no rows."""
        games = [
            {
                "id": "g3",
                "home_team": "Heat",
                "away_team": "Magic",
                "commence_time": "2026-02-20T23:00:00Z",
                "bookmakers": [],
            }
        ]
        mock_client, mock_table = self._make_mock_client()

        with _mock_st_secrets(configured=True):
            with patch("data.price_history_store._client", return_value=mock_client):
                from data.price_history_store import record_new_events
                result = record_new_events(games)

        # Nothing to upsert
        mock_table.upsert.assert_not_called()
        assert result == 0

    def test_skips_games_without_id(self):
        """Games missing an event_id are silently skipped."""
        games = [_make_h2h_game("", "Bulls", "Pistons", -110, -110)]
        mock_client, mock_table = self._make_mock_client()

        with _mock_st_secrets(configured=True):
            with patch("data.price_history_store._client", return_value=mock_client):
                from data.price_history_store import record_new_events
                result = record_new_events(games)

        mock_table.upsert.assert_not_called()
        assert result == 0

    def test_returns_zero_on_empty_game_list(self):
        """Empty games list → 0 rows written, no DB call."""
        mock_client, mock_table = self._make_mock_client()

        with _mock_st_secrets(configured=True):
            with patch("data.price_history_store._client", return_value=mock_client):
                from data.price_history_store import record_new_events
                result = record_new_events([])

        mock_table.upsert.assert_not_called()
        assert result == 0


# ---------------------------------------------------------------------------
# inject_into_cache
# ---------------------------------------------------------------------------

class TestInjectIntoCache:
    def setup_method(self):
        clear_open_price_cache()

    def _make_mock_fetch(self, stored: dict):
        """
        Patch fetch_all_open_prices to return `stored` without a DB call.
        stored: { event_id: {"home": price, "away": price} }
        """
        return patch(
            "data.price_history_store.fetch_all_open_prices",
            return_value=stored,
        )

    def test_injects_historical_prices_into_empty_cache(self):
        """Stored prices are written into _OPEN_PRICE_CACHE."""
        games = [_make_h2h_game("g10", "Bucks", "76ers", -120, 100)]
        stored = {"g10": {"home": -120, "away": 100}}

        with _mock_st_secrets(configured=True):
            with self._make_mock_fetch(stored):
                from data.price_history_store import inject_into_cache
                injected = inject_into_cache(games)

        assert injected == 1
        assert "g10" in _OPEN_PRICE_CACHE
        assert _OPEN_PRICE_CACHE["g10"]["home"] == -120.0
        assert _OPEN_PRICE_CACHE["g10"]["away"] == 100.0

    def test_does_not_overwrite_already_cached_event(self):
        """If event_id already in cache, inject_into_cache must not overwrite it."""
        games = [_make_h2h_game("g11", "Raptors", "Pacers", -130, 110)]
        # Pre-seed the cache with a different price
        _OPEN_PRICE_CACHE["g11"] = {"home": -999.0, "away": 999.0}
        stored = {"g11": {"home": -130, "away": 110}}

        with _mock_st_secrets(configured=True):
            with self._make_mock_fetch(stored):
                from data.price_history_store import inject_into_cache
                injected = inject_into_cache(games)

        # Must NOT have overwritten the existing cache entry
        assert injected == 0
        assert _OPEN_PRICE_CACHE["g11"]["home"] == -999.0

    def test_returns_zero_on_empty_game_list(self):
        """Empty games list → 0 injected."""
        with _mock_st_secrets(configured=True):
            with self._make_mock_fetch({}):
                from data.price_history_store import inject_into_cache
                injected = inject_into_cache([])

        assert injected == 0

    def test_partial_injection_only_injects_unknown_events(self):
        """
        Two games. One already in cache, one not.
        Only the unknown event should be injected.
        """
        games = [
            _make_h2h_game("g12", "Warriors", "Clippers", -150, 130),
            _make_h2h_game("g13", "Mavericks", "Spurs",   -110, -110),
        ]
        _OPEN_PRICE_CACHE["g12"] = {"home": -999.0, "away": 999.0}  # already cached
        stored = {
            "g12": {"home": -150, "away": 130},
            "g13": {"home": -110, "away": -110},
        }

        with _mock_st_secrets(configured=True):
            with self._make_mock_fetch(stored):
                from data.price_history_store import inject_into_cache
                injected = inject_into_cache(games)

        assert injected == 1
        assert _OPEN_PRICE_CACHE["g12"]["home"] == -999.0  # untouched
        assert _OPEN_PRICE_CACHE["g13"]["home"] == -110.0  # injected
