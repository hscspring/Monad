"""Tests for desktop_control — action routing, _find_element, error handling, TOOL_META."""

from unittest.mock import patch, MagicMock
import pytest

from monad.tools.desktop_control import (
    run, _find_element, _find_all_matches, _filter_elements, _is_garbled,
    _is_self_noise, _hotkey, _get_frontmost_app, _is_same_app,
    TOOL_META, IS_MAC, IS_WIN,
)


# ---------------------------------------------------------------------------
# TOOL_META
# ---------------------------------------------------------------------------

class TestToolMeta:

    def test_meta_has_required_fields(self):
        assert TOOL_META["name"] == "desktop_control"
        assert "action" in TOOL_META["inputs"]
        assert TOOL_META["description"]


# ---------------------------------------------------------------------------
# _find_element
# ---------------------------------------------------------------------------

SAMPLE_ELEMENTS = [
    {"text": "File", "x": 50, "y": 10, "left": 40, "top": 5, "width": 20, "height": 10, "confidence": 0.95},
    {"text": "Edit", "x": 100, "y": 10, "left": 90, "top": 5, "width": 20, "height": 10, "confidence": 0.93},
    {"text": "View Settings", "x": 200, "y": 10, "left": 180, "top": 5, "width": 40, "height": 10, "confidence": 0.90},
    {"text": "搜索文件", "x": 300, "y": 50, "left": 280, "top": 45, "width": 60, "height": 10, "confidence": 0.88},
]


class TestFindElement:

    def test_exact_match(self):
        result = _find_element(SAMPLE_ELEMENTS, "File")
        assert result is not None
        assert result["text"] == "File"

    def test_exact_match_case_insensitive(self):
        result = _find_element(SAMPLE_ELEMENTS, "file")
        assert result is not None
        assert result["text"] == "File"

    def test_partial_match(self):
        result = _find_element(SAMPLE_ELEMENTS, "Settings")
        assert result is not None
        assert result["text"] == "View Settings"

    def test_chinese_match(self):
        result = _find_element(SAMPLE_ELEMENTS, "搜索")
        assert result is not None
        assert result["text"] == "搜索文件"

    def test_no_match_returns_none(self):
        result = _find_element(SAMPLE_ELEMENTS, "NonExistent")
        assert result is None

    def test_empty_elements(self):
        assert _find_element([], "anything") is None

    def test_exact_preferred_over_partial(self):
        result = _find_element(SAMPLE_ELEMENTS, "Edit")
        assert result["text"] == "Edit"


# ---------------------------------------------------------------------------
# run() — action routing
# ---------------------------------------------------------------------------

class TestRunActionRouting:

    def test_empty_action_returns_error(self):
        result = run(action="")
        assert "Error" in result

    def test_unknown_action(self):
        result = run(action="fly to the moon")
        assert "Unknown action" in result

    def test_wait_action(self):
        result = run(action="wait 0.01")
        assert "Waited" in result

    def test_wait_capped_at_10(self):
        result = run(action="wait 100")
        assert "10.0" in result

    def test_click_requires_target(self):
        result = run(action="click")
        assert "Error" in result

    def test_double_click_requires_target(self):
        result = run(action="double_click")
        assert "Error" in result

    def test_type_requires_text(self):
        result = run(action="type")
        assert "Error" in result

    def test_hotkey_requires_keys(self):
        result = run(action="hotkey")
        assert "Error" in result

    def test_find_requires_text(self):
        result = run(action="find")
        assert "Error" in result

    def test_click_xy_requires_coords(self):
        result = run(action="click_xy")
        assert "Error" in result

    def test_click_xy_requires_two_coords(self):
        result = run(action="click_xy 100")
        assert "Error" in result


# ---------------------------------------------------------------------------
# run() — with mocked screenshot + OCR
# ---------------------------------------------------------------------------

class TestRunWithMockedScreen:

    @patch("monad.tools.desktop_control._ocr")
    @patch("monad.tools.desktop_control._screenshot_window", return_value=(None, None))
    @patch("monad.tools.desktop_control._screenshot")
    @patch("monad.tools.desktop_control._get_frontmost_app", return_value="Lark")
    def test_screenshot_returns_elements(self, mock_front, mock_ss, mock_sw, mock_ocr):
        mock_ss.return_value = "/tmp/fake.png"
        mock_ocr.return_value = SAMPLE_ELEMENTS
        result = run(action="screenshot")
        assert "Found 4 UI elements" in result
        assert '"File"' in result

    @patch("monad.tools.desktop_control._ocr")
    @patch("monad.tools.desktop_control._screenshot")
    def test_screenshot_empty_screen(self, mock_ss, mock_ocr):
        mock_ss.return_value = "/tmp/fake.png"
        mock_ocr.return_value = []
        result = run(action="screenshot")
        assert "no text elements" in result

    @patch("monad.tools.desktop_control._click")
    @patch("monad.tools.desktop_control._capture_and_locate")
    def test_click_finds_and_clicks(self, mock_locate, mock_click):
        mock_locate.return_value = ({"text": "File", "x": 50, "y": 10, "width": 30, "height": 15}, "")
        result = run(action="click File")
        mock_click.assert_called_once_with(50, 10)
        assert "Clicked" in result

    @patch("monad.tools.desktop_control._click")
    @patch("monad.tools.desktop_control._capture_and_locate")
    def test_click_header_area_shows_hint(self, mock_locate, mock_click):
        """Click on element at y<60 shows header hint."""
        mock_locate.return_value = ({"text": "恒变百合", "x": 569, "y": 31, "width": 60, "height": 15}, "")
        result = run(action="click 恒变百合")
        assert "header" in result.lower() or "already be open" in result.lower()
        assert "type" in result.lower()

    @patch("monad.tools.desktop_control._click")
    @patch("monad.tools.desktop_control._capture_and_locate")
    def test_click_normal_area_no_header_hint(self, mock_locate, mock_click):
        mock_locate.return_value = ({"text": "File", "x": 100, "y": 200, "width": 40, "height": 15}, "")
        result = run(action="click File")
        assert "header" not in result.lower()

    @patch("monad.tools.desktop_control._capture_and_locate")
    def test_click_not_found(self, mock_locate):
        mock_locate.return_value = 'Element "NonExistent" not found. Visible elements: ["File"]'
        result = run(action="click NonExistent")
        assert "not found" in result

    @patch("monad.tools.desktop_control._double_click")
    @patch("monad.tools.desktop_control._capture_and_locate")
    def test_double_click_works(self, mock_locate, mock_dblclick):
        mock_locate.return_value = ({"text": "Edit", "x": 100, "y": 10, "width": 30, "height": 15}, "")
        result = run(action="double_click Edit")
        mock_dblclick.assert_called_once_with(100, 10)
        assert "Double-clicked" in result

    @patch("monad.tools.desktop_control._click")
    def test_click_xy_works(self, mock_click):
        result = run(action="click_xy 320 450")
        mock_click.assert_called_once_with(320, 450)
        assert "Clicked at (320,450)" in result

    @patch("monad.tools.desktop_control._type_text")
    def test_type_works(self, mock_type):
        result = run(action="type Hello world")
        mock_type.assert_called_once_with("Hello world")
        assert "Typed" in result

    @patch("monad.tools.desktop_control._hotkey")
    def test_hotkey_works(self, mock_hk):
        result = run(action="hotkey cmd space")
        mock_hk.assert_called_once_with("cmd", "space")
        assert "Pressed hotkey" in result

    @patch("monad.tools.desktop_control._capture_and_locate")
    def test_find_found(self, mock_locate):
        mock_locate.return_value = ({"text": "搜索文件", "x": 200, "y": 20, "width": 40, "height": 15}, "")
        result = run(action="find 搜索")
        assert "Found" in result

    @patch("monad.tools.desktop_control._capture_and_locate")
    def test_find_not_found(self, mock_locate):
        mock_locate.return_value = 'Element "不存在" not found. Visible elements: []'
        result = run(action="find 不存在")
        assert "not found" in result


# ---------------------------------------------------------------------------
# run() — ImportError handling
# ---------------------------------------------------------------------------

class TestImportErrorHandling:

    def test_missing_mss_caught(self):
        with patch("monad.tools.desktop_control._screenshot_window", return_value=(None, None)), \
             patch("monad.tools.desktop_control._screenshot", side_effect=ImportError("No module named 'mss'")):
            result = run(action="screenshot")
            assert "Missing dependency" in result

    def test_missing_pynput_caught(self):
        with patch("monad.tools.desktop_control._type_text", side_effect=ImportError("No module named 'pynput'")):
            result = run(action="type Hello")
            assert "Missing dependency" in result


# ---------------------------------------------------------------------------
# Kwargs merging — LLM sends params as separate fields
# ---------------------------------------------------------------------------

class TestKwargsMerging:

    @patch("monad.tools.desktop_control._click")
    @patch("monad.tools.desktop_control._capture_and_locate")
    def test_click_with_text_kwarg(self, mock_locate, mock_click):
        mock_locate.return_value = ({"text": "File", "x": 50, "y": 10, "width": 30, "height": 15}, "")
        result = run(action="click", text="File")
        mock_click.assert_called_once_with(50, 10)
        assert "Clicked" in result

    @patch("monad.tools.desktop_control._type_text")
    def test_type_with_text_kwarg(self, mock_type):
        result = run(action="type", text="Hello world")
        mock_type.assert_called_once_with("Hello world")
        assert "Typed" in result

    @patch("monad.tools.desktop_control._hotkey")
    def test_hotkey_with_keys_kwarg(self, mock_hk):
        result = run(action="hotkey", keys="cmd space")
        mock_hk.assert_called_once_with("cmd", "space")
        assert "Pressed hotkey" in result

    @patch("monad.tools.desktop_control._click")
    def test_click_xy_with_kwargs(self, mock_click):
        result = run(action="click_xy", x="100", y="200")
        mock_click.assert_called_once_with(100, 200)
        assert "Clicked at" in result

    @patch("monad.tools.desktop_control._capture_and_locate")
    def test_find_with_text_kwarg(self, mock_locate):
        mock_locate.return_value = ({"text": "搜索", "x": 200, "y": 20, "width": 40, "height": 15}, "")
        result = run(action="find", text="搜索")
        assert "Found" in result

    @patch("monad.tools.desktop_control._double_click")
    @patch("monad.tools.desktop_control._capture_and_locate")
    def test_double_click_with_target_kwarg(self, mock_locate, mock_dc):
        mock_locate.return_value = ({"text": "Edit", "x": 100, "y": 10, "width": 30, "height": 15}, "")
        result = run(action="double_click", target="Edit")
        mock_dc.assert_called_once_with(100, 10)
        assert "Double-clicked" in result


# ---------------------------------------------------------------------------
# _find_all_matches — search input vs result disambiguation
# ---------------------------------------------------------------------------

class TestFindAllMatches:

    def _make_el(self, text, x=100, y=100, w=60, h=15):
        return {"text": text, "x": x, "y": y, "left": x - w // 2,
                "top": y - h // 2, "width": w, "height": h}

    def test_single_exact_match_returned(self):
        el = self._make_el("File", y=100)
        best, all_m = _find_all_matches([el], "File")
        assert best is el
        assert len(all_m) == 1

    def test_partial_match_prefers_shorter_text(self):
        long = self._make_el("在飞书帮助中心中搜索百合", y=300)
        short = self._make_el("问一问：百合", y=200)
        best, all_m = _find_all_matches([long, short], "百合")
        assert best is short

    def test_no_match_returns_none(self):
        el = self._make_el("File")
        best, all_m = _find_all_matches([el], "不存在的文字")
        assert best is None
        assert all_m == []

    def test_exact_plus_partial_prefers_exact(self):
        exact = self._make_el("百合", y=300)
        partial = self._make_el("问一问：百合", y=200)
        best, all_m = _find_all_matches([exact, partial], "百合")
        assert best is exact
        assert len(all_m) == 2

    def test_two_exact_prefers_lower_y(self):
        """Search input (y=50) vs search result (y=300): prefer result."""
        search_input = self._make_el("恒变百合", y=69)
        search_result = self._make_el("恒变百合", y=124)
        best, all_m = _find_all_matches([search_input, search_result], "恒变百合")
        assert best is search_result
        assert len(all_m) == 2

    def test_three_plus_exact_returns_first(self):
        """3+ exact matches: too ambiguous, return first."""
        sidebar = self._make_el("消息", x=34, y=340)
        tab = self._make_el("消息", x=111, y=146)
        label = self._make_el("消息", x=146, y=253)
        best, all_m = _find_all_matches([sidebar, tab, label], "消息")
        assert best is sidebar
        assert len(all_m) == 3


# ---------------------------------------------------------------------------
# OCR noise filtering
# ---------------------------------------------------------------------------

class TestOCRFiltering:

    def test_is_garbled_short_text(self):
        assert _is_garbled("口") is True
        assert _is_garbled("X") is True

    def test_is_garbled_symbols(self):
        assert _is_garbled("!P<") is True
        assert _is_garbled("…口") is True

    def test_is_garbled_normal_text(self):
        assert _is_garbled("File") is False
        assert _is_garbled("搜索文件") is False
        assert _is_garbled("monad机器人") is False

    def test_filter_removes_noise(self):
        elements = [
            {"text": "口", "x": 10, "y": 10, "left": 5, "top": 5, "width": 10, "height": 10, "confidence": 0.9},
            {"text": "File", "x": 50, "y": 10, "left": 40, "top": 5, "width": 30, "height": 15, "confidence": 0.95},
            {"text": "!P<", "x": 30, "y": 30, "left": 25, "top": 25, "width": 15, "height": 10, "confidence": 0.88},
            {"text": "搜索", "x": 100, "y": 50, "left": 90, "top": 45, "width": 40, "height": 15, "confidence": 0.92},
        ]
        filtered = _filter_elements(elements)
        texts = [e["text"] for e in filtered]
        assert "File" in texts
        assert "搜索" in texts
        assert "口" not in texts
        assert "!P<" not in texts

    def test_filter_low_confidence(self):
        elements = [
            {"text": "Real", "x": 10, "y": 10, "left": 5, "top": 5, "width": 50, "height": 20, "confidence": 0.9},
            {"text": "Ghost", "x": 50, "y": 50, "left": 45, "top": 45, "width": 50, "height": 20, "confidence": 0.3},
        ]
        filtered = _filter_elements(elements)
        texts = [e["text"] for e in filtered]
        assert "Real" in texts
        assert "Ghost" not in texts

    def test_filter_caps_at_max(self):
        elements = [
            {"text": f"Element{i}", "x": i, "y": 10, "left": i, "top": 5,
             "width": 50, "height": 20, "confidence": 0.9}
            for i in range(100)
        ]
        filtered = _filter_elements(elements)
        assert len(filtered) <= 50


# ---------------------------------------------------------------------------
# activate action
# ---------------------------------------------------------------------------

class TestSelfNoiseFilter:
    """Terminal output from MONAD itself should be filtered from screenshots."""

    def test_monad_action_line(self):
        assert _is_self_noise('[MONAD]行动[desktop_control]:{"action":"screenshot"}') is True

    def test_monad_thinking(self):
        assert _is_self_noise('[MONAD]思考：用户要求打开飞书') is True

    def test_reasoning_turn(self):
        assert _is_self_noise('[MONAD 08:52:43] ── Reasoning Turn 3/30 ──') is True

    def test_coordinate_fragment(self):
        assert _is_self_noise('at (1066,633) size 605x24') is True

    def test_normal_ui_text(self):
        assert _is_self_noise('百合') is False
        assert _is_self_noise('消息') is False
        assert _is_self_noise('发送') is False

    def test_normal_long_ui_text(self):
        assert _is_self_noise('包含：百合丨群消息更新于3月12日') is False


class TestActivateAction:

    def test_activate_requires_app_name(self):
        result = run(action="activate")
        assert "Error" in result

    @patch("monad.tools.desktop_control._activate_app")
    def test_activate_calls_function(self, mock_activate):
        mock_activate.return_value = 'Activated "Lark" (brought to foreground)'
        result = run(action="activate Lark")
        mock_activate.assert_called_once_with("Lark")
        assert "Activated" in result

    @patch("monad.tools.desktop_control._activate_app")
    def test_activate_with_app_kwarg(self, mock_activate):
        mock_activate.return_value = 'Activated "Lark" (brought to foreground)'
        result = run(action="activate", app="Lark")
        mock_activate.assert_called_once_with("Lark")
        assert "Activated" in result

    @patch("monad.tools.desktop_control._filter_elements")
    @patch("monad.tools.desktop_control._ocr")
    @patch("monad.tools.desktop_control._screenshot")
    @patch("monad.tools.desktop_control._screenshot_window")
    @patch("monad.tools.desktop_control._get_frontmost_app")
    @patch("monad.tools.desktop_control._activate_app")
    def test_activate_auto_screenshots(self, mock_activate, mock_front, mock_sw, mock_ss, mock_ocr, mock_filter):
        """When activate verifies foreground, auto-screenshot is included."""
        mock_activate.return_value = 'Activated "Lark" (verified in foreground)'
        mock_front.return_value = "Feishu"
        mock_sw.return_value = (None, None)
        mock_ss.return_value = "/tmp/test.png"
        elements = [
            {"text": "消息", "x": 100, "y": 50, "left": 80, "top": 40,
             "width": 40, "height": 15, "confidence": 0.95},
        ]
        mock_ocr.return_value = elements
        mock_filter.return_value = elements
        result = run(action="activate Lark")
        assert "Activated" in result
        assert "Auto-screenshot" in result
        assert "消息" in result
        assert "hotkey cmd k" in result


# ---------------------------------------------------------------------------
# App alias matching (Lark/Feishu, WeChat/Weixin, etc.)
# ---------------------------------------------------------------------------

class TestAppAliases:

    def test_same_name(self):
        assert _is_same_app("Lark", "Lark") is True

    def test_substring(self):
        assert _is_same_app("Lark", "Lark Helper") is True

    def test_lark_feishu(self):
        assert _is_same_app("Lark", "Feishu") is True

    def test_feishu_lark(self):
        assert _is_same_app("Feishu", "Lark") is True

    def test_lark_飞书(self):
        assert _is_same_app("Lark", "飞书") is True

    def test_wechat_weixin(self):
        assert _is_same_app("WeChat", "Weixin") is True

    def test_unrelated(self):
        assert _is_same_app("Lark", "Safari") is False

    def test_case_insensitive(self):
        assert _is_same_app("lark", "FEISHU") is True
