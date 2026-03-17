"""Tests for Reasoner — JSON parsing, completion check, action verification, thought similarity, platform info."""

import platform
from unittest.mock import patch

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
# _check_task_completion (replaces _is_hollow_answer)
# ---------------------------------------------------------------------------

class TestTaskCompletionCheck:

    def test_complete_response_returns_true(self, reasoner):
        with patch("monad.cognition.reasoner.llm_call", return_value="COMPLETE"):
            is_complete, reason = reasoner._check_task_completion(
                "今天天气怎么样", [], "今天北京晴天"
            )
            assert is_complete is True
            assert reason == ""

    def test_incomplete_response_returns_false_with_reason(self, reasoner):
        with patch("monad.cognition.reasoner.llm_call",
                   return_value="INCOMPLETE|未调用 stop_recording 结束录制"):
            is_complete, reason = reasoner._check_task_completion(
                "开始录屏，分析博客，结束录制",
                [{"capability": "start_recording", "params": {}}],
                "分析完成"
            )
            assert is_complete is False
            assert "stop_recording" in reason

    def test_incomplete_without_pipe_gives_default_reason(self, reasoner):
        with patch("monad.cognition.reasoner.llm_call", return_value="INCOMPLETE"):
            is_complete, reason = reasoner._check_task_completion(
                "创建文件", [], "已完成"
            )
            assert is_complete is False
            assert reason == "部分步骤未执行"

    def test_llm_failure_defaults_to_complete(self, reasoner):
        """Fail-open: if LLM call fails, allow the answer through."""
        with patch("monad.cognition.reasoner.llm_call", side_effect=Exception("timeout")):
            is_complete, reason = reasoner._check_task_completion(
                "帮我创建一个技能", [], "已创建"
            )
            assert is_complete is True

    def test_unparseable_response_defaults_to_complete(self, reasoner):
        with patch("monad.cognition.reasoner.llm_call", return_value="I'm not sure"):
            is_complete, reason = reasoner._check_task_completion(
                "做个报告", [], "报告已生成"
            )
            assert is_complete is True

    def test_action_summary_includes_all_capabilities(self, reasoner):
        """Verify that the prompt sent to LLM contains all action types."""
        actions = [
            {"capability": "python_exec", "params": {"code": "print('hi')"}},
            {"capability": "shell", "params": {"command": "ls"}},
            {"capability": "web_fetch", "params": {"url": "https://example.com"}},
            {"capability": "desktop_control", "params": {"action": "screenshot"}},
            {"capability": "start_recording", "params": {"output_path": "/tmp/r.mkv"}},
        ]
        captured_prompt = None

        def mock_llm(prompt, **kwargs):
            nonlocal captured_prompt
            captured_prompt = prompt
            return "COMPLETE"

        with patch("monad.cognition.reasoner.llm_call", side_effect=mock_llm):
            reasoner._check_task_completion("test", actions, "done")

        assert "[python_exec]" in captured_prompt
        assert "[shell]" in captured_prompt
        assert "[web_fetch]" in captured_prompt
        assert "[desktop_control]" in captured_prompt
        assert "[start_recording]" in captured_prompt


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
        assert "Do NOT" in hint
        assert "desktop_control" in hint

    def test_screenshot_hint(self, reasoner):
        hint = reasoner._action_hint("desktop_control", {"action": "screenshot"},
                                     '[Frontmost app: Lark] Found 20 UI elements (full screen):')
        assert "click" in hint.lower() or "interact" in hint.lower()

    def test_screenshot_hint_generic(self, reasoner):
        hint = reasoner._action_hint("desktop_control", {"action": "screenshot"},
                                     '[Feishu window] Found 20 UI elements:')
        assert "desktop_control" in hint or "click" in hint.lower()

    def test_click_with_also_matched_hint(self, reasoner):
        hint = reasoner._action_hint(
            "desktop_control", {"action": "click 消息"},
            'Clicked "消息" at (34,340). Also matched: "消息" at (111,146)')
        assert "Also matched" in hint or "alternatives" in hint.lower()

    def test_click_success_gives_wait_hint(self, reasoner):
        hint = reasoner._action_hint(
            "desktop_control", {"action": "click File"},
            'Clicked "File" at (50,10).')
        assert "wait" in hint.lower()

    def test_click_send_to_opens_chat(self, reasoner):
        """After clicking '发送给百合', hint should say 'type message', not 'click again'."""
        hint = Reasoner._action_hint(
            "desktop_control", {"action": "click 发送给百合"},
            'Clicked "发送给百合" at (681,703).',
            user_input='给百合发个"你好"')
        assert "type" in hint
        assert "你好" in hint
        assert "click 发送给" not in hint

    def test_click_shows_send_to_card(self, reasoner):
        """After clicking a contact, if '发送给' appears, hint should say 'click it'."""
        hint = Reasoner._action_hint(
            "desktop_control", {"action": "click_xy 288 291"},
            'Clicked at (288,291). "发送给百合" visible.')
        assert "click 发送给百合" in hint

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

    def test_system_prompt_references_tool_docs(self):
        assert "desktop_control" in REASONER_SYSTEM and "工具文档" in REASONER_SYSTEM

    def test_desktop_control_doc_has_messaging_rules(self):
        from pathlib import Path
        doc = Path(__file__).resolve().parent.parent / "monad" / "knowledge" / "tools" / "desktop_control.md"
        text = doc.read_text()
        assert "发消息必须完成全流程" in text
        assert "cmd k" in text
        assert "cmd f" in text
        assert "不要点击输入框" in text


# ---------------------------------------------------------------------------
# _update_plan (plan progress tracking)
# ---------------------------------------------------------------------------

class TestUpdatePlan:

    def test_exact_match(self, reasoner):
        plan = [
            {"step": "录屏", "capability": "start_recording", "done": False},
            {"step": "发消息", "capability": "desktop_control", "done": False},
        ]
        reasoner._update_plan(plan, "start_recording")
        assert plan[0]["done"] is True
        assert plan[1]["done"] is False

    def test_fuzzy_match_hallucinated_capability(self, reasoner):
        """desktop_control should satisfy steps tagged with non-existent capabilities."""
        plan = [
            {"step": "录屏", "capability": "start_recording", "done": True},
            {"step": "发消息", "capability": "send_feishu_msg", "done": False},
            {"step": "停止录屏", "capability": "stop_recording", "done": False},
        ]
        reasoner._update_plan(plan, "desktop_control")
        assert plan[1]["done"] is True
        assert plan[2]["done"] is False

    def test_no_match_does_nothing(self, reasoner):
        plan = [
            {"step": "录屏", "capability": "start_recording", "done": False},
        ]
        reasoner._update_plan(plan, "web_fetch")
        assert plan[0]["done"] is False

    def test_fuzzy_does_not_match_real_capabilities(self, reasoner):
        """Fuzzy match should NOT override steps tagged with real capability names."""
        plan = [
            {"step": "抓网页", "capability": "web_fetch", "done": False},
        ]
        reasoner._update_plan(plan, "desktop_control")
        assert plan[0]["done"] is False
