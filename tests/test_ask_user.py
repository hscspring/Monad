"""Tests for tools/ask_user.py — custom handler, default question, TOOL_META."""

from unittest.mock import patch

from monad.tools.ask_user import run, TOOL_META
import monad.tools.ask_user as ask_module


class TestAskUserMeta:

    def test_meta_fields(self):
        assert TOOL_META["name"] == "ask_user"
        assert "question" in TOOL_META["inputs"]


class TestAskUserRun:

    def test_custom_handler(self):
        original = ask_module.custom_input_handler
        try:
            ask_module.custom_input_handler = lambda: "  custom answer  "
            result = run(question="What color?")
            assert result == "custom answer"
        finally:
            ask_module.custom_input_handler = original

    def test_custom_handler_with_empty_question(self):
        original = ask_module.custom_input_handler
        try:
            ask_module.custom_input_handler = lambda: "response"
            result = run()
            assert result == "response"
        finally:
            ask_module.custom_input_handler = original

    @patch("builtins.input", return_value="  keyboard input  ")
    def test_fallback_to_input(self, mock_input):
        original = ask_module.custom_input_handler
        try:
            ask_module.custom_input_handler = None
            result = run(question="Name?")
            assert result == "keyboard input"
            mock_input.assert_called_once()
        finally:
            ask_module.custom_input_handler = original
