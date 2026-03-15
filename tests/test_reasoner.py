"""Tests for Reasoner — JSON parsing, hollow answer guard, action verification, thought similarity, platform info."""

import platform

import pytest
from monad.cognition.reasoner import Reasoner, REASONER_SYSTEM, _PLATFORM_INFO


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

    def test_ask_user_type_becomes_action(self, reasoner):
        result = reasoner._normalize_parsed({"type": "ask_user", "content": "你想要什么？"})
        assert result["type"] == "action"
        assert result["capability"] == "ask_user"
        assert result["params"]["question"] == "你想要什么？"

    def test_ask_user_with_question_field(self, reasoner):
        result = reasoner._normalize_parsed({"type": "ask_user", "question": "请确认"})
        assert result["capability"] == "ask_user"
        assert result["params"]["question"] == "请确认"


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

    def test_desktop_send_message_no_click_is_hollow(self, reasoner):
        actions = [
            {"capability": "shell", "params": {"command": "open -a Lark"}},
            {"capability": "desktop_control", "params": {"action": "activate Lark"}},
            {"capability": "desktop_control", "params": {"action": "screenshot"}},
        ]
        assert reasoner._is_hollow_answer("打开飞书给cube发消息", actions) is True

    def test_desktop_send_message_with_click_not_hollow(self, reasoner):
        actions = [
            {"capability": "desktop_control", "params": {"action": "activate Lark"}},
            {"capability": "desktop_control", "params": {"action": "click cube"}},
            {"capability": "desktop_control", "params": {"action": "type 你好"}},
        ]
        assert reasoner._is_hollow_answer("给cube发消息", actions) is False

    def test_messaging_click_only_no_type_is_hollow(self, reasoner):
        """Bug case: LLM clicks around but never types the message."""
        actions = [
            {"capability": "shell", "params": {"command": "open -a Lark"}},
            {"capability": "desktop_control", "params": {"action": "activate Lark"}},
            {"capability": "desktop_control", "params": {"action": "screenshot"}},
            {"capability": "desktop_control", "params": {"action": "click 消息"}},
            {"capability": "desktop_control", "params": {"action": "click 百合"}},
            {"capability": "desktop_control", "params": {"action": "click 百合"}},
        ]
        assert reasoner._is_hollow_answer("打开飞书给百合发个消息，问她晚上一起吃饭不", actions) is True

    def test_messaging_with_type_not_hollow(self, reasoner):
        actions = [
            {"capability": "desktop_control", "params": {"action": "click 百合"}},
            {"capability": "desktop_control", "params": {"action": "type 晚上一起吃饭吗？"}},
            {"capability": "desktop_control", "params": {"action": "hotkey enter"}},
        ]
        assert reasoner._is_hollow_answer("打开飞书给百合发个消息，问她晚上一起吃饭不", actions) is False

    def test_ask_question_requires_type(self, reasoner):
        actions = [
            {"capability": "desktop_control", "params": {"action": "click 百合"}},
        ]
        assert reasoner._is_hollow_answer("问她晚上一起吃饭不", actions) is True

    def test_desktop_open_app_with_click_not_hollow(self, reasoner):
        actions = [
            {"capability": "desktop_control", "params": {"action": "click 搜索"}},
        ]
        assert reasoner._is_hollow_answer("打开设置", actions) is False

    def test_desktop_click_keyword_with_type_not_hollow(self, reasoner):
        actions = [
            {"capability": "desktop_control", "params": {"action": "type hello"}},
        ]
        assert reasoner._is_hollow_answer("输入hello并发送", actions) is False

    def test_non_desktop_task_not_affected(self, reasoner):
        assert reasoner._is_hollow_answer("今天天气怎么样", []) is False


# ---------------------------------------------------------------------------
# _action_hint — smart next-step hints
# ---------------------------------------------------------------------------

class TestActionHint:

    def test_open_app_hint(self, reasoner):
        hint = reasoner._action_hint("shell", {"command": "open -a Lark"}, "(no output)")
        assert "activate Lark" in hint
        assert "Do NOT run open -a again" in hint

    def test_open_app_error_no_hint(self, reasoner):
        hint = reasoner._action_hint("shell", {"command": 'open -a "Feishu"'},
                                     "[stderr] Unable to find application named 'Feishu'")
        assert hint == ""

    def test_activate_hint_no_auto_screenshot(self, reasoner):
        hint = reasoner._action_hint("desktop_control", {"action": "activate Lark"},
                                     'Activated "Lark" (verified in foreground)')
        assert "screenshot" in hint.lower()

    def test_activate_hint_with_auto_screenshot(self, reasoner):
        result = ('Activated "Lark" (verified in foreground)\n'
                  '[Auto-screenshot of Feishu window] Found 20 UI elements:')
        hint = reasoner._action_hint("desktop_control", {"action": "activate Lark"}, result)
        assert "click" in hint.lower() or "interact" in hint.lower()
        assert "open" not in hint.lower() or "Do NOT" in hint
        assert "cmd k" in hint

    def test_screenshot_hint(self, reasoner):
        hint = reasoner._action_hint("desktop_control", {"action": "screenshot"},
                                     '[Frontmost app: Lark] Found 20 UI elements (full screen):')
        assert "click" in hint
        assert "Do NOT take another screenshot" in hint

    def test_screenshot_hint_messaging_app(self, reasoner):
        hint = reasoner._action_hint("desktop_control", {"action": "screenshot"},
                                     '[Feishu window] Found 20 UI elements:')
        assert "hotkey cmd k" in hint

    def test_click_with_also_matched_hint(self, reasoner):
        hint = reasoner._action_hint(
            "desktop_control", {"action": "click 消息"},
            'Clicked "消息" at (34,340). Also matched: "消息" at (111,146)')
        assert "Also matched" in hint or "alternatives" in hint.lower()

    def test_click_no_alternatives_no_hint(self, reasoner):
        hint = reasoner._action_hint(
            "desktop_control", {"action": "click File"},
            'Clicked "File" at (50,10).')
        assert hint == ""

    def test_unrelated_command_no_hint(self, reasoner):
        hint = reasoner._action_hint("shell", {"command": "ls -la"}, "file1\nfile2")
        assert hint == ""

    def test_web_fetch_no_hint(self, reasoner):
        hint = reasoner._action_hint("web_fetch", {"url": "https://example.com"}, "page content")
        assert hint == ""


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


# ---------------------------------------------------------------------------
# Platform info & system prompt
# ---------------------------------------------------------------------------

class TestPlatformInfo:

    def test_platform_info_contains_os(self):
        assert platform.system() in _PLATFORM_INFO

    def test_platform_info_contains_arch(self):
        assert platform.machine() in _PLATFORM_INFO

    def test_system_prompt_starts_with_platform(self):
        assert REASONER_SYSTEM.startswith("## 当前运行环境")

    def test_system_prompt_contains_desktop_control(self):
        assert "desktop_control" in REASONER_SYSTEM

    def test_system_prompt_contains_5_capabilities(self):
        assert "5个" in REASONER_SYSTEM

    def test_system_prompt_contains_screenshot(self):
        assert "screenshot" in REASONER_SYSTEM

    def test_system_prompt_contains_activate(self):
        assert "activate" in REASONER_SYSTEM

    def test_system_prompt_warns_against_split_params(self):
        assert "click 搜索" in REASONER_SYSTEM

    def test_system_prompt_warns_search_result_direct_click(self):
        assert "直接点击该搜索结果" in REASONER_SYSTEM

    def test_system_prompt_warns_messaging_needs_type(self):
        assert "type" in REASONER_SYSTEM and "发消息必须完成全流程" in REASONER_SYSTEM
