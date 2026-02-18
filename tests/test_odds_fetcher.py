"""
tests/test_odds_fetcher.py — TITANIUM V36.1
=============================================
Tests for odds_fetcher.fetch_batch_odds() and _preferred_book().

No real API calls are made here. All HTTP responses are mocked so:
  - Zero API quota is consumed
  - Tests run offline

To test with your real API key, see the instructions at the bottom of this file.

Run with: pytest tests/test_odds_fetcher.py -v
"""

import sys
import os
import json
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from odds_fetcher import fetch_batch_odds, _preferred_book

# ---------------------------------------------------------------------------
# Shared sample data
# A minimal but realistic API response for one NHL game.
# Structure mirrors the real Odds API v4 response.
# ---------------------------------------------------------------------------

SAMPLE_NHL_GAME = {
    "id": "abc123",
    "sport_key": "icehockey_nhl",
    "sport_title": "NHL",
    "commence_time": "2026-02-18T00:00:00Z",
    "home_team": "Boston Bruins",
    "away_team": "Toronto Maple Leafs",
    "bookmakers": [
        {
            "key": "draftkings",
            "title": "DraftKings",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Boston Bruins",      "price": -130},
                        {"name": "Toronto Maple Leafs", "price": 110},
                    ],
                },
                {
                    "key": "spreads",
                    "outcomes": [
                        {"name": "Boston Bruins",      "price": -110, "point": -1.5},
                        {"name": "Toronto Maple Leafs", "price": -110, "point":  1.5},
                    ],
                },
                {
                    "key": "totals",
                    "outcomes": [
                        {"name": "Over",  "price": -115, "point": 6.0},
                        {"name": "Under", "price": -105, "point": 6.0},
                    ],
                },
            ],
        },
        {
            "key": "fanduel",
            "title": "FanDuel",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Boston Bruins",      "price": -128},
                        {"name": "Toronto Maple Leafs", "price": 108},
                    ],
                },
            ],
        },
    ],
}


def _make_mock_response(status_code: int, json_body=None, headers=None):
    """Helper: build a mock requests.Response with the given attributes."""
    import requests as req_lib
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.headers = headers or {
        "x-requests-remaining": "499",
        "x-requests-used": "1",
    }
    if json_body is not None:
        mock_resp.json.return_value = json_body
    # raise_for_status must raise requests.exceptions.HTTPError (a RequestException
    # subclass) on 4xx/5xx — matching what the real requests library raises.
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = req_lib.exceptions.HTTPError(
            f"HTTP {status_code}"
        )
    else:
        mock_resp.raise_for_status.return_value = None
    return mock_resp


# ============================================================================
# fetch_batch_odds — success path
# ============================================================================

class TestFetchBatchOddsSuccess:

    def test_returns_list_of_games_on_200(self):
        """Happy path: API returns 200 with one NHL game."""
        mock_resp = _make_mock_response(200, json_body=[SAMPLE_NHL_GAME])
        with patch("odds_fetcher.requests.get", return_value=mock_resp):
            result = fetch_batch_odds("icehockey_nhl", "FAKE_KEY")
        assert isinstance(result, list)
        assert len(result) == 1

    def test_returned_game_has_expected_keys(self):
        """Each game dict must contain the fields edge_calculator will need."""
        mock_resp = _make_mock_response(200, json_body=[SAMPLE_NHL_GAME])
        with patch("odds_fetcher.requests.get", return_value=mock_resp):
            result = fetch_batch_odds("icehockey_nhl", "FAKE_KEY")
        game = result[0]
        for key in ("id", "home_team", "away_team", "commence_time", "bookmakers"):
            assert key in game, f"Missing key: {key}"

    def test_returned_game_has_bookmakers(self):
        """Bookmakers list must be present and non-empty."""
        mock_resp = _make_mock_response(200, json_body=[SAMPLE_NHL_GAME])
        with patch("odds_fetcher.requests.get", return_value=mock_resp):
            result = fetch_batch_odds("icehockey_nhl", "FAKE_KEY")
        assert len(result[0]["bookmakers"]) > 0

    def test_correct_url_is_called(self):
        """Must call the correct Odds API endpoint for NHL."""
        mock_resp = _make_mock_response(200, json_body=[SAMPLE_NHL_GAME])
        with patch("odds_fetcher.requests.get", return_value=mock_resp) as mock_get:
            fetch_batch_odds("icehockey_nhl", "FAKE_KEY")
        called_url = mock_get.call_args[0][0]
        assert "icehockey_nhl" in called_url
        assert called_url.startswith("https://api.the-odds-api.com/v4/sports/")

    def test_correct_params_sent_to_api(self):
        """regions, oddsFormat, and markets must be in the request params."""
        mock_resp = _make_mock_response(200, json_body=[SAMPLE_NHL_GAME])
        with patch("odds_fetcher.requests.get", return_value=mock_resp) as mock_get:
            fetch_batch_odds("icehockey_nhl", "FAKE_KEY")
        params = mock_get.call_args[1]["params"]
        assert params["regions"] == "us"
        assert params["oddsFormat"] == "american"
        assert "h2h" in params["markets"]
        assert "spreads" in params["markets"]
        assert "totals" in params["markets"]

    def test_api_key_is_passed_in_params(self):
        """The api_key argument must appear in the request params (not hardcoded)."""
        mock_resp = _make_mock_response(200, json_body=[SAMPLE_NHL_GAME])
        with patch("odds_fetcher.requests.get", return_value=mock_resp) as mock_get:
            fetch_batch_odds("icehockey_nhl", "MY_TEST_KEY_XYZ")
        params = mock_get.call_args[1]["params"]
        assert params["apiKey"] == "MY_TEST_KEY_XYZ"

    def test_empty_slate_returns_empty_list(self):
        """If no games are scheduled, API returns [] — we pass it through."""
        mock_resp = _make_mock_response(200, json_body=[])
        with patch("odds_fetcher.requests.get", return_value=mock_resp):
            result = fetch_batch_odds("icehockey_nhl", "FAKE_KEY")
        assert result == []


# ============================================================================
# fetch_batch_odds — error handling (fake key / bad responses)
# ============================================================================

class TestFetchBatchOddsErrors:

    def test_invalid_api_key_returns_empty_list(self):
        """401 from the API (bad key) must return [] without raising."""
        mock_resp = _make_mock_response(401)
        mock_resp.text = "Invalid API key"
        with patch("odds_fetcher.requests.get", return_value=mock_resp):
            result = fetch_batch_odds("icehockey_nhl", "THIS_KEY_IS_FAKE")
        assert result == []

    def test_bad_sport_key_returns_empty_list_immediately(self):
        """Unknown sport_key must return [] before even calling the API."""
        with patch("odds_fetcher.requests.get") as mock_get:
            result = fetch_batch_odds("not_a_real_sport", "FAKE_KEY")
        assert result == []
        mock_get.assert_not_called()  # no API call should have been made

    def test_quota_exceeded_returns_empty_list(self):
        """429 (quota exceeded) must return [] without raising."""
        mock_resp = _make_mock_response(429)
        with patch("odds_fetcher.requests.get", return_value=mock_resp):
            result = fetch_batch_odds("icehockey_nhl", "FAKE_KEY")
        assert result == []

    def test_server_error_returns_empty_list(self):
        """500 from the API must return [] without raising."""
        mock_resp = _make_mock_response(500)
        with patch("odds_fetcher.requests.get", return_value=mock_resp):
            result = fetch_batch_odds("icehockey_nhl", "FAKE_KEY")
        assert result == []

    def test_network_timeout_returns_empty_list(self):
        """If the request times out, must return [] without raising."""
        import requests as req_lib
        with patch("odds_fetcher.requests.get", side_effect=req_lib.exceptions.Timeout):
            result = fetch_batch_odds("icehockey_nhl", "FAKE_KEY")
        assert result == []

    def test_no_network_connection_returns_empty_list(self):
        """If there's no internet, must return [] without raising."""
        import requests as req_lib
        with patch("odds_fetcher.requests.get", side_effect=req_lib.exceptions.ConnectionError):
            result = fetch_batch_odds("icehockey_nhl", "FAKE_KEY")
        assert result == []

    def test_malformed_json_returns_empty_list(self):
        """If the API returns garbage instead of JSON, must return []."""
        mock_resp = _make_mock_response(200)
        mock_resp.json.side_effect = ValueError("No JSON")
        with patch("odds_fetcher.requests.get", return_value=mock_resp):
            result = fetch_batch_odds("icehockey_nhl", "FAKE_KEY")
        assert result == []


# ============================================================================
# _preferred_book — DraftKings selection logic
# ============================================================================

class TestPreferredBook:

    def test_returns_draftkings_when_present(self):
        """DraftKings must be selected even if it's not first in the list."""
        bookmakers = [
            {"key": "fanduel",     "title": "FanDuel"},
            {"key": "draftkings",  "title": "DraftKings"},
            {"key": "betmgm",      "title": "BetMGM"},
        ]
        result = _preferred_book(bookmakers)
        assert result["key"] == "draftkings"

    def test_returns_first_book_when_draftkings_absent(self):
        """If DraftKings is not in the list, return the first bookmaker."""
        bookmakers = [
            {"key": "fanduel",  "title": "FanDuel"},
            {"key": "betmgm",   "title": "BetMGM"},
        ]
        result = _preferred_book(bookmakers)
        assert result["key"] == "fanduel"

    def test_returns_none_for_empty_list(self):
        """Empty bookmakers list must return None, not raise."""
        result = _preferred_book([])
        assert result is None

    def test_returns_only_book_when_one_present(self):
        """Single bookmaker in list should be returned regardless of key."""
        bookmakers = [{"key": "pointsbet", "title": "PointsBet"}]
        result = _preferred_book(bookmakers)
        assert result["key"] == "pointsbet"

    def test_draftkings_first_in_list_still_selected(self):
        """DraftKings first in list — should still be selected correctly."""
        bookmakers = [
            {"key": "draftkings", "title": "DraftKings"},
            {"key": "fanduel",    "title": "FanDuel"},
        ]
        result = _preferred_book(bookmakers)
        assert result["key"] == "draftkings"

    def test_preferred_book_from_real_sample_game(self):
        """Run _preferred_book against our full sample game structure."""
        result = _preferred_book(SAMPLE_NHL_GAME["bookmakers"])
        assert result["key"] == "draftkings"
        # Confirm markets are still attached to the returned dict
        assert "markets" in result
