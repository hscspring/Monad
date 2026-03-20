"""Tests for KnowledgeVault — experience staging, tag filtering, skill I/O."""

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from monad.knowledge.vault import KnowledgeVault, PROMOTE_THRESHOLD


@dataclass
class _TmpConfig:
    root_dir: Path
    knowledge_dir: str = "knowledge"

    @property
    def knowledge_path(self):
        return self.root_dir / self.knowledge_dir

    @property
    def axioms_path(self):
        return self.knowledge_path / "axioms"

    @property
    def environment_path(self):
        return self.knowledge_path / "environment"

    @property
    def tools_docs_path(self):
        return self.knowledge_path / "tools"

    @property
    def skills_path(self):
        return self.knowledge_path / "skills"

    @property
    def protocols_path(self):
        return self.knowledge_path / "protocols"

    @property
    def user_path(self):
        return self.knowledge_path / "user"

    @property
    def experiences_path(self):
        return self.knowledge_path / "experiences"

    @property
    def records_path(self):
        return self.knowledge_path / "records"

    @property
    def cache_path(self):
        return self.knowledge_path / "cache"

    def skill_dir(self, name: str) -> Path:
        return self.skills_path / name


@pytest.fixture
def vault(tmp_path):
    config = _TmpConfig(root_dir=tmp_path)
    return KnowledgeVault(config=config)


# ---------------------------------------------------------------------------
# Experience staging: pending → promote
# ---------------------------------------------------------------------------

class TestExperienceStaging:

    def test_first_save_goes_to_pending(self, vault):
        result = vault.save_experience("task A", "summary A", tags=["web", "fetch"])
        assert "pending.jsonl" in result.name
        pending = vault._read_pending(vault.config.experiences_path / "pending.jsonl")
        assert len(pending) == 1
        assert pending[0]["task"] == "task A"

    def test_below_threshold_stays_pending(self, vault):
        for i in range(PROMOTE_THRESHOLD - 1):
            vault.save_experience(f"task {i}", f"summary {i}", tags=["web"])
        promoted = vault.config.experiences_path / "accumulated_experiences.md"
        assert not promoted.exists()

    def test_reaching_threshold_promotes(self, vault):
        for i in range(PROMOTE_THRESHOLD):
            vault.save_experience(f"web task {i}", f"summary {i}", tags=["web", "fetch"])
        promoted = vault.config.experiences_path / "accumulated_experiences.md"
        assert promoted.exists()
        content = promoted.read_text(encoding="utf-8")
        assert "[SUCCESS]" in content
        assert "#web" in content

    def test_promotion_purges_cluster(self, vault):
        for i in range(PROMOTE_THRESHOLD):
            vault.save_experience(f"web task {i}", f"summary {i}", tags=["web"])
        pending = vault._read_pending(vault.config.experiences_path / "pending.jsonl")
        web_entries = [e for e in pending if "web" in e.get("tags", [])]
        assert len(web_entries) == 0

    def test_unrelated_entries_survive_purge(self, vault):
        vault.save_experience("unrelated", "different topic", tags=["music"])
        for i in range(PROMOTE_THRESHOLD):
            vault.save_experience(f"web {i}", f"summary {i}", tags=["web"])
        pending = vault._read_pending(vault.config.experiences_path / "pending.jsonl")
        music_entries = [e for e in pending if "music" in e.get("tags", [])]
        assert len(music_entries) == 1

    def test_failed_experience_never_promotes(self, vault):
        for i in range(PROMOTE_THRESHOLD + 2):
            vault.save_experience(f"fail {i}", f"oops {i}", success=False, tags=["web"])
        promoted = vault.config.experiences_path / "accumulated_experiences.md"
        assert not promoted.exists()

    def test_no_tags_never_promotes(self, vault):
        for i in range(PROMOTE_THRESHOLD + 2):
            vault.save_experience(f"task {i}", f"summary {i}", tags=[])
        promoted = vault.config.experiences_path / "accumulated_experiences.md"
        assert not promoted.exists()

    def test_promotion_picks_best_quality(self, vault):
        """Best = most tags + longest summary, not just the last entry."""
        vault.save_experience("web task 0", "short", tags=["web"])
        vault.save_experience(
            "web task 1",
            "This is a much longer and more detailed summary with actionable insights",
            tags=["web", "fetch", "analysis"])
        vault.save_experience("web task 2", "brief", tags=["web"])
        promoted = vault.config.experiences_path / "accumulated_experiences.md"
        assert promoted.exists()
        content = promoted.read_text(encoding="utf-8")
        assert "much longer and more detailed" in content


# ---------------------------------------------------------------------------
# Experience loading & tag-based retrieval
# ---------------------------------------------------------------------------

class TestExperienceLoading:

    def _seed_promoted(self, vault, entries):
        promoted_path = vault.config.experiences_path / "accumulated_experiences.md"
        blocks = []
        for task, summary, tags in entries:
            tag_line = f"\nTags: {' '.join('#' + t for t in tags)}\n" if tags else ""
            blocks.append(f"### 历史任务: {task} [SUCCESS]\n{summary}{tag_line}")
        promoted_path.write_text("\n\n---\n\n".join(blocks) + "\n\n---\n\n", encoding="utf-8")

    def test_tag_matching_returns_relevant(self, vault):
        self._seed_promoted(vault, [
            ("分析 PDF 文档", "用 docling 解析了 PDF", ["pdf", "docling", "解析"]),
            ("搜索新闻", "从 Bing 抓了新闻", ["news", "bing", "搜索"]),
            ("写 Python 脚本", "写了数据处理脚本", ["python", "脚本"]),
        ])
        result = vault.load_experiences(query="帮我解析这个 PDF")
        assert "docling" in result

    def test_failed_experiences_excluded(self, vault):
        promoted_path = vault.config.experiences_path / "accumulated_experiences.md"
        promoted_path.write_text(
            "### 历史任务: 失败的任务 [FAILED]\n这是失败的\nTags: #web\n\n---\n\n"
            "### 历史任务: 成功的任务 [SUCCESS]\n这是成功的\nTags: #web\n\n---\n\n",
            encoding="utf-8",
        )
        result = vault.load_experiences(query="web")
        assert "成功的" in result
        assert "失败的" not in result

    def test_recent_fallback_always_included(self, vault):
        self._seed_promoted(vault, [
            ("旧任务 A", "很久以前", ["old"]),
            ("旧任务 B", "也很久了", ["old"]),
            ("最近任务 X", "刚做的 X", ["recent_x"]),
            ("最近任务 Y", "刚做的 Y", ["recent_y"]),
            ("最近任务 Z", "刚做的 Z", ["recent_z"]),
        ])
        result = vault.load_experiences(query="完全无关的查询")
        assert "刚做的 X" in result or "刚做的 Y" in result or "刚做的 Z" in result

    def test_empty_file_returns_empty(self, vault):
        assert vault.load_experiences(query="anything") == ""

    def test_max_cap(self, vault):
        entries = [(f"task_{i}", f"summary_{i}", [f"tag{i}"]) for i in range(20)]
        self._seed_promoted(vault, entries)
        result = vault.load_experiences(query="tag1 tag2 tag3 tag4 tag5 tag6 tag7 tag8 tag9 tag10 tag11")
        blocks = [b.strip() for b in result.split("\n---\n") if b.strip()]
        assert len(blocks) <= 10


# ---------------------------------------------------------------------------
# Skill I/O
# ---------------------------------------------------------------------------

class TestSkillOperations:

    def test_save_and_load_skill(self, vault):
        vault.save_skill(
            name="test_skill", goal="Do something", inputs=["param1"],
            steps=["step 1", "step 2"],
            code="def run(**kwargs):\n    return 'ok'",
            triggers=["when user asks to test"],
        )
        loaded = vault.load_skills()
        assert "test_skill" in loaded
        assert "Do something" in loaded
        assert "when user asks to test" in loaded

    def test_skill_without_triggers(self, vault):
        vault.save_skill(name="no_trigger", goal="Goal", inputs=["x"], steps=["s"])
        loaded = vault.load_skills()
        assert "no_trigger" in loaded
        assert "Triggers" not in loaded

    def test_skill_files_created(self, vault):
        vault.save_skill(name="my_skill", goal="g", inputs=[], steps=[],
                         code="def run(**kwargs): pass")
        skill_dir = vault.config.skills_path / "my_skill"
        assert (skill_dir / "skill.yaml").exists()
        assert (skill_dir / "executor.py").exists()


# ---------------------------------------------------------------------------
# Knowledge loading
# ---------------------------------------------------------------------------

class TestKnowledgeLoading:

    def test_load_axioms(self, vault):
        (vault.config.axioms_path / "test.md").write_text("Be rational.", encoding="utf-8")
        assert "Be rational" in vault.load_axioms()

    def test_load_empty_dir(self, vault):
        assert vault.load_axioms() == ""

    def test_load_all_context_keys(self, vault):
        ctx = vault.load_all_context(query="test")
        expected = {"axioms", "environment", "tools", "skills",
                    "protocols", "user_context", "experiences"}
        assert expected.issubset(set(ctx.keys()))
        assert set(ctx.keys()) - expected <= {"schedule"}

    def test_save_and_load_record(self, vault):
        path = vault.save_record("task", "process", "ok", notes="note")
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "task" in content
        assert "note" in content

    def test_load_environment(self, vault):
        env_dir = vault.config.environment_path
        env_dir.mkdir(parents=True, exist_ok=True)
        (env_dir / "internet.md").write_text("Search engines list", encoding="utf-8")
        result = vault.load_environment()
        assert "Search engines" in result

    def test_load_environment_empty(self, vault):
        assert vault.load_environment() == ""

    def test_load_tools_docs(self, vault):
        tools_dir = vault.config.tools_docs_path
        tools_dir.mkdir(parents=True, exist_ok=True)
        (tools_dir / "shell.md").write_text("Execute shell commands", encoding="utf-8")
        (tools_dir / "desktop_control.md").write_text("Control desktop apps", encoding="utf-8")
        result = vault.load_tools_docs()
        assert "shell" in result.lower()
        assert "desktop" in result.lower()

    def test_load_tools_docs_empty(self, vault):
        assert vault.load_tools_docs() == ""

    def test_load_protocols(self, vault):
        proto_dir = vault.config.protocols_path
        proto_dir.mkdir(parents=True, exist_ok=True)
        (proto_dir / "error_handling.md").write_text("Retry on failure", encoding="utf-8")
        result = vault.load_protocols()
        assert "Retry" in result

    def test_load_protocols_empty(self, vault):
        assert vault.load_protocols() == ""

    def test_load_user_context(self, vault):
        user_dir = vault.config.user_path
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "facts.md").write_text("Prefers Python", encoding="utf-8")
        result = vault.load_user_context()
        assert "Python" in result

    def test_load_user_context_empty(self, vault):
        assert vault.load_user_context() == ""


# ---------------------------------------------------------------------------
# User context writers
# ---------------------------------------------------------------------------

class TestUserContextWriters:

    def test_update_user_facts_appends(self, vault):
        user_dir = vault.config.user_path
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "facts.md").write_text(
            "# 用户客观事实与偏好 (Facts)\n\n1. likes Python\n", encoding="utf-8")

        vault.update_user_facts(["uses macOS", "prefers dark mode"])
        content = (user_dir / "facts.md").read_text(encoding="utf-8")
        assert "uses macOS" in content
        assert "prefers dark mode" in content
        assert "likes Python" in content

    def test_update_user_facts_deduplicates(self, vault):
        user_dir = vault.config.user_path
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "facts.md").write_text(
            "# Facts\n\n1. uses macOS\n", encoding="utf-8")

        vault.update_user_facts(["uses macOS", "new fact"])
        content = (user_dir / "facts.md").read_text(encoding="utf-8")
        assert content.count("uses macOS") == 1
        assert "new fact" in content

    def test_update_user_facts_skips_empty(self, vault):
        user_dir = vault.config.user_path
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "facts.md").write_text("# Facts\n", encoding="utf-8")

        vault.update_user_facts(["", "  "])
        content = (user_dir / "facts.md").read_text(encoding="utf-8")
        assert content.strip() == "# Facts"

    def test_update_user_goals(self, vault):
        vault.update_user_goals(["Build MONAD", "Launch product"])
        content = (vault.config.user_path / "goals.md").read_text(encoding="utf-8")
        assert "Build MONAD" in content
        assert "Launch product" in content

    def test_update_user_goals_empty_resets(self, vault):
        vault.update_user_goals([])
        content = (vault.config.user_path / "goals.md").read_text(encoding="utf-8")
        assert "暂无记录" in content

    def test_update_user_mood(self, vault):
        vault.update_user_mood("very excited about progress")
        content = (vault.config.user_path / "mood.md").read_text(encoding="utf-8")
        assert "very excited" in content
        assert "Updated:" in content

    def test_update_user_mood_empty_resets(self, vault):
        vault.update_user_mood("")
        content = (vault.config.user_path / "mood.md").read_text(encoding="utf-8")
        assert "暂无记录" in content


# ---------------------------------------------------------------------------
# Skill outputs field
# ---------------------------------------------------------------------------

class TestSkillOutputs:

    def test_save_skill_with_outputs(self, vault):
        import yaml
        vault.save_skill(
            name="test_skill", goal="test", inputs=["x"],
            steps=["do"], code="def run(**kw): pass",
            outputs={"result": "the result"}
        )
        yaml_path = vault.config.skills_path / "test_skill" / "skill.yaml"
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        assert data["outputs"] == {"result": "the result"}

    def test_load_skills_shows_outputs(self, vault):
        vault.save_skill(
            name="out_skill", goal="produce output", inputs=["x"],
            steps=["do"], code="def run(**kw): pass",
            outputs={"file_path": "生成文件路径"}
        )
        skills_text = vault.load_skills()
        assert "Outputs:" in skills_text
        assert "file_path" in skills_text

    def test_load_skills_no_outputs_no_line(self, vault):
        vault.save_skill(
            name="plain_skill", goal="plain", inputs=["x"],
            steps=["do"], code="def run(**kw): pass"
        )
        skills_text = vault.load_skills()
        assert "Outputs:" not in skills_text
