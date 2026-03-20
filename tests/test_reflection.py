"""Tests for Reflection — tag extraction, LLM output cleaning."""

from monad.cognition.parser import parse_tags
from monad.learning.reflection import clean_llm_output


class TestParseTags:

    def test_standard_tags_line(self):
        tags = parse_tags("1. 过程: ...\n2. 结果: ...\nTags: #web_fetch #PDF #解析")
        assert "web_fetch" in tags and "pdf" in tags and "解析" in tags

    def test_numbered_tags(self):
        tags = parse_tags("some text\n5. Tags: web_fetch, PDF, 解析")
        assert "web_fetch" in tags and "pdf" in tags

    def test_chinese_comma(self):
        tags = parse_tags("Tags: #网络，#搜索，#新闻")
        assert "网络" in tags and "搜索" in tags

    def test_mixed_hash_and_plain(self):
        tags = parse_tags("Tags: #python docling #markdown")
        assert set(tags) >= {"python", "docling", "markdown"}

    def test_no_tags_returns_empty(self):
        assert parse_tags("Summary without tags") == []

    def test_single_char_filtered(self):
        tags = parse_tags("Tags: a #bb c #dd")
        assert "a" not in tags and "c" not in tags
        assert "bb" in tags and "dd" in tags


class TestCleanLLMOutput:

    def test_strip_think_blocks(self):
        assert clean_llm_output("<think>internal</think>Actual") == "Actual"

    def test_strip_unclosed_think(self):
        result = clean_llm_output("Start <think>unclosed goes on...")
        assert "Start" in result and "unclosed" not in result

    def test_strip_minimax_tags(self):
        result = clean_llm_output("<minimax:tool_call>x</minimax:tool_call> output")
        assert "output" in result and "minimax" not in result

    def test_clean_text_unchanged(self):
        assert clean_llm_output("Normal text") == "Normal text"

    def test_nested_think_blocks(self):
        result = clean_llm_output("<think>outer <think>inner</think> still</think>visible")
        assert "visible" in result
