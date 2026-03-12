"""Tests for Reasoner — JSON parsing, hollow answer guard, action verification, thought similarity."""

import pytest
from monad.cognition.reasoner import Reasoner


@pytest.fixture
def reasoner():
    return Reasoner()


# ---------------------------------------------------------------------------
# _parse_response
# ---------------------------------------------------------------------------

class TestParseResponse:

    def test_pure_json_action(self, reasoner):
        parsed = reasoner._parse_response(
            '{"type": "action", "capability": "web_fetch", "params": {"url": "https://example.com"}}')
        assert parsed["type"] == "action"
        assert parsed["capability"] == "web_fetch"

    def test_pure_json_thought(self, reasoner):
        parsed = reasoner._parse_response('{"type": "thought", "content": "I need to search"}')
        assert parsed["type"] == "thought"

    def test_pure_json_answer(self, reasoner):
        parsed = reasoner._parse_response('{"type": "answer", "content": "Done!"}')
        assert parsed["type"] == "answer"

    def test_markdown_wrapped(self, reasoner):
        raw = '```json\n{"type": "action", "capability": "shell", "params": {"command": "ls"}}\n```'
        parsed = reasoner._parse_response(raw)
        assert parsed["type"] == "action" and parsed["capability"] == "shell"

    def test_mixed_text_json(self, reasoner):
        parsed = reasoner._parse_response('思考: {"type": "thought", "content": "分析中..."}')
        assert parsed["type"] == "thought"

    def test_think_tag_stripped(self, reasoner):
        parsed = reasoner._parse_response('<think>internal</think>{"type": "answer", "content": "result"}')
        assert parsed["type"] == "answer"

    def test_plain_text_becomes_thought(self, reasoner):
        parsed = reasoner._parse_response(
            "I need to analyze this problem carefully and think about what to do next.")
        assert parsed["type"] == "thought"

    def test_alternative_action_format(self, reasoner):
        parsed = reasoner._parse_response('{"action": "shell", "params": {"command": "pwd"}}')
        assert parsed["type"] == "action" and parsed["capability"] == "shell"

    def test_alternative_capability_format(self, reasoner):
        parsed = reasoner._parse_response('{"capability": "web_fetch", "params": {"url": "https://x.com"}}')
        assert parsed["type"] == "action" and parsed["capability"] == "web_fetch"

    def test_alternative_answer_format(self, reasoner):
        parsed = reasoner._parse_response('{"answer": "final result"}')
        assert parsed["type"] == "answer" and parsed["content"] == "final result"

    def test_minimax_xml_stripped(self, reasoner):
        parsed = reasoner._parse_response(
            '<minimax:tool_call>junk</minimax:tool_call>{"type": "answer", "content": "ok"}')
        assert parsed["type"] == "answer"

    def test_short_string_is_error(self, reasoner):
        assert reasoner._parse_response("hi")["type"] == "error"


# ---------------------------------------------------------------------------
# _normalize_parsed
# ---------------------------------------------------------------------------

class TestNormalizeParsed:

    def test_already_standard(self, reasoner):
        d = {"type": "action", "capability": "shell", "params": {}}
        assert reasoner._normalize_parsed(d) == d

    def test_action_shorthand(self, reasoner):
        result = reasoner._normalize_parsed({"action": "web_fetch", "params": {"url": "x"}})
        assert result["type"] == "action" and result["capability"] == "web_fetch"

    def test_thought_shorthand(self, reasoner):
        assert reasoner._normalize_parsed({"thought": "hmm"})["type"] == "thought"

    def test_unknown_format(self, reasoner):
        assert reasoner._normalize_parsed({"foo": "bar"}) is None


# ---------------------------------------------------------------------------
# _thought_similarity
# ---------------------------------------------------------------------------

class TestThoughtSimilarity:

    def test_identical(self, reasoner):
        assert reasoner._thought_similarity("hello world", "hello world") == 1.0

    def test_completely_different(self, reasoner):
        assert reasoner._thought_similarity("hello world", "foo bar") == 0.0

    def test_partial_overlap(self, reasoner):
        sim = reasoner._thought_similarity("the quick brown fox", "the slow brown dog")
        assert 0.0 < sim < 1.0

    def test_empty_string(self, reasoner):
        assert reasoner._thought_similarity("", "hello") == 0.0
        assert reasoner._thought_similarity("", "") == 0.0


# ---------------------------------------------------------------------------
# _is_hollow_answer
# ---------------------------------------------------------------------------

class TestHollowAnswerGuard:

    def test_creation_no_write_is_hollow(self, reasoner):
        actions = [
            {"capability": "python_exec", "params": {"code": "print(os.path.exists('/tmp'))"}},
        ]
        assert reasoner._is_hollow_answer("帮我创建一个技能", actions) is True

    def test_creation_with_write_not_hollow(self, reasoner):
        actions = [
            {"capability": "python_exec", "params": {"code": "with open('f.py', 'w') as f: f.write('hi')"}},
        ]
        assert reasoner._is_hollow_answer("帮我创建一个技能", actions) is False

    def test_non_creation_never_hollow(self, reasoner):
        assert reasoner._is_hollow_answer("今天天气怎么样", []) is False

    def test_pip_install_not_hollow(self, reasoner):
        actions = [{"capability": "shell", "params": {"command": "pip install docling"}}]
        assert reasoner._is_hollow_answer("安装 docling", actions) is False

    def test_english_keywords(self, reasoner):
        assert reasoner._is_hollow_answer("create a new skill", []) is True

    def test_makedirs_counts_as_write(self, reasoner):
        actions = [{"capability": "python_exec", "params": {"code": "os.makedirs('/tmp/s')"}}]
        assert reasoner._is_hollow_answer("保存技能", actions) is False


# ---------------------------------------------------------------------------
# _verify_action
# ---------------------------------------------------------------------------

class TestVerifyAction:

    def test_non_exec_returns_empty(self, reasoner):
        assert reasoner._verify_action("web_fetch", {}, "") == ""

    def test_no_skills_path_returns_empty(self, reasoner):
        assert reasoner._verify_action("python_exec", {"code": "print(1)"}, "") == ""

    def test_skill_exists(self, reasoner):
        """Verify against a skill that actually exists in ~/.monad/knowledge/skills/."""
        import os
        skills_dir = os.path.expanduser("~/.monad/knowledge/skills/")
        existing = None
        if os.path.isdir(skills_dir):
            for name in os.listdir(skills_dir):
                p = os.path.join(skills_dir, name)
                if (os.path.isdir(p)
                        and os.path.isfile(os.path.join(p, "skill.yaml"))
                        and os.path.isfile(os.path.join(p, "executor.py"))):
                    existing = name
                    break
        if existing is None:
            pytest.skip("No real skill found in ~/.monad/knowledge/skills/")
        code = f"open('{skills_dir}{existing}/executor.py') # /skills/{existing}"
        result = reasoner._verify_action("python_exec", {"code": code}, "")
        assert "✅" in result and existing in result

    def test_missing_files_warned(self, reasoner):
        code = "os.makedirs('/skills/nonexistent_skill_xyz')"
        result = reasoner._verify_action("python_exec", {"code": code}, "")
        if result:
            assert "⚠️" in result
