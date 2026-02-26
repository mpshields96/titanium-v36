"""
tests/test_nhl_data.py — NHL goalie starter detection tests (V37 R4)
====================================================================
Tests for data/nhl_data.py.

All external calls (requests.get) are mocked via session injection.
No live API calls. Zero Odds API quota cost.

Pattern: All functions accept an optional `session` kwarg for test injection.
Cache isolation: call clear_goalie_cache() in setup_method to prevent bleed.
"""

import sys
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.nhl_data import (
    normalize_team_name,
    get_nhl_game_ids_for_date,
    get_nhl_starters_for_game,
    get_starters_for_odds_game,
    cache_goalie_status,
    get_cached_goalie_status,
    clear_goalie_cache,
    goalie_cache_size,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_session(json_data: dict, status_code: int = 200) -> MagicMock:
    """Build a mock requests.Session that returns json_data on any .get() call."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from requests import HTTPError
        mock_resp.raise_for_status.side_effect = HTTPError(f"HTTP {status_code}")

    session = MagicMock()
    session.get.return_value = mock_resp
    return session


def _boxscore_with_goalies(
    away_starter_name: str = "T. Rask",
    away_starter: bool = True,
    home_starter_name: str = "A. Price",
    home_starter: bool = True,
) -> dict:
    """Build a minimal NHL boxscore API response with goalie data."""
    return {
        "playerByGameStats": {
            "awayTeam": {
                "goalies": [
                    {
                        "name": {"default": away_starter_name},
                        "starter": away_starter,
                    }
                ]
            },
            "homeTeam": {
                "goalies": [
                    {
                        "name": {"default": home_starter_name},
                        "starter": home_starter,
                    }
                ]
            },
        }
    }


def _schedule_response(
    date_str: str = "2026-02-25",
    game_id: int = 2026020001,
    away_abbrev: str = "BOS",
    home_abbrev: str = "NYR",
    start_utc: str = "2026-02-25T23:00:00Z",
    game_state: str = "LIVE",
) -> dict:
    return {
        "gameWeek": [
            {
                "date": date_str,
                "games": [
                    {
                        "id": game_id,
                        "awayTeam": {"abbrev": away_abbrev},
                        "homeTeam": {"abbrev": home_abbrev},
                        "startTimeUTC": start_utc,
                        "gameState": game_state,
                    }
                ],
            }
        ]
    }


# ---------------------------------------------------------------------------
# normalize_team_name
# ---------------------------------------------------------------------------

class TestNormalizeTeamName:
    def test_full_name_resolves(self):
        assert normalize_team_name("Boston Bruins") == "BOS"

    def test_full_name_case_insensitive(self):
        assert normalize_team_name("boston bruins") == "BOS"

    def test_abbrev_passthrough(self):
        assert normalize_team_name("BOS") == "BOS"

    def test_abbrev_case_insensitive(self):
        assert normalize_team_name("bos") == "BOS"

    def test_last_word_partial(self):
        assert normalize_team_name("Bruins") == "BOS"

    def test_last_word_case_insensitive(self):
        assert normalize_team_name("bruins") == "BOS"

    def test_rangers_resolves(self):
        assert normalize_team_name("Rangers") == "NYR"

    def test_new_york_rangers_resolves(self):
        assert normalize_team_name("New York Rangers") == "NYR"

    def test_empty_string_returns_none(self):
        assert normalize_team_name("") is None

    def test_unknown_team_returns_none(self):
        assert normalize_team_name("Unknown FC") is None

    def test_all_32_teams_resolve(self):
        """Smoke test: all full names in _TEAM_NAME_MAP resolve without error."""
        from data.nhl_data import _TEAM_NAME_MAP
        for full_name in _TEAM_NAME_MAP:
            result = normalize_team_name(full_name)
            assert result is not None, f"Failed to normalize: {full_name}"

    def test_utah_hockey_club_resolves(self):
        assert normalize_team_name("Utah Hockey Club") == "UTA"

    def test_vegas_golden_knights_resolves(self):
        assert normalize_team_name("Vegas Golden Knights") == "VGK"


# ---------------------------------------------------------------------------
# Goalie cache
# ---------------------------------------------------------------------------

class TestGoalieCache:
    def setup_method(self):
        clear_goalie_cache()

    def test_cache_initially_empty(self):
        assert goalie_cache_size() == 0

    def test_store_and_retrieve(self):
        payload = {"game_id": 123, "away": {"starter_confirmed": True}}
        cache_goalie_status("evt_abc", payload)
        assert get_cached_goalie_status("evt_abc") == payload

    def test_missing_key_returns_none(self):
        assert get_cached_goalie_status("nonexistent") is None

    def test_cache_size_increments(self):
        cache_goalie_status("evt_1", {})
        cache_goalie_status("evt_2", {})
        assert goalie_cache_size() == 2

    def test_clear_resets_cache(self):
        cache_goalie_status("evt_1", {})
        clear_goalie_cache()
        assert goalie_cache_size() == 0

    def test_overwrite_existing_key(self):
        cache_goalie_status("evt_1", {"v": 1})
        cache_goalie_status("evt_1", {"v": 2})
        assert get_cached_goalie_status("evt_1")["v"] == 2


# ---------------------------------------------------------------------------
# get_nhl_game_ids_for_date
# ---------------------------------------------------------------------------

class TestGetNhlGameIdsForDate:
    def test_returns_game_list(self):
        session = _mock_session(_schedule_response())
        games = get_nhl_game_ids_for_date("2026-02-25", session=session)
        assert len(games) == 1
        assert games[0]["game_id"] == 2026020001

    def test_away_home_abbrevs_extracted(self):
        session = _mock_session(_schedule_response())
        games = get_nhl_game_ids_for_date("2026-02-25", session=session)
        assert games[0]["away_team"] == "BOS"
        assert games[0]["home_team"] == "NYR"

    def test_game_state_extracted(self):
        session = _mock_session(_schedule_response(game_state="FUT"))
        games = get_nhl_game_ids_for_date("2026-02-25", session=session)
        assert games[0]["game_state"] == "FUT"

    def test_date_mismatch_returns_empty(self):
        session = _mock_session(_schedule_response(date_str="2026-02-26"))
        games = get_nhl_game_ids_for_date("2026-02-25", session=session)
        assert games == []

    def test_api_error_returns_empty(self):
        session = _mock_session({}, status_code=500)
        games = get_nhl_game_ids_for_date("2026-02-25", session=session)
        assert games == []

    def test_network_exception_returns_empty(self):
        session = MagicMock()
        session.get.side_effect = Exception("Connection error")
        games = get_nhl_game_ids_for_date("2026-02-25", session=session)
        assert games == []

    def test_start_time_parsed_as_datetime(self):
        session = _mock_session(_schedule_response())
        games = get_nhl_game_ids_for_date("2026-02-25", session=session)
        assert isinstance(games[0]["game_start_utc"], datetime)

    def test_empty_gameweek_returns_empty(self):
        session = _mock_session({"gameWeek": []})
        games = get_nhl_game_ids_for_date("2026-02-25", session=session)
        assert games == []


# ---------------------------------------------------------------------------
# get_nhl_starters_for_game
# ---------------------------------------------------------------------------

class TestGetNhlStartersForGame:
    def test_returns_starter_dict(self):
        session = _mock_session(_boxscore_with_goalies())
        result = get_nhl_starters_for_game(2026020001, session=session)
        assert result is not None
        assert result["game_id"] == 2026020001

    def test_away_starter_confirmed(self):
        session = _mock_session(_boxscore_with_goalies(away_starter=True))
        result = get_nhl_starters_for_game(2026020001, session=session)
        assert result["away"]["starter_confirmed"] is True

    def test_home_starter_confirmed(self):
        session = _mock_session(_boxscore_with_goalies(home_starter=True))
        result = get_nhl_starters_for_game(2026020001, session=session)
        assert result["home"]["starter_confirmed"] is True

    def test_backup_goalie_starter_false(self):
        session = _mock_session(_boxscore_with_goalies(away_starter=False))
        result = get_nhl_starters_for_game(2026020001, session=session)
        assert result["away"]["starter_confirmed"] is False

    def test_fut_state_returns_none(self):
        """FUT state: playerByGameStats absent → returns None."""
        session = _mock_session({})
        result = get_nhl_starters_for_game(2026020001, session=session)
        assert result is None

    def test_api_error_returns_none(self):
        session = _mock_session({}, status_code=404)
        result = get_nhl_starters_for_game(2026020001, session=session)
        assert result is None

    def test_network_exception_returns_none(self):
        session = MagicMock()
        session.get.side_effect = Exception("Timeout")
        result = get_nhl_starters_for_game(2026020001, session=session)
        assert result is None

    def test_empty_goalies_returns_none(self):
        """No goalie data in response → returns None (not yet populated)."""
        payload = {
            "playerByGameStats": {
                "awayTeam": {"goalies": []},
                "homeTeam": {"goalies": []},
            }
        }
        session = _mock_session(payload)
        result = get_nhl_starters_for_game(2026020001, session=session)
        assert result is None

    def test_starter_name_captured(self):
        session = _mock_session(_boxscore_with_goalies(
            away_starter_name="T. Rask",
            home_starter_name="A. Price",
        ))
        result = get_nhl_starters_for_game(2026020001, session=session)
        assert result["away"]["starter_name"] == "T. Rask"
        assert result["home"]["starter_name"] == "A. Price"


# ---------------------------------------------------------------------------
# get_starters_for_odds_game — integration (schedule + boxscore mocked)
# ---------------------------------------------------------------------------

class TestGetStartersForOddsGame:
    def _two_call_session(
        self, schedule_data: dict, boxscore_data: dict
    ) -> MagicMock:
        """Session that returns schedule on first call, boxscore on second."""
        resp1 = MagicMock()
        resp1.json.return_value = schedule_data
        resp1.raise_for_status = MagicMock()

        resp2 = MagicMock()
        resp2.json.return_value = boxscore_data
        resp2.raise_for_status = MagicMock()

        session = MagicMock()
        session.get.side_effect = [resp1, resp2]
        return session

    def test_returns_starter_info(self):
        session = self._two_call_session(
            _schedule_response(away_abbrev="BOS", home_abbrev="NYR"),
            _boxscore_with_goalies(),
        )
        result = get_starters_for_odds_game(
            "Boston Bruins", "New York Rangers",
            session=session, _today_str="2026-02-25",
        )
        assert result is not None
        assert result["away"]["starter_confirmed"] is True

    def test_unknown_team_returns_none(self):
        result = get_starters_for_odds_game("Unknown FC", "Another FC")
        assert result is None

    def test_game_not_in_schedule_returns_none(self):
        """Schedule has no matching game → returns None."""
        session = self._two_call_session(
            _schedule_response(away_abbrev="EDM", home_abbrev="VGK"),
            _boxscore_with_goalies(),
        )
        result = get_starters_for_odds_game("Boston Bruins", "New York Rangers", session=session)
        assert result is None

    def test_timing_gate_too_early_returns_none(self):
        """game_start_utc > 90 min away → skip boxscore poll entirely."""
        future_start = datetime.now(timezone.utc) + timedelta(hours=3)
        result = get_starters_for_odds_game(
            "Boston Bruins", "New York Rangers",
            game_start_utc=future_start,
        )
        assert result is None

    def test_timing_gate_within_window_proceeds(self):
        """game_start_utc < 90 min away → proceed with poll."""
        near_start = datetime.now(timezone.utc) + timedelta(minutes=45)
        session = self._two_call_session(
            _schedule_response(away_abbrev="BOS", home_abbrev="NYR"),
            _boxscore_with_goalies(),
        )
        result = get_starters_for_odds_game(
            "Boston Bruins", "New York Rangers",
            game_start_utc=near_start,
            session=session,
            _today_str="2026-02-25",
        )
        assert result is not None
