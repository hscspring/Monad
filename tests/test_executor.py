"""Tests for Executor — capability routing, skill loading, tool injection.

NOTE: Importing Executor triggers scrapling/playwright load which is slow (~60s).
These tests are still valuable for CI but may take a while on first import.
"""

import textwrap
from pathlib import Path

import pytest
import yaml

from monad.execution.executor import Executor


@pytest.fixture
def executor():
    return Executor()


class TestCapabilityRouting:

    def test_known_capabilities(self, executor):
        names = executor.capability_names
        assert "python_exec" in names
        assert "shell" in names
        assert "web_fetch" in names
        assert "ask_user" in names
        assert "desktop_control" in names

    def test_desktop_control_routes(self, executor):
        result = executor.execute("desktop_control", action="wait 0.01")
        assert "Waited" in result

    def test_python_exec_routes(self, executor):
        assert "routed" in executor.execute("python_exec", code='print("routed")')

    def test_shell_routes(self, executor):
        assert "routed" in executor.execute("shell", command='echo routed')

    def test_unknown_capability(self, executor):
        result = executor.execute("nonexistent_cap")
        assert "Unknown capability" in result


class TestSkillExecution:

    def test_skill_loading(self, executor, tmp_path, monkeypatch):
        skill_dir = tmp_path / "knowledge" / "skills" / "greet"
        skill_dir.mkdir(parents=True)
        (skill_dir / "skill.yaml").write_text(
            yaml.dump({"name": "greet", "goal": "Say hello", "inputs": ["name"], "steps": ["greet"]}),
            encoding="utf-8",
        )
        (skill_dir / "executor.py").write_text(
            textwrap.dedent("""\
                def run(**kwargs):
                    return f"Hello, {kwargs.get('name', 'world')}!"
            """),
            encoding="utf-8",
        )

        from monad.config import CONFIG
        monkeypatch.setattr(CONFIG, "root_dir", tmp_path)
        result = executor.execute("greet", name="MONAD")
        assert "Hello, MONAD!" in result

    def test_skill_tool_injection(self, executor, tmp_path, monkeypatch):
        skill_dir = tmp_path / "knowledge" / "skills" / "check_tools"
        skill_dir.mkdir(parents=True)
        (skill_dir / "skill.yaml").write_text(
            yaml.dump({"name": "check_tools", "goal": "check", "inputs": [], "steps": ["check"]}),
            encoding="utf-8",
        )
        (skill_dir / "executor.py").write_text(
            textwrap.dedent("""\
                def run(**kwargs):
                    return f"wf={callable(web_fetch)},sh={callable(shell)}"
            """),
            encoding="utf-8",
        )

        from monad.config import CONFIG
        monkeypatch.setattr(CONFIG, "root_dir", tmp_path)
        result = executor.execute("check_tools")
        assert "wf=True" in result and "sh=True" in result

    def test_missing_skill(self, executor):
        result = executor.execute("totally_nonexistent_skill_xyz")
        assert "Unknown capability" in result

    def test_composite_skill_sequence(self, executor, tmp_path, monkeypatch):
        root = tmp_path / "knowledge" / "skills"

        for name, ret in [
            ("leaf_a", "return 'A' + kwargs.get('x', '')"),
            ("leaf_b", "return 'B'"),
        ]:
            d = root / name
            d.mkdir(parents=True)
            (d / "skill.yaml").write_text(
                yaml.dump({"name": name, "goal": "g", "inputs": [], "steps": []}),
                encoding="utf-8",
            )
            (d / "executor.py").write_text(f"def run(**kwargs):\n    {ret}\n", encoding="utf-8")

        pipe = root / "pipe"
        pipe.mkdir(parents=True)
        (pipe / "skill.yaml").write_text(
            yaml.dump(
                {
                    "name": "pipe",
                    "goal": "pipeline",
                    "inputs": [],
                    "steps": [],
                    "composition": {"sequence": ["leaf_a", "leaf_b"]},
                }
            ),
            encoding="utf-8",
        )

        from monad.config import CONFIG

        monkeypatch.setattr(CONFIG, "root_dir", tmp_path)
        result = executor.execute("pipe", x="!")
        assert "composition: pipe → leaf_a" in result
        assert "A!" in result
        assert "composition: pipe → leaf_b" in result
        assert "B" in result


class TestTaskStatePropagation:

    def test_python_exec_receives_task_state(self, executor):
        from monad.execution.context import TaskState
        ts = TaskState()
        ts["prior_data"] = "hello from prior step"
        result = executor.execute(
            "python_exec", task_state=ts,
            code='print(task_state["prior_data"])')
        assert "hello from prior step" in result

    def test_python_exec_can_write_task_state(self, executor):
        from monad.execution.context import TaskState
        ts = TaskState()
        executor.execute(
            "python_exec", task_state=ts,
            code='task_state["computed"] = "42"')
        assert ts["computed"] == "42"

    def test_python_exec_without_task_state(self, executor):
        result = executor.execute("python_exec", code='print("no state")')
        assert "no state" in result

    def test_skill_receives_task_state(self, executor, tmp_path, monkeypatch):
        from monad.execution.context import TaskState
        skill_dir = tmp_path / "knowledge" / "skills" / "state_check"
        skill_dir.mkdir(parents=True)
        (skill_dir / "skill.yaml").write_text(
            "name: state_check\ngoal: check\ninputs: []\nsteps: [check]\n",
            encoding="utf-8")
        (skill_dir / "executor.py").write_text(
            "def run(**kwargs):\n    return f'got={task_state[\"key\"]}'",
            encoding="utf-8")

        from monad.config import CONFIG
        monkeypatch.setattr(CONFIG, "root_dir", tmp_path)
        ts = TaskState()
        ts["key"] = "value_from_state"
        result = executor.execute("state_check", task_state=ts)
        assert "got=value_from_state" in result


class TestGetSkillTeardown:

    def test_returns_teardown_name(self, executor, tmp_path, monkeypatch):
        skill_dir = tmp_path / "knowledge" / "skills" / "with_teardown"
        skill_dir.mkdir(parents=True)
        (skill_dir / "skill.yaml").write_text(
            yaml.dump({"name": "with_teardown", "goal": "g", "inputs": [], "steps": [],
                        "teardown": "cleanup_skill"}),
            encoding="utf-8",
        )
        from monad.config import CONFIG
        monkeypatch.setattr(CONFIG, "root_dir", tmp_path)
        assert executor.get_skill_teardown("with_teardown") == "cleanup_skill"

    def test_returns_none_when_no_teardown(self, executor, tmp_path, monkeypatch):
        skill_dir = tmp_path / "knowledge" / "skills" / "no_teardown"
        skill_dir.mkdir(parents=True)
        (skill_dir / "skill.yaml").write_text(
            yaml.dump({"name": "no_teardown", "goal": "g", "inputs": [], "steps": []}),
            encoding="utf-8",
        )
        from monad.config import CONFIG
        monkeypatch.setattr(CONFIG, "root_dir", tmp_path)
        assert executor.get_skill_teardown("no_teardown") is None

    def test_returns_none_for_missing_skill(self, executor):
        assert executor.get_skill_teardown("nonexistent_xyz") is None


class TestEnsureSkillDeps:

    def test_missing_deps_triggers_pip(self, executor, tmp_path, monkeypatch):
        skill_dir = tmp_path / "knowledge" / "skills" / "dep_test"
        skill_dir.mkdir(parents=True)
        (skill_dir / "skill.yaml").write_text(
            yaml.dump({"name": "dep_test", "goal": "g", "inputs": [], "steps": [],
                        "dependencies": {"python": ["a_totally_fake_pkg_xyzzy"]}}),
            encoding="utf-8",
        )
        from unittest.mock import patch
        with patch("subprocess.run") as mock_run:
            executor._ensure_skill_deps(skill_dir)
            mock_run.assert_called_once()
            args = mock_run.call_args
            assert "a_totally_fake_pkg_xyzzy" in args[0][0]

    def test_no_yaml_does_nothing(self, executor, tmp_path):
        skill_dir = tmp_path / "empty_skill"
        skill_dir.mkdir(parents=True)
        executor._ensure_skill_deps(skill_dir)


# ---------------------------------------------------------------------------
# Template resolution for composition.steps
# ---------------------------------------------------------------------------

class TestResolveTemplates:

    def test_kwargs_substitution(self, executor):
        raw = {"url": "{{kwargs.url}}", "title": "fixed"}
        result = executor._resolve_templates(raw, {"url": "https://example.com"}, {})
        assert result == {"url": "https://example.com", "title": "fixed"}

    def test_step_result_substitution(self, executor):
        raw = {"content": "{{web_to_markdown}}"}
        step_results = {"web_to_markdown": "# Hello World"}
        result = executor._resolve_templates(raw, {}, step_results)
        assert result == {"content": "# Hello World"}

    def test_missing_ref_kept_as_is(self, executor):
        raw = {"x": "{{kwargs.missing}}"}
        result = executor._resolve_templates(raw, {}, {})
        assert result == {"x": "{{kwargs.missing}}"}

    def test_non_string_values_preserved(self, executor):
        raw = {"count": 42, "flag": True}
        result = executor._resolve_templates(raw, {}, {})
        assert result == {"count": 42, "flag": True}

    def test_mixed_template_and_text(self, executor):
        raw = {"msg": "Hello {{kwargs.name}}, welcome!"}
        result = executor._resolve_templates(raw, {"name": "Alice"}, {})
        assert result == {"msg": "Hello Alice, welcome!"}


class TestCompositionSteps:

    def test_steps_with_param_mapping(self, executor, tmp_path, monkeypatch):
        from monad.config import CONFIG
        monkeypatch.setattr(CONFIG, "root_dir", tmp_path)

        # Create skill_a
        a_dir = tmp_path / "knowledge" / "skills" / "skill_a"
        a_dir.mkdir(parents=True)
        (a_dir / "skill.yaml").write_text(
            yaml.dump({"name": "skill_a", "goal": "a", "inputs": ["url"], "steps": ["fetch"]}),
            encoding="utf-8")
        (a_dir / "executor.py").write_text(
            "def run(**kw):\n    return f\"fetched:{kw.get('url', '')}\"", encoding="utf-8")

        # Create skill_b
        b_dir = tmp_path / "knowledge" / "skills" / "skill_b"
        b_dir.mkdir(parents=True)
        (b_dir / "skill.yaml").write_text(
            yaml.dump({"name": "skill_b", "goal": "b", "inputs": ["content"], "steps": ["process"]}),
            encoding="utf-8")
        (b_dir / "executor.py").write_text(
            "def run(**kw):\n    return f\"processed:{kw.get('content', '')}\"", encoding="utf-8")

        # Create composite skill
        comp_dir = tmp_path / "knowledge" / "skills" / "pipeline"
        comp_dir.mkdir(parents=True)
        (comp_dir / "skill.yaml").write_text(
            yaml.dump({
                "name": "pipeline", "goal": "chain", "inputs": ["url"],
                "steps": ["fetch then process"],
                "composition": {
                    "steps": [
                        {"skill": "skill_a", "params": {"url": "{{kwargs.url}}"}},
                        {"skill": "skill_b", "params": {"content": "{{skill_a}}"}},
                    ]
                }
            }), encoding="utf-8")

        result = executor.execute("pipeline", url="https://test.com")
        assert "fetched:https://test.com" in result
        assert "processed:fetched:https://test.com" in result
