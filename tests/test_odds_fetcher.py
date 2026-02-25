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

from odds_fetcher import (
    fetch_batch_odds,
    preferred_book as _preferred_book,
    compute_rest_days_from_schedule,
    cache_open_prices,
    compute_rlm,
    clear_open_price_cache,
    DailyCreditLog,
    QuotaTracker,
    DAILY_CREDIT_CAP,
    SESSION_CREDIT_HARD_STOP,
    BILLING_RESERVE,
)

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
        "x-requests-remaining": "5000",  # above BILLING_RESERVE — don't trigger guard
        "x-requests-used": "15000",
        "x-requests-last": "3",
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

    def setup_method(self):
        """Reset module-level quota before each test to prevent state bleed."""
        import odds_fetcher as _of
        _of.quota.remaining = 18000
        _of.quota.session_used = 0
        _of.quota.daily_log._data["used_today"] = 0
        _of.quota.daily_log._data["start_remaining"] = None

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

    def setup_method(self):
        """Reset module-level quota before each test to prevent state bleed."""
        import odds_fetcher as _of
        _of.quota.remaining = 18000
        _of.quota.session_used = 0
        _of.quota.daily_log._data["used_today"] = 0
        _of.quota.daily_log._data["start_remaining"] = None

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


# ============================================================================
# compute_rest_days_from_schedule — schedule-derived rest days
# ============================================================================

class TestComputeRestDaysFromSchedule:

    def _make_game(self, home: str, away: str, commence_time: str) -> dict:
        """Minimal game dict with the fields compute_rest_days needs."""
        return {
            "id": f"{home}_{commence_time}",
            "home_team": home,
            "away_team": away,
            "commence_time": commence_time,
            "bookmakers": [],
        }

    def test_empty_input_returns_empty_dict(self):
        """No games → no rest days."""
        result = compute_rest_days_from_schedule([])
        assert result == {}

    def test_single_game_all_teams_return_none(self):
        """Teams appearing only once get None (stub fallback required)."""
        games = [self._make_game("Lakers", "Celtics", "2026-02-18T00:00:00Z")]
        result = compute_rest_days_from_schedule(games)
        assert result["Lakers"] is None
        assert result["Celtics"] is None

    def test_back_to_back_same_day_returns_zero(self):
        """Team playing twice same day → rest_days = 0."""
        games = [
            self._make_game("Lakers", "Warriors", "2026-02-18T13:00:00Z"),
            self._make_game("Celtics", "Lakers",  "2026-02-18T22:00:00Z"),
        ]
        result = compute_rest_days_from_schedule(games)
        assert result["Lakers"] == 0   # same calendar day, delta < 86400s → 0

    def test_one_day_rest_returns_one(self):
        """24 hours between games → rest_days = 1."""
        games = [
            self._make_game("Lakers", "Warriors", "2026-02-18T20:00:00Z"),
            self._make_game("Celtics", "Lakers",  "2026-02-19T20:00:00Z"),
        ]
        result = compute_rest_days_from_schedule(games)
        assert result["Lakers"] == 1

    def test_two_day_rest_returns_two(self):
        """48 hours between games → rest_days = 2."""
        games = [
            self._make_game("Lakers", "Warriors", "2026-02-18T20:00:00Z"),
            self._make_game("Celtics", "Lakers",  "2026-02-20T20:00:00Z"),
        ]
        result = compute_rest_days_from_schedule(games)
        assert result["Lakers"] == 2

    def test_same_day_games_returns_zero(self):
        """Two games on the same calendar day → rest_days = 0."""
        games = [
            self._make_game("Lakers", "Warriors", "2026-02-18T00:00:00Z"),
            self._make_game("Celtics", "Lakers",  "2026-02-18T19:00:00Z"),
        ]
        result = compute_rest_days_from_schedule(games)
        assert result["Lakers"] == 0

    def test_multiple_teams_resolved_independently(self):
        """Each team's rest days are computed separately."""
        games = [
            self._make_game("Heat",   "Nets",   "2026-02-18T00:00:00Z"),
            self._make_game("Nets",   "Bulls",  "2026-02-18T23:00:00Z"),  # Nets B2B
            self._make_game("Heat",   "Bulls",  "2026-02-20T00:00:00Z"),  # Heat 2-day rest
        ]
        result = compute_rest_days_from_schedule(games)
        assert result["Nets"] == 0    # less than 1 day between games
        assert result["Heat"] == 2

    def test_teams_appearing_once_return_none(self):
        """A team in only one game returns None regardless of other teams."""
        games = [
            self._make_game("Warriors", "Celtics", "2026-02-18T00:00:00Z"),
            self._make_game("Warriors", "Lakers",  "2026-02-20T00:00:00Z"),
        ]
        result = compute_rest_days_from_schedule(games)
        assert result["Warriors"] == 2   # Warriors plays twice
        assert result["Celtics"] is None  # only plays once
        assert result["Lakers"] is None   # only plays once

    def test_invalid_commence_time_skipped(self):
        """Games with unparseable commence_time are silently skipped."""
        games = [
            self._make_game("Bucks", "Raptors", "NOT_A_DATE"),
            self._make_game("Bucks", "Heat",    "2026-02-20T00:00:00Z"),
        ]
        result = compute_rest_days_from_schedule(games)
        # Only one valid game for Bucks → None (stub fallback)
        assert result["Bucks"] is None

    def test_missing_commence_time_skipped(self):
        """Games with missing commence_time key are silently skipped."""
        games = [
            {"id": "x", "home_team": "Knicks", "away_team": "Sixers", "bookmakers": []},
            self._make_game("Knicks", "Bulls", "2026-02-20T00:00:00Z"),
        ]
        result = compute_rest_days_from_schedule(games)
        # Only one valid game per team → None
        assert result["Knicks"] is None


# ============================================================================
# compute_rlm — passive Reverse Line Movement detection
# ============================================================================

def _make_h2h_game(event_id: str, home: str, away: str,
                   home_price: int, away_price: int) -> dict:
    """Minimal game dict with one h2h bookmaker for RLM tests."""
    return {
        "id": event_id,
        "home_team": home,
        "away_team": away,
        "commence_time": "2026-02-18T20:00:00Z",
        "bookmakers": [
            {
                "key": "draftkings",
                "title": "DraftKings",
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


class TestComputeRlm:

    def setup_method(self):
        """Clear the open price cache before each test to ensure isolation."""
        clear_open_price_cache()

    def test_empty_games_returns_empty_dict(self):
        """No games → empty result."""
        result = compute_rlm([])
        assert result == {}

    def test_no_cache_returns_false(self):
        """If cache_open_prices was never called, all events return False."""
        game = _make_h2h_game("g1", "Lakers", "Celtics", -130, 110)
        result = compute_rlm([game])
        assert result["g1"] is False

    def test_no_movement_returns_false(self):
        """Prices unchanged from open → no RLM."""
        game = _make_h2h_game("g2", "Lakers", "Celtics", -150, 130)
        cache_open_prices([game])
        result = compute_rlm([game])   # same prices = no drift
        assert result["g2"] is False

    def test_rlm_fires_when_public_on_home_and_line_moves_to_away(self):
        """
        Public on home favourite (-150). Line moves: away drifts from +130 → +105
        (away implied prob: 43% → 49%, shift = +6% > 3% threshold). RLM = True.
        """
        open_game    = _make_h2h_game("g3", "Celtics", "Wizards", -150,  130)
        current_game = _make_h2h_game("g3", "Celtics", "Wizards", -120,  100)
        cache_open_prices([open_game])
        result = compute_rlm([current_game])
        assert result["g3"] is True

    def test_rlm_does_not_fire_on_small_drift(self):
        """
        Line moves by only ~1% implied prob shift — below 3% threshold. No RLM.
        -150 → -148: trivially small movement.
        """
        open_game    = _make_h2h_game("g4", "Celtics", "Wizards", -150, 130)
        current_game = _make_h2h_game("g4", "Celtics", "Wizards", -148, 128)
        cache_open_prices([open_game])
        result = compute_rlm([current_game])
        assert result["g4"] is False

    def test_rlm_fires_on_away_favourite_line_move_to_home(self):
        """
        Away is the favourite (-140). Line moves to favour home team.
        Home implied prob increases > 3% → RLM fires.
        """
        open_game    = _make_h2h_game("g5", "Knicks", "Heat", 120, -140)
        current_game = _make_h2h_game("g5", "Knicks", "Heat",  90, -110)
        cache_open_prices([open_game])
        result = compute_rlm([current_game])
        assert result["g5"] is True

    def test_pick_em_game_no_rlm_signal(self):
        """
        Neither team is a clear favourite (both at -105 or longer). No RLM signal.
        Public side heuristic only applies when price < -105.
        """
        open_game    = _make_h2h_game("g6", "Celtics", "Sixers", -104, -104)
        current_game = _make_h2h_game("g6", "Celtics", "Sixers", -110, 100)
        cache_open_prices([open_game])
        result = compute_rlm([current_game])
        assert result["g6"] is False

    def test_cache_is_frozen_second_call_does_not_overwrite(self):
        """
        Open price cache uses first-seen values. Calling cache_open_prices again
        with different prices must NOT overwrite the original baseline.
        """
        open_game    = _make_h2h_game("g7", "Bucks", "Nets", -150, 130)
        # "Different prices" — simulating a refresh call
        refresh_game = _make_h2h_game("g7", "Bucks", "Nets", -110, 100)
        cache_open_prices([open_game])
        cache_open_prices([refresh_game])   # must not overwrite
        # Now compute RLM using the refresh prices as current
        result = compute_rlm([refresh_game])
        # Bucks at -150 open → public on Bucks. Nets prob drifts from ~43% to ~50% → RLM.
        assert result["g7"] is True

    def test_multiple_events_resolved_independently(self):
        """RLM is computed per-event; one event firing does not affect others."""
        game_a_open = _make_h2h_game("ga", "Lakers",  "Celtics",  -150, 130)
        game_b_open = _make_h2h_game("gb", "Nuggets", "Warriors", -150, 130)

        game_a_curr = _make_h2h_game("ga", "Lakers",  "Celtics",  -115, 95)   # big move → RLM
        game_b_curr = _make_h2h_game("gb", "Nuggets", "Warriors", -148, 128)  # tiny move → no RLM

        cache_open_prices([game_a_open, game_b_open])
        result = compute_rlm([game_a_curr, game_b_curr])

        assert result["ga"] is True
        assert result["gb"] is False

    def test_game_with_no_bookmakers_returns_false(self):
        """Games with empty bookmakers list cannot produce RLM signal."""
        open_game = _make_h2h_game("g8", "Heat", "Magic", -130, 110)
        cache_open_prices([open_game])
        # Current game has no bookmakers
        empty_game = {
            "id": "g8",
            "home_team": "Heat",
            "away_team": "Magic",
            "commence_time": "2026-02-18T20:00:00Z",
            "bookmakers": [],
        }
        result = compute_rlm([empty_game])
        assert result["g8"] is False


# ---------------------------------------------------------------------------
# DailyCreditLog — persistent daily cap
# ---------------------------------------------------------------------------

class TestDailyCreditLog:
    """Tests for the persistent daily credit cap (1,000 credits/day rule)."""

    def setup_method(self):
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp.close()
        self.log = DailyCreditLog(log_path=self._tmp.name)

    def teardown_method(self):
        import os as _os
        try:
            _os.unlink(self._tmp.name)
        except OSError:
            pass

    def test_fresh_log_used_today_is_zero(self):
        assert self.log.used_today() == 0

    def test_fresh_log_is_daily_cap_not_hit(self):
        assert self.log.is_daily_cap_hit() is False

    def test_record_sets_start_remaining_on_first_call(self):
        self.log.record(18000)
        assert self.log._data["start_remaining"] == 18000
        assert self.log._data["used_today"] == 0

    def test_record_calculates_used_on_second_call(self):
        self.log.record(18000)
        self.log.record(17994)
        assert self.log.used_today() == 6

    def test_is_daily_cap_hit_when_used_exceeds_cap(self):
        self.log.record(18000)
        self.log.record(18000 - DAILY_CREDIT_CAP)  # exactly at cap
        assert self.log.is_daily_cap_hit() is True

    def test_used_today_never_goes_negative(self):
        self.log.record(18000)
        self.log.record(18001)  # remaining went UP (shouldn't happen but must be safe)
        assert self.log.used_today() == 0

    def test_report_includes_cap_warning_when_hit(self):
        self.log.record(18000)
        self.log.record(18000 - DAILY_CREDIT_CAP)
        assert "DAILY_CAP" in self.log.report()

    def test_report_no_warning_when_under_cap(self):
        self.log.record(18000)
        self.log.record(17500)
        assert "DAILY_CAP" not in self.log.report()

    def test_persists_and_reloads(self):
        self.log.record(18000)
        self.log.record(17990)
        reloaded = DailyCreditLog(log_path=self._tmp.name)
        assert reloaded.used_today() == 10


# ---------------------------------------------------------------------------
# QuotaTracker — session + daily guards
# ---------------------------------------------------------------------------

class TestQuotaTrackerGuards:
    """Tests for QuotaTracker credit enforcement guards."""

    def setup_method(self):
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp.close()
        self.qt = QuotaTracker()
        # Replace daily_log with isolated temp-file version
        self.qt.daily_log = DailyCreditLog(log_path=self._tmp.name)

    def teardown_method(self):
        import os as _os
        try:
            _os.unlink(self._tmp.name)
        except OSError:
            pass

    def _headers(self, remaining: int, used: int = 0, last: int = 3) -> dict:
        return {
            "x-requests-remaining": str(remaining),
            "x-requests-used": str(used),
            "x-requests-last": str(last),
        }

    def test_no_hard_stop_initially(self):
        assert self.qt.is_session_hard_stop() is False

    def test_session_hard_stop_when_session_used_at_cap(self):
        self.qt.session_used = SESSION_CREDIT_HARD_STOP
        assert self.qt.is_session_hard_stop() is True

    def test_billing_reserve_triggers_hard_stop(self):
        self.qt.update(self._headers(remaining=BILLING_RESERVE - 1))
        assert self.qt.is_session_hard_stop() is True

    def test_billing_reserve_exact_boundary(self):
        self.qt.update(self._headers(remaining=BILLING_RESERVE))
        # Exactly at reserve floor = not yet triggered
        assert self.qt.is_session_hard_stop() is False

    def test_daily_cap_triggers_hard_stop(self):
        self.qt.daily_log.record(18000)
        self.qt.daily_log.record(18000 - DAILY_CREDIT_CAP)
        assert self.qt.is_session_hard_stop() is True

    def test_session_used_increments_from_remaining_delta(self):
        # First call: prev_remaining=None → falls back to last_cost=3 → session_used=3
        self.qt.update(self._headers(remaining=18000, last=3))
        # Second call: prev=18000, new=17997 → delta=3 → session_used=6
        self.qt.update(self._headers(remaining=17997, last=3))
        assert self.qt.session_used == 6

    def test_session_soft_limit_fires_at_threshold(self):
        self.qt.session_used = 300
        assert self.qt.is_session_soft_limit() is True

    def test_report_includes_daily_info(self):
        report = self.qt.report()
        assert "daily=" in report

    def test_report_shows_hard_stop_when_session_maxed(self):
        self.qt.session_used = SESSION_CREDIT_HARD_STOP
        assert "HARD_STOP" in self.qt.report()


# ---------------------------------------------------------------------------
# fetch_game_lines — guard enforcement
# ---------------------------------------------------------------------------

class TestFetchGameLinesGuards:
    """fetch_game_lines must return [] without calling the API when any guard is hit."""

    def setup_method(self):
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp.close()
        import odds_fetcher as _of
        # Replace module-level quota with isolated version
        self._orig_quota = _of.quota
        _of.quota = QuotaTracker()
        _of.quota.daily_log = DailyCreditLog(log_path=self._tmp.name)
        self._module = _of

    def teardown_method(self):
        import os as _os
        self._module.quota = self._orig_quota
        try:
            _os.unlink(self._tmp.name)
        except OSError:
            pass

    def test_fetch_blocked_when_session_hard_stop(self):
        self._module.quota.session_used = SESSION_CREDIT_HARD_STOP
        with patch("odds_fetcher._get") as mock_get:
            result = self._module.fetch_game_lines("basketball_nba")
        assert result == []
        mock_get.assert_not_called()

    def test_fetch_blocked_when_billing_reserve_low(self):
        self._module.quota.remaining = BILLING_RESERVE - 1
        with patch("odds_fetcher._get") as mock_get:
            result = self._module.fetch_game_lines("basketball_nba")
        assert result == []
        mock_get.assert_not_called()

    def test_fetch_blocked_when_daily_cap_hit(self):
        self._module.quota.daily_log.record(18000)
        self._module.quota.daily_log.record(18000 - DAILY_CREDIT_CAP)
        with patch("odds_fetcher._get") as mock_get:
            result = self._module.fetch_game_lines("basketball_nba")
        assert result == []
        mock_get.assert_not_called()

    def test_fetch_proceeds_when_guards_clear(self):
        mock_resp = [{"id": "g1", "home_team": "Lakers", "away_team": "Celtics",
                      "commence_time": "2026-02-18T00:00:00Z", "bookmakers": []}]
        with patch("odds_fetcher._get", return_value=mock_resp):
            result = self._module.fetch_game_lines("basketball_nba")
        assert result == mock_resp
