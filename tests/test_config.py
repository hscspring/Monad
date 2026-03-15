"""Tests for MonadConfig — path properties, browser_path, LLMConfig defaults."""

from pathlib import Path

from monad.config import MonadConfig, LLMConfig, WORKSPACE_DIR


class TestLLMConfig:

    def test_defaults(self):
        cfg = LLMConfig()
        assert cfg.temperature == 0.3
        assert cfg.max_tokens == 4096
        assert isinstance(cfg.base_url, str)
        assert isinstance(cfg.model, str)


class TestMonadConfig:

    def test_default_root(self):
        cfg = MonadConfig()
        assert cfg.root_dir == WORKSPACE_DIR

    def test_custom_root(self, tmp_path):
        cfg = MonadConfig(root_dir=tmp_path)
        assert cfg.root_dir == tmp_path

    def test_knowledge_path(self, tmp_path):
        cfg = MonadConfig(root_dir=tmp_path)
        assert cfg.knowledge_path == tmp_path / "knowledge"

    def test_all_path_properties(self, tmp_path):
        cfg = MonadConfig(root_dir=tmp_path)
        expected = {
            "axioms_path": tmp_path / "knowledge" / "axioms",
            "environment_path": tmp_path / "knowledge" / "environment",
            "tools_docs_path": tmp_path / "knowledge" / "tools",
            "skills_path": tmp_path / "knowledge" / "skills",
            "protocols_path": tmp_path / "knowledge" / "protocols",
            "user_path": tmp_path / "knowledge" / "user",
            "experiences_path": tmp_path / "knowledge" / "experiences",
            "records_path": tmp_path / "knowledge" / "records",
            "cache_path": tmp_path / "knowledge" / "cache",
        }
        for attr, expected_path in expected.items():
            assert getattr(cfg, attr) == expected_path, f"{attr} mismatch"

    def test_browser_path(self, tmp_path):
        cfg = MonadConfig(root_dir=tmp_path)
        assert cfg.browser_path == tmp_path / "browser"

    def test_browser_path_not_under_knowledge(self, tmp_path):
        cfg = MonadConfig(root_dir=tmp_path)
        assert "knowledge" not in str(cfg.browser_path)

    def test_custom_knowledge_dir(self, tmp_path):
        cfg = MonadConfig(root_dir=tmp_path, knowledge_dir="kb")
        assert cfg.knowledge_path == tmp_path / "kb"
        assert cfg.axioms_path == tmp_path / "kb" / "axioms"


class TestWorkspaceInit:

    def test_workspace_dir_exists(self):
        assert WORKSPACE_DIR.exists()

    def test_env_file_exists(self):
        assert (WORKSPACE_DIR / ".env").exists()
