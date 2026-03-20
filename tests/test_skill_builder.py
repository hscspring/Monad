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

    def test_includes_detailed_trace(self, builder):
        prompt = builder._build_prompt(
            {"goal": "demo"},
            {
                "steps": [{"action": "web_fetch", "description": "x"}],
                "actions_full": [
                    {"capability": "web_fetch", "params": {"url": "https://example.com"}}
                ],
                "step_results_full": [
                    {"capability": "web_fetch", "result": "<html>ok</html>", "success": True}
                ],
            },
            "",
        )
        assert "Detailed execution trace" in prompt
        assert "https://example.com" in prompt
        assert "<html>ok</html>" in prompt


# ---------------------------------------------------------------------------
# Smoke run
# ---------------------------------------------------------------------------

class TestSmokeRun:

    def test_smoke_passes_minimal_skill(self):
        ok, msg = SkillBuilder._smoke_run_skill_code(
            "def run(**kwargs):\n    return 'ok'", []
        )
        assert ok and msg == ""

    def test_smoke_fails_when_run_raises(self):
        ok, msg = SkillBuilder._smoke_run_skill_code(
            "def run(**kwargs):\n    raise ValueError('nope')", []
        )
        assert not ok and "nope" in msg


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
        mock_llm.side_effect = [
            json.dumps({
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
            }),
            '{"pass": true, "reason": ""}'
        ]
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
        mock_llm.side_effect = [
            json.dumps({
                "action": "update",
                "target": "existing_skill",
                "reason": "improved",
                "skill": {
                    "goal": "New goal",
                    "inputs": ["x", "y"],
                    "steps": ["better step"],
                    "code": "def run(**kwargs): return 'v2'"
                }
            }),
            '{"pass": true, "reason": ""}'
        ]
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

    @patch("monad.learning.skill_builder.llm_call")
    def test_create_blocked_by_smoke(self, mock_llm, builder):
        mock_llm.side_effect = [
            json.dumps(
                {
                    "action": "create",
                    "reason": "new",
                    "skill": {
                        "name": "smoke_fail",
                        "goal": "g",
                        "inputs": [],
                        "steps": ["s"],
                        "code": "def run(**kwargs):\n    raise RuntimeError('bad')",
                    },
                }
            ),
            '{"pass": true, "reason": ""}',
        ]
        result = builder.evaluate_and_build(
            {"goal": "x"}, {"success": True, "steps": []})
        assert result is None

    @patch("monad.learning.skill_builder.llm_call")
    def test_create_composition_only_no_second_llm(self, mock_llm, builder):
        mock_llm.return_value = json.dumps(
            {
                "action": "create",
                "reason": "pipeline",
                "skill": {
                    "name": "combo_skill",
                    "goal": "chain",
                    "inputs": ["q"],
                    "steps": ["a", "b"],
                    "code": "",
                    "composition": {"sequence": ["other_a", "other_b"]},
                },
            }
        )
        result = builder.evaluate_and_build(
            {"goal": "pipe"}, {"success": True, "steps": []})
        assert result is not None
        assert result.get("name") == "combo_skill"
        import yaml

        yaml_path = builder.vault.config.skills_path / "combo_skill" / "skill.yaml"
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert data["composition"]["sequence"] == ["other_a", "other_b"]
        assert mock_llm.call_count == 1


# ---------------------------------------------------------------------------
# _review_code (LLM-based quality gate)
# ---------------------------------------------------------------------------

class TestReviewCode:

    @patch("monad.learning.skill_builder.llm_call")
    def test_pass(self, mock_llm):
        mock_llm.return_value = '{"pass": true, "reason": ""}'
        passed, reason = SkillBuilder._review_code("def run(**kw): return 1", "test")
        assert passed is True
        assert reason == ""

    @patch("monad.learning.skill_builder.llm_call")
    def test_fail(self, mock_llm):
        mock_llm.return_value = '{"pass": false, "reason": "hardcoded analysis"}'
        passed, reason = SkillBuilder._review_code("def run(**kw): return 'advice'", "分析")
        assert passed is False
        assert "hardcoded" in reason

    @patch("monad.learning.skill_builder.llm_call")
    def test_fail_open_on_error(self, mock_llm):
        """LLM call failure should not block skill creation."""
        mock_llm.side_effect = Exception("API down")
        passed, reason = SkillBuilder._review_code("def run(**kw): pass", "test")
        assert passed is True

    @patch("monad.learning.skill_builder.llm_call")
    def test_markdown_wrapped_json(self, mock_llm):
        mock_llm.return_value = '```json\n{"pass": false, "reason": "no CJK font"}\n```'
        passed, reason = SkillBuilder._review_code("def run(**kw): pass", "PDF报告")
        assert passed is False

    @patch("monad.learning.skill_builder.llm_call")
    def test_create_blocked_by_review(self, mock_llm, builder):
        """_handle_create should reject code that fails review."""
        responses = [
            json.dumps({
                "action": "create", "reason": "new",
                "skill": {"name": "bad_skill", "goal": "分析博主",
                           "inputs": ["url"], "steps": ["s"],
                           "code": "def run(**kwargs):\n    return 'hardcoded advice'"}
            }),
            '{"pass": false, "reason": "hollow skill with hardcoded content"}'
        ]
        mock_llm.side_effect = responses
        result = builder.evaluate_and_build(
            {"goal": "分析博主"}, {"success": True, "steps": []})
        assert result is None

    @patch("monad.learning.skill_builder.llm_call")
    def test_create_passes_review(self, mock_llm, builder):
        """_handle_create should accept code that passes review."""
        responses = [
            json.dumps({
                "action": "create", "reason": "new",
                "skill": {"name": "good_skill", "goal": "fetch data",
                           "inputs": ["url"], "steps": ["s"],
                           "code": "def run(**kwargs):\n    return web_fetch(url=kwargs['url'])"}
            }),
            '{"pass": true, "reason": ""}'
        ]
        mock_llm.side_effect = responses
        result = builder.evaluate_and_build(
            {"goal": "fetch data"}, {"success": True, "steps": []})
        assert result is not None
        assert result["name"] == "good_skill"


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

class TestDependencyPassing:

    @patch("monad.learning.skill_builder.llm_call")
    def test_create_saves_dependencies(self, mock_llm, builder):
        mock_llm.side_effect = [
            json.dumps({
                "action": "create", "reason": "new",
                "skill": {
                    "name": "dep_skill", "goal": "do stuff",
                    "inputs": ["x"], "steps": ["s"],
                    "code": "def run(**kwargs): return 'ok'",
                    "dependencies": {"python": ["requests>=2.0"], "system": ["ffmpeg"]},
                }
            }),
            '{"pass": true, "reason": ""}'
        ]
        result = builder.evaluate_and_build(
            {"goal": "dep test"}, {"success": True, "steps": []})
        assert result is not None

        import yaml
        yaml_path = builder.vault.config.skills_path / "dep_skill" / "skill.yaml"
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert data["dependencies"]["python"] == ["requests>=2.0"]
        assert data["dependencies"]["system"] == ["ffmpeg"]

    @patch("monad.learning.skill_builder.llm_call")
    def test_update_saves_dependencies(self, mock_llm, builder):
        builder.vault.save_skill(
            name="old_skill", goal="Old", inputs=["x"], steps=["s"],
            code="def run(**kwargs): pass")
        mock_llm.side_effect = [
            json.dumps({
                "action": "update", "target": "old_skill", "reason": "deps",
                "skill": {
                    "goal": "New", "inputs": ["x"], "steps": ["s"],
                    "code": "def run(**kwargs): return 'v2'",
                    "dependencies": {"python": ["pandas"]},
                }
            }),
            '{"pass": true, "reason": ""}'
        ]
        result = builder.evaluate_and_build(
            {"goal": "update deps"}, {"success": True, "steps": []})
        assert result is not None

        import yaml
        yaml_path = builder.vault.config.skills_path / "old_skill" / "skill.yaml"
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert data["dependencies"]["python"] == ["pandas"]

    @patch("monad.learning.skill_builder.llm_call")
    def test_create_without_dependencies(self, mock_llm, builder):
        mock_llm.side_effect = [
            json.dumps({
                "action": "create", "reason": "new",
                "skill": {
                    "name": "nodep_skill", "goal": "simple",
                    "inputs": [], "steps": ["s"],
                    "code": "def run(**kwargs): return 'ok'",
                }
            }),
            '{"pass": true, "reason": ""}'
        ]
        result = builder.evaluate_and_build(
            {"goal": "no dep"}, {"success": True, "steps": []})
        assert result is not None

        import yaml
        yaml_path = builder.vault.config.skills_path / "nodep_skill" / "skill.yaml"
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert "dependencies" not in data


class TestSystemPrompt:

    def test_system_prompt_has_json_formats(self):
        assert '"action": "skip"' in SKILL_BUILDER_SYSTEM
        assert '"action": "create"' in SKILL_BUILDER_SYSTEM
        assert '"action": "update"' in SKILL_BUILDER_SYSTEM
        assert "composition" in SKILL_BUILDER_SYSTEM
