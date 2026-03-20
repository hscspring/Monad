"""Tests for plan JSON extraction and semantic plan/action alignment."""

import pytest

from monad.cognition.planning import (
    action_satisfies_planned_capability,
    code_suggests_http_fetch,
    extract_json_array,
    parse_plan_steps,
)


class TestExtractJsonArray:

    def test_nested_brackets(self):
        raw = 'prefix [{"step": "a", "capability": "web_fetch"}, {"step": "b", "capability": "shell"}] suffix'
        frag = extract_json_array(raw)
        assert frag is not None
        steps = parse_plan_steps(frag)
        assert len(steps) == 2
        assert steps[0]["capability"] == "web_fetch"

    def test_extra_keys_preserved_in_json(self):
        raw = r'[{"step": "x", "capability": "python_exec", "hint": "use [1,2]"}]'
        frag = extract_json_array(raw)
        assert frag is not None
        steps = parse_plan_steps(raw)
        assert len(steps) == 1
        assert steps[0]["capability"] == "python_exec"

    def test_no_array_returns_none(self):
        assert extract_json_array("just plain text") is None

    def test_unclosed_bracket(self):
        assert extract_json_array('[{"step": "a"') is None


class TestParsePlanSteps:

    def test_markdown_fences_stripped(self):
        raw = '```json\n[{"step": "do it", "capability": "shell"}]\n```'
        steps = parse_plan_steps(raw)
        assert len(steps) == 1
        assert steps[0]["capability"] == "shell"

    def test_empty_array(self):
        assert parse_plan_steps("[]") == []

    def test_not_json(self):
        assert parse_plan_steps("this is not json") == []

    def test_entries_without_step_field_skipped(self):
        raw = '[{"capability": "shell"}, {"step": "ok", "capability": "shell"}]'
        steps = parse_plan_steps(raw)
        assert len(steps) == 1
        assert steps[0]["step"] == "ok"

    def test_non_dict_entries_skipped(self):
        raw = '["hello", {"step": "real", "capability": "web_fetch"}]'
        steps = parse_plan_steps(raw)
        assert len(steps) == 1

    def test_done_always_false(self):
        raw = '[{"step": "a", "capability": "shell", "done": true}]'
        steps = parse_plan_steps(raw)
        assert steps[0]["done"] is False

    def test_empty_string(self):
        assert parse_plan_steps("") == []


class TestSemanticMatch:

    def test_web_fetch_from_python_requests(self):
        params = {"code": "import requests\nr = requests.get('https://example.com')"}
        assert action_satisfies_planned_capability(
            "web_fetch", "python_exec", params, frozenset()
        )

    def test_web_fetch_not_plain_python(self):
        params = {"code": "print(1+1)"}
        assert not action_satisfies_planned_capability(
            "web_fetch", "python_exec", params, frozenset()
        )

    def test_shell_from_python_subprocess(self):
        params = {"code": "import subprocess\nsubprocess.run(['ls'])"}
        assert action_satisfies_planned_capability(
            "shell", "python_exec", params, frozenset()
        )

    def test_code_suggests_http_fetch(self):
        assert code_suggests_http_fetch("import httpx\nhttpx.get('https://x')")
        assert not code_suggests_http_fetch("print('hello')")

    def test_exact_match(self):
        assert action_satisfies_planned_capability("shell", "shell", {}, frozenset())

    def test_named_skill_exact(self):
        assert action_satisfies_planned_capability(
            "my_skill", "my_skill", {}, frozenset({"my_skill"})
        )

    def test_named_skill_via_python_exec(self):
        params = {"code": "from my_skill import run\nrun()"}
        assert action_satisfies_planned_capability(
            "my_skill", "python_exec", params, frozenset({"my_skill"})
        )

    def test_empty_planned_returns_false(self):
        assert not action_satisfies_planned_capability("", "shell", {}, frozenset())

    def test_shell_via_curl(self):
        params = {"command": "curl https://example.com"}
        assert action_satisfies_planned_capability(
            "web_fetch", "shell", params, frozenset()
        )
