"""Tests for schedule awareness — osascript integration."""

from unittest.mock import patch, MagicMock

import pytest

from monad.knowledge.schedule import read_today_schedule, _run_osascript


class TestRunOsascript:

    @patch("monad.knowledge.schedule.subprocess.run")
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="10:00 Meeting\n")
        result = _run_osascript("test script")
        assert result == "10:00 Meeting\n"

    @patch("monad.knowledge.schedule.subprocess.run")
    def test_failure_returns_empty(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        result = _run_osascript("test script")
        assert result == ""

    @patch("monad.knowledge.schedule.subprocess.run")
    def test_exception_returns_empty(self, mock_run):
        mock_run.side_effect = FileNotFoundError("osascript not found")
        result = _run_osascript("test script")
        assert result == ""

    @patch("monad.knowledge.schedule.subprocess.run")
    def test_timeout_returns_empty(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("osascript", 10)
        result = _run_osascript("test script")
        assert result == ""


class TestReadTodaySchedule:

    @patch("monad.knowledge.schedule.platform.system", return_value="Linux")
    def test_non_macos_returns_empty(self, _):
        assert read_today_schedule() == ""

    @patch("monad.knowledge.schedule.platform.system", return_value="Darwin")
    @patch("monad.knowledge.schedule._run_osascript")
    def test_both_calendar_and_reminders(self, mock_osascript, _):
        mock_osascript.side_effect = ["09:00 Standup\n14:00 Review\n", "- Buy groceries\n"]
        result = read_today_schedule()
        assert "09:00 Standup" in result
        assert "14:00 Review" in result
        assert "Buy groceries" in result

    @patch("monad.knowledge.schedule.platform.system", return_value="Darwin")
    @patch("monad.knowledge.schedule._run_osascript")
    def test_empty_calendar_and_reminders(self, mock_osascript, _):
        mock_osascript.side_effect = ["", ""]
        assert read_today_schedule() == ""

    @patch("monad.knowledge.schedule.platform.system", return_value="Darwin")
    @patch("monad.knowledge.schedule._run_osascript")
    def test_only_reminders(self, mock_osascript, _):
        mock_osascript.side_effect = ["", "- Task 1\n"]
        result = read_today_schedule()
        assert "Task 1" in result
        assert "日程" not in result
