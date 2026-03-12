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
