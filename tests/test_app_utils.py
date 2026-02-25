"""
tests/test_app_utils.py — TITANIUM V36.1
==========================================
Unit tests for app.py utility functions (_touch_activity, _ACTIVITY_FILE).

These tests use tmp_path to avoid touching the real data/ directory.
"""

import json
import sys
import os
import time
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestTouchActivity:
    """Tests for _touch_activity() inactivity tracking."""

    def test_touch_activity_writes_file(self, tmp_path, monkeypatch):
        """_touch_activity() creates last_activity.json with current timestamp."""
        import app

        activity_file = tmp_path / "last_activity.json"
        monkeypatch.setattr(app, "_ACTIVITY_FILE", activity_file)

        before = time.time()
        app._touch_activity()
        after = time.time()

        assert activity_file.exists(), "Activity file should be created"
        data = json.loads(activity_file.read_text())
        assert "ts" in data, "File should contain 'ts' key"
        assert before <= data["ts"] <= after, "Timestamp should be within test window"

    def test_touch_activity_overwrites_existing(self, tmp_path, monkeypatch):
        """_touch_activity() updates an existing file (not appends)."""
        import app

        activity_file = tmp_path / "last_activity.json"
        activity_file.write_text(json.dumps({"ts": 0.0}))
        monkeypatch.setattr(app, "_ACTIVITY_FILE", activity_file)

        app._touch_activity()

        data = json.loads(activity_file.read_text())
        assert data["ts"] > 1_000_000, "Timestamp should be a recent epoch value, not 0.0"

    def test_touch_activity_creates_parent_dir(self, tmp_path, monkeypatch):
        """_touch_activity() creates the parent directory if it doesn't exist."""
        import app

        activity_file = tmp_path / "subdir" / "last_activity.json"
        monkeypatch.setattr(app, "_ACTIVITY_FILE", activity_file)

        app._touch_activity()

        assert activity_file.exists(), "File should be created even if parent dir was missing"

    def test_touch_activity_silently_handles_os_error(self, tmp_path, monkeypatch):
        """_touch_activity() does not raise if the write fails (OSError swallowed)."""
        import app

        # Point to a path that can't be written (parent is a file, not a dir)
        blocker = tmp_path / "blocker"
        blocker.write_text("I am a file, not a directory")
        activity_file = blocker / "last_activity.json"
        monkeypatch.setattr(app, "_ACTIVITY_FILE", activity_file)

        # Must not raise
        app._touch_activity()

    def test_activity_file_path_is_absolute(self):
        """_ACTIVITY_FILE is an absolute path (not dependent on launch directory)."""
        import app

        assert app._ACTIVITY_FILE.is_absolute(), "_ACTIVITY_FILE must be an absolute path"
