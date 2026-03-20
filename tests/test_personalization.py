"""Tests for Personalizer — extraction, parsing, and vault updates."""

import json
from unittest.mock import patch

import pytest

from monad.learning.personalization import Personalizer
from monad.knowledge.vault import KnowledgeVault
from tests.test_vault import _TmpConfig


@pytest.fixture
def vault(tmp_path):
    config = _TmpConfig(root_dir=tmp_path)
    return KnowledgeVault(config=config)


@pytest.fixture
def personalizer(vault):
    return Personalizer(vault=vault)


class TestParse:

    def test_valid_json(self, personalizer):
        raw = '{"facts": ["likes Python"], "goals": ["build an agent"], "mood": "excited"}'
        result = personalizer._parse(raw)
        assert result == {"facts": ["likes Python"], "goals": ["build an agent"], "mood": "excited"}

    def test_empty_result_returns_none(self, personalizer):
        raw = '{"facts": [], "goals": [], "mood": ""}'
        assert personalizer._parse(raw) is None

    def test_invalid_json_returns_none(self, personalizer):
        assert personalizer._parse("not json at all") is None

    def test_non_dict_returns_none(self, personalizer):
        assert personalizer._parse("[1, 2, 3]") is None

    def test_markdown_fences_stripped(self, personalizer):
        raw = '```json\n{"facts": ["uses macOS"], "goals": [], "mood": ""}\n```'
        result = personalizer._parse(raw)
        assert result is not None
        assert result["facts"] == ["uses macOS"]


class TestApply:

    def test_writes_facts(self, personalizer, vault):
        # seed the facts file
        (vault.config.user_path / "facts.md").write_text(
            "# 用户客观事实与偏好 (Facts)\n\n1. old fact\n", encoding="utf-8")

        changes = personalizer._apply({"facts": ["new fact"], "goals": [], "mood": ""})
        assert len(changes) == 1
        assert "1 条新事实" in changes[0]
        content = (vault.config.user_path / "facts.md").read_text(encoding="utf-8")
        assert "new fact" in content

    def test_writes_goals(self, personalizer, vault):
        changes = personalizer._apply({"facts": [], "goals": ["build MONAD"], "mood": ""})
        assert any("目标" in c for c in changes)
        content = (vault.config.user_path / "goals.md").read_text(encoding="utf-8")
        assert "build MONAD" in content

    def test_writes_mood(self, personalizer, vault):
        changes = personalizer._apply({"facts": [], "goals": [], "mood": "very excited"})
        assert any("心情" in c for c in changes)
        content = (vault.config.user_path / "mood.md").read_text(encoding="utf-8")
        assert "very excited" in content

    def test_no_changes_returns_empty(self, personalizer):
        changes = personalizer._apply({"facts": [], "goals": [], "mood": ""})
        assert changes == []


class TestExtractAndUpdate:

    @patch("monad.learning.personalization.llm_call")
    def test_successful_extraction(self, mock_llm, personalizer, vault):
        mock_llm.return_value = json.dumps({
            "facts": ["prefers dark mode"],
            "goals": [],
            "mood": "focused"
        })
        result = personalizer.extract_and_update("帮我设置深色模式", {"answer": "已设置"})
        assert result is not None
        assert result["facts"] == ["prefers dark mode"]
        mock_llm.assert_called_once()

    @patch("monad.learning.personalization.llm_call")
    def test_llm_failure_returns_none(self, mock_llm, personalizer):
        mock_llm.side_effect = Exception("API error")
        result = personalizer.extract_and_update("test", {"answer": "ok"})
        assert result is None

    @patch("monad.learning.personalization.llm_call")
    def test_no_new_info_returns_none(self, mock_llm, personalizer):
        mock_llm.return_value = '{"facts": [], "goals": [], "mood": ""}'
        result = personalizer.extract_and_update("hello", {"answer": "hi"})
        assert result is None
