"""Tests for core/loop.py — MonadLoop orchestration with mocked components."""

from unittest.mock import patch, MagicMock

import pytest


class TestMonadLoopProcess:

    @patch("monad.core.loop.SkillBuilder")
    @patch("monad.core.loop.Reflection")
    @patch("monad.core.loop.Reasoner")
    @patch("monad.core.loop.Executor")
    @patch("monad.core.loop.KnowledgeVault")
    @patch("monad.core.loop.VoiceInput")
    @patch("monad.core.loop.Output")
    def test_process_with_actions(self, mock_out, mock_vi, mock_vault,
                                  mock_exec, mock_reasoner, mock_refl, mock_sb):
        mock_reasoner_inst = MagicMock()
        mock_reasoner_inst.solve.return_value = {
            "answer": "Done!",
            "actions": [{"capability": "shell", "params": {"command": "ls"}}],
            "thoughts": ["thinking..."],
            "success": True,
        }
        mock_reasoner.return_value = mock_reasoner_inst
        mock_exec.return_value = MagicMock(capability_names=["python_exec", "shell", "web_fetch", "ask_user", "desktop_control"])
        mock_sb.return_value = MagicMock(evaluate_and_build=MagicMock(return_value=None))
        mock_refl.return_value = MagicMock()

        from monad.core.loop import MonadLoop
        loop = MonadLoop()
        loop._process("list files")

        mock_reasoner_inst.solve.assert_called_once()
        mock_refl.return_value.learn.assert_called_once()
        mock_sb.return_value.evaluate_and_build.assert_called_once()

    @patch("monad.core.loop.SkillBuilder")
    @patch("monad.core.loop.Reflection")
    @patch("monad.core.loop.Reasoner")
    @patch("monad.core.loop.Executor")
    @patch("monad.core.loop.KnowledgeVault")
    @patch("monad.core.loop.VoiceInput")
    @patch("monad.core.loop.Output")
    def test_process_no_actions_skips_reflection(self, mock_out, mock_vi, mock_vault,
                                                  mock_exec, mock_reasoner, mock_refl, mock_sb):
        mock_reasoner_inst = MagicMock()
        mock_reasoner_inst.solve.return_value = {
            "answer": "Hello!",
            "actions": [],
            "thoughts": [],
            "success": True,
        }
        mock_reasoner.return_value = mock_reasoner_inst
        mock_exec.return_value = MagicMock(capability_names=["python_exec", "shell"])
        mock_refl.return_value = MagicMock()
        mock_sb.return_value = MagicMock()

        from monad.core.loop import MonadLoop
        loop = MonadLoop()
        loop._process("say hi")

        mock_refl.return_value.learn.assert_not_called()

    @patch("monad.core.loop.SkillBuilder")
    @patch("monad.core.loop.Reflection")
    @patch("monad.core.loop.Reasoner")
    @patch("monad.core.loop.Executor")
    @patch("monad.core.loop.KnowledgeVault")
    @patch("monad.core.loop.VoiceInput")
    @patch("monad.core.loop.Output")
    def test_run_once_returns_result(self, mock_out, mock_vi, mock_vault,
                                     mock_exec, mock_reasoner, mock_refl, mock_sb):
        expected = {"answer": "42", "actions": [], "thoughts": [], "success": True}
        mock_reasoner_inst = MagicMock()
        mock_reasoner_inst.solve.return_value = expected
        mock_reasoner.return_value = mock_reasoner_inst
        mock_exec.return_value = MagicMock(capability_names=["python_exec"])

        from monad.core.loop import MonadLoop
        loop = MonadLoop()
        result = loop.run_once("what is 6*7?")
        assert result == expected
