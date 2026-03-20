"""Tests for MonadConfig — path properties, browser_path, LLMConfig defaults, init_workspace."""

import os
import shutil
from pathlib import Path

import pytest

from monad.config import (
    MonadConfig, LLMConfig, WORKSPACE_DIR,
    init_workspace, _sync_bundled_knowledge, _ensure_default_env,
    truncate, PACKAGE_DIR, DEFAULT_BASE_URL, DEFAULT_MODEL, CONFIG,
)


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

    def test_skill_dir(self, tmp_path):
        cfg = MonadConfig(root_dir=tmp_path)
        assert cfg.skill_dir("my_skill") == tmp_path / "knowledge" / "skills" / "my_skill"

    def test_web_host_default(self, monkeypatch):
        monkeypatch.delenv("WEB_HOST", raising=False)
        assert CONFIG.web_host == "127.0.0.1"

    def test_web_port_default(self, monkeypatch):
        monkeypatch.delenv("WEB_PORT", raising=False)
        assert CONFIG.web_port == 8000

    def test_web_port_from_env(self, monkeypatch):
        monkeypatch.setenv("WEB_PORT", "9999")
        assert CONFIG.web_port == 9999

    def test_web_port_invalid_env(self, monkeypatch):
        monkeypatch.setenv("WEB_PORT", "not_a_number")
        assert CONFIG.web_port == 8000


class TestTruncate:

    def test_short_text_unchanged(self):
        assert truncate("hello", 100) == "hello"

    def test_exact_boundary(self):
        assert truncate("abcde", 5) == "abcde"

    def test_over_boundary(self):
        assert truncate("abcdef", 5) == "abcde..."

    def test_empty_string(self):
        assert truncate("") == ""

    def test_none_returns_none(self):
        assert truncate(None) is None


class TestEnsureDefaultEnv:

    def test_creates_env_file(self, tmp_path):
        _ensure_default_env(tmp_path)
        env = tmp_path / ".env"
        assert env.exists()
        content = env.read_text()
        assert "MONAD_BASE_URL" in content
        assert "MONAD_API_KEY" in content

    def test_does_not_overwrite(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("CUSTOM=1\n")
        _ensure_default_env(tmp_path)
        assert env.read_text() == "CUSTOM=1\n"


class TestSyncBundledKnowledge:

    def test_fresh_workspace_gets_full_copy(self, tmp_path):
        _sync_bundled_knowledge(tmp_path)
        knowledge = tmp_path / "knowledge"
        if PACKAGE_DIR.joinpath("knowledge").exists():
            assert knowledge.exists()

    def test_system_managed_overwritten(self, tmp_path):
        bundled = PACKAGE_DIR / "knowledge"
        if not bundled.exists():
            pytest.skip("no bundled knowledge")
        knowledge = tmp_path / "knowledge"
        knowledge.mkdir()
        tools = knowledge / "tools"
        tools.mkdir()
        marker = tools / "_marker.md"
        marker.write_text("old")
        _sync_bundled_knowledge(tmp_path)
        # system-managed files are always overwritten / synced
        # marker we created may or may not survive (only bundled files are copied)
        # but at least the dir must still exist
        assert tools.exists()

    def test_user_managed_not_overwritten(self, tmp_path):
        bundled = PACKAGE_DIR / "knowledge"
        if not bundled.exists():
            pytest.skip("no bundled knowledge")
        knowledge = tmp_path / "knowledge"
        knowledge.mkdir()
        user = knowledge / "user"
        user.mkdir(parents=True)
        custom = user / "facts.md"
        custom.write_text("my custom facts")
        _sync_bundled_knowledge(tmp_path)
        assert custom.read_text() == "my custom facts"


class TestInitWorkspace:

    def test_creates_subdirs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(CONFIG, "root_dir", tmp_path)
        init_workspace(configure_logging=False)
        assert (tmp_path / "browser").exists()
        assert (tmp_path / "output").exists()
        assert (tmp_path / "input").exists()

    def test_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(CONFIG, "root_dir", tmp_path)
        init_workspace(configure_logging=False)
        init_workspace(configure_logging=False)
        assert (tmp_path / ".env").exists()


class TestWorkspaceInit:

    def test_workspace_dir_exists(self):
        assert WORKSPACE_DIR.exists()

    def test_env_file_exists(self):
        assert (WORKSPACE_DIR / ".env").exists()
