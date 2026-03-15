"""Tests for SkillBuilder — prompt building, action handling, LLM response parsing."""

import json
from unittest.mock import patch, MagicMock

import pytest

from monad.learning.skill_builder import SkillBuilder, SKILL_BUILDER_SYSTEM


@pytest.fixture
def vault(tmp_path):
    from tests.test_vault import _TmpConfig
    from monad.knowledge.vault import KnowledgeVault
    config = _TmpConfig(root_dir=tmp_path)
    return KnowledgeVault(config=config)


@pytest.fixture
def builder(vault):
    return SkillBuilder(vault=vault)


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:

    def test_includes_goal(self, builder):
        prompt = builder._build_prompt(
            {"goal": "fetch weather"}, {"steps": []}, "")
        assert "fetch weather" in prompt

    def test_includes_steps(self, builder):
        prompt = builder._build_prompt(
            {"goal": "x"},
            {"steps": [{"action": "web_fetch", "description": "grabbed data"}]},
            "")
        assert "web_fetch" in prompt

    def test_includes_existing_skills(self, builder):
        prompt = builder._build_prompt({"goal": "x"}, {"steps": []}, "Skill: my_skill\nGoal: do stuff")
        assert "my_skill" in prompt
        assert "overlap" in prompt.lower()

    def test_no_existing_skills(self, builder):
        prompt = builder._build_prompt({"goal": "x"}, {"steps": []}, "")
        assert "No existing skills" in prompt


# ---------------------------------------------------------------------------
# evaluate_and_build
# ---------------------------------------------------------------------------

class TestEvaluateAndBuild:

    def test_skip_on_failure(self, builder):
        result = builder.evaluate_and_build(
            {"goal": "test"}, {"success": False})
        assert result is None

    @patch("monad.learning.skill_builder.llm_call")
    def test_skip_action(self, mock_llm, builder):
        mock_llm.return_value = json.dumps({"action": "skip", "reason": "one-off"})
        result = builder.evaluate_and_build(
            {"goal": "test"}, {"success": True, "steps": []})
        assert result is None

    @patch("monad.learning.skill_builder.llm_call")
    def test_create_action(self, mock_llm, builder):
        mock_llm.return_value = json.dumps({
            "action": "create",
            "reason": "new pattern",
            "skill": {
                "name": "greet",
                "goal": "Say hello",
                "inputs": ["name"],
                "steps": ["greet user"],
                "triggers": ["when greeted"],
                "code": "def run(**kwargs):\n    return 'hi'"
            }
        })
        result = builder.evaluate_and_build(
            {"goal": "say hi"}, {"success": True, "steps": []})
        assert result is not None
        assert result["name"] == "greet"
        skill_dir = builder.vault.config.skills_path / "greet"
        assert (skill_dir / "skill.yaml").exists()
        assert (skill_dir / "executor.py").exists()

    @patch("monad.learning.skill_builder.llm_call")
    def test_update_action(self, mock_llm, builder):
        builder.vault.save_skill(
            name="existing_skill", goal="Old goal", inputs=["x"], steps=["s"],
            code="def run(**kwargs): pass")
        mock_llm.return_value = json.dumps({
            "action": "update",
            "target": "existing_skill",
            "reason": "improved",
            "skill": {
                "goal": "New goal",
                "inputs": ["x", "y"],
                "steps": ["better step"],
                "code": "def run(**kwargs): return 'v2'"
            }
        })
        result = builder.evaluate_and_build(
            {"goal": "improve"}, {"success": True, "steps": []})
        assert result is not None
        assert result["updated"] is True

    @patch("monad.learning.skill_builder.llm_call")
    def test_update_no_target_returns_none(self, mock_llm, builder):
        mock_llm.return_value = json.dumps({
            "action": "update", "target": "", "reason": "oops", "skill": {}
        })
        result = builder.evaluate_and_build(
            {"goal": "x"}, {"success": True, "steps": []})
        assert result is None

    @patch("monad.learning.skill_builder.llm_call")
    def test_create_no_name_returns_none(self, mock_llm, builder):
        mock_llm.return_value = json.dumps({
            "action": "create", "reason": "new", "skill": {"name": "", "goal": "g"}
        })
        result = builder.evaluate_and_build(
            {"goal": "x"}, {"success": True, "steps": []})
        assert result is None

    @patch("monad.learning.skill_builder.llm_call")
    def test_markdown_wrapped_json(self, mock_llm, builder):
        mock_llm.return_value = '```json\n{"action": "skip", "reason": "trivial"}\n```'
        result = builder.evaluate_and_build(
            {"goal": "test"}, {"success": True, "steps": []})
        assert result is None

    @patch("monad.learning.skill_builder.llm_call")
    def test_invalid_json_returns_none(self, mock_llm, builder):
        mock_llm.return_value = "this is not json at all"
        result = builder.evaluate_and_build(
            {"goal": "test"}, {"success": True, "steps": []})
        assert result is None

    @patch("monad.learning.skill_builder.llm_call")
    def test_unknown_action_returns_none(self, mock_llm, builder):
        mock_llm.return_value = json.dumps({"action": "dance", "reason": "fun"})
        result = builder.evaluate_and_build(
            {"goal": "test"}, {"success": True, "steps": []})
        assert result is None


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

class TestSystemPrompt:

    def test_system_prompt_has_json_formats(self):
        assert '"action": "skip"' in SKILL_BUILDER_SYSTEM
        assert '"action": "create"' in SKILL_BUILDER_SYSTEM
        assert '"action": "update"' in SKILL_BUILDER_SYSTEM
