"""
MONAD Knowledge Vault
Reads and writes knowledge from/to the file system.
The file system IS the database.
"""

import json
import yaml
from datetime import datetime
from pathlib import Path

import jieba

from monad.cognition.parser import parse_tags
from monad.config import CONFIG, PROMOTE_THRESHOLD, MAX_EXPERIENCES, RECENT_FALLBACK


class KnowledgeVault:
    """Knowledge read/write engine for MONAD."""

    def __init__(self, config=None):
        self.config = config or CONFIG
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Create knowledge directories if they don't exist."""
        dirs = [
            self.config.axioms_path,
            self.config.environment_path,
            self.config.tools_docs_path,
            self.config.skills_path,
            self.config.protocols_path,
            self.config.user_path,
            self.config.experiences_path,
            self.config.records_path,
            self.config.cache_path,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    # ── Read Operations ──────────────────────────────────────────

    def _load_dir(self, path: Path) -> str:
        """Load and concatenate all .md files in a directory."""
        contents = []
        if not path.exists():
            return ""
        for f in sorted(path.glob("*.md")):
            text = f.read_text(encoding="utf-8").strip()
            if text:
                contents.append(f"### {f.stem}\n\n{text}")
        return "\n\n---\n\n".join(contents)

    def load_axioms(self) -> str:
        return self._load_dir(self.config.axioms_path)

    def load_environment(self) -> str:
        return self._load_dir(self.config.environment_path)

    def load_tools_docs(self) -> str:
        return self._load_dir(self.config.tools_docs_path)

    def load_protocols(self) -> str:
        return self._load_dir(self.config.protocols_path)

    def load_user_context(self) -> str:
        return self._load_dir(self.config.user_path)

    def load_skills(self) -> str:
        """Load available skills as a formatted string."""
        skills_path = self.config.skills_path
        if not skills_path.exists():
            return ""

        skills = []
        for skill_dir in sorted(skills_path.iterdir()):
            if not skill_dir.is_dir():
                continue
            yaml_path = skill_dir / "skill.yaml"
            if not yaml_path.exists():
                continue
            try:
                data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                name = data.get("name", skill_dir.name)
                goal = data.get("goal", "")
                inputs = data.get("inputs", [])
                steps = data.get("steps", [])
                triggers = data.get("triggers", [])
                outputs = data.get("outputs", {})
                composition = data.get("composition")
                tag = " [composite]" if isinstance(composition, dict) and composition else ""
                entry = (
                    f"Skill: {name}{tag}\n"
                    f"  Goal: {goal}\n"
                    f"  Inputs: {', '.join(inputs)}\n"
                    f"  Steps: {' → '.join(steps)}"
                )
                if outputs and isinstance(outputs, dict):
                    out_parts = [f"{k}: {v}" for k, v in outputs.items()]
                    entry += f"\n  Outputs: {'; '.join(out_parts)}"
                if triggers:
                    entry += f"\n  Triggers: {'; '.join(triggers)}"
                skills.append(entry)
            except Exception:
                continue
        return "\n\n".join(skills)

    def load_experiences(self, query: str = "") -> str:
        """Load relevant experiences scored by relevance + recency.

        Scoring: relevance * 2 + recency (keyword overlap + timestamp).
        Always includes the most recent RECENT_FALLBACK entries.
        Failed experiences are excluded.
        """
        filepath = self.config.experiences_path / "accumulated_experiences.md"
        if not filepath.exists():
            return ""

        text = filepath.read_text(encoding="utf-8")
        blocks = text.split("\n---\n")

        entries = []
        for block in blocks:
            stripped = block.strip()
            if not stripped or "[FAILED]" in stripped:
                continue
            keywords = self._extract_keywords(stripped)
            entries.append((stripped, keywords))

        if not entries:
            return ""

        query_tokens = self._tokenize(query)
        total = len(entries)
        scored = []
        for i, (block_text, keywords) in enumerate(entries):
            relevance = self._compute_relevance(query_tokens, keywords)
            recency = (i + 1) / total
            scored.append((i, relevance * 2 + recency))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_indices = {idx for idx, _ in scored[:MAX_EXPERIENCES - RECENT_FALLBACK]}
        recent_indices = set(range(max(0, total - RECENT_FALLBACK), total))
        selected = sorted(top_indices | recent_indices)[-MAX_EXPERIENCES:]

        return "\n\n---\n\n".join(entries[i][0] for i in selected)

    def load_all_context(self, query: str = "") -> dict:
        """Load all knowledge needed for reasoning."""
        from monad.knowledge.schedule import read_today_schedule

        ctx = {
            "axioms": self.load_axioms(),
            "environment": self.load_environment(),
            "tools": self.load_tools_docs(),
            "skills": self.load_skills(),
            "protocols": self.load_protocols(),
            "user_context": self.load_user_context(),
            "experiences": self.load_experiences(query=query),
        }
        schedule = read_today_schedule()
        if schedule:
            ctx["schedule"] = schedule
        return ctx

    # ── Write Operations ─────────────────────────────────────────

    def save_record(self, task: str, process: str, result: str,
                    notes: str = "") -> Path:
        """Save a task execution record."""
        timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in task)
        safe_name = safe_name.strip().replace(" ", "_")[:50]
        filename = f"{timestamp}_{safe_name}.md"
        filepath = self.config.records_path / filename

        content = (
            f"# Task Record\n\n"
            f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"## Task\n{task}\n\n"
            f"## Process\n{process}\n\n"
            f"## Result\n{result}\n\n"
        )
        if notes:
            content += f"## Notes\n{notes}\n"

        filepath.write_text(content, encoding="utf-8")
        return filepath

    def save_experience(self, query: str, reflection: str, success: bool = True,
                        tags: list = None) -> Path:
        """Save experience to pending buffer; auto-promote when pattern recurs."""
        pending_path = self.config.experiences_path / "pending.jsonl"
        promoted_path = self.config.experiences_path / "accumulated_experiences.md"

        entry = {
            "task": query,
            "summary": reflection,
            "tags": tags or [],
            "success": success,
            "ts": datetime.now().isoformat(),
        }

        with open(pending_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        if not success:
            return pending_path

        promoted = self._try_promote(entry, pending_path, promoted_path)
        return promoted_path if promoted else pending_path

    def _try_promote(self, new_entry: dict, pending_path: Path,
                     promoted_path: Path) -> bool:
        """Check if the new entry's tag cluster reaches promotion threshold."""
        new_tags = set(new_entry.get("tags", []))
        if not new_tags:
            return False

        pending = self._read_pending(pending_path)
        similar = [e for e in pending if e.get("success") and
                   new_tags & set(e.get("tags", []))]

        if len(similar) < PROMOTE_THRESHOLD:
            return False

        best = max(similar, key=lambda e: len(e.get("tags", [])) + len(e.get("summary", "")))
        tag_line = ""
        if best.get("tags"):
            tag_line = f"\nTags: {' '.join('#' + t for t in best['tags'])}\n"
        date_line = f"Date: {datetime.now().strftime('%Y-%m-%d')}\n"
        content = (
            f"### 历史任务: {best['task']} [SUCCESS]\n"
            f"{date_line}{best['summary']}{tag_line}\n\n---\n\n"
        )
        with open(promoted_path, "a", encoding="utf-8") as f:
            f.write(content)

        self._purge_cluster(new_tags, pending_path)
        return True

    def save_skill(self, name: str, goal: str, inputs: list, steps: list,
                   code: str = "", triggers: list = None,
                   dependencies: dict = None,
                   composition: dict | None = None,
                   outputs: dict | None = None) -> Path:
        """Save a new skill to the skill tree."""
        skill_dir = self.config.skill_dir(name)
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_data = {
            "name": name,
            "goal": goal,
            "inputs": inputs,
            "steps": steps,
        }
        if triggers:
            skill_data["triggers"] = triggers
        if dependencies:
            skill_data["dependencies"] = dependencies
        if composition:
            skill_data["composition"] = composition
        if outputs:
            skill_data["outputs"] = outputs
        yaml_path = skill_dir / "skill.yaml"
        yaml_path.write_text(
            yaml.dump(skill_data, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )

        if code:
            exec_path = skill_dir / "executor.py"
            exec_path.write_text(code, encoding="utf-8")

        return skill_dir

    # ── User Context Writers ────────────────────────────────────

    def update_user_facts(self, new_facts: list[str]) -> Path:
        """Append new facts to user/facts.md, deduplicating against existing."""
        path = self.config.user_path / "facts.md"
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        existing_lower = existing.lower()
        added = []
        idx = len(existing.strip().split("\n"))
        for fact in new_facts:
            fact = fact.strip()
            if not fact or fact.lower() in existing_lower:
                continue
            idx += 1
            added.append(f"{idx}. {fact}")
        if added:
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n" + "\n".join(added) + "\n")
        return path

    def update_user_goals(self, new_goals: list[str]) -> Path:
        """Rewrite user/goals.md with the provided goals list."""
        path = self.config.user_path / "goals.md"
        header = "# 用户当前目标与长期项目 (Goals)\n\n"
        body = "\n".join(f"- {g.strip()}" for g in new_goals if g.strip())
        if not body:
            body = "（暂无记录。当用户提到正在进行的重要项目或长期目标时，记录于此以保持上下文连贯。）"
        path.write_text(header + body + "\n", encoding="utf-8")
        return path

    def update_user_mood(self, mood: str) -> Path:
        """Overwrite user/mood.md with the current mood snapshot."""
        path = self.config.user_path / "mood.md"
        header = "# 用户当前状态与心情 (Mood/State)\n\n"
        body = mood.strip() if mood.strip() else "（暂无记录。当用户表达心情、感受或当前所处的临时状态时，记录于此。）"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        path.write_text(f"{header}{body}\n\n_Updated: {ts}_\n", encoding="utf-8")
        return path

    def save_to_cache(self, key: str, content: str) -> Path:
        """Save temporary task results to cache."""
        filepath = self.config.cache_path / f"{key}.md"
        filepath.write_text(content, encoding="utf-8")
        return filepath

    # ── Private Helpers ──────────────────────────────────────────

    @staticmethod
    def _extract_keywords(block: str) -> set:
        """Extract keyword set from an experience block."""
        keywords = set()
        tags = parse_tags(block)
        if tags:
            keywords.update(KnowledgeVault._tokenize(" ".join(tags)))
        for line in block.split("\n"):
            line_s = line.strip()
            if line_s.startswith("### 历史任务:"):
                title = line_s.split(":", 1)[-1]
                title = title.replace("[SUCCESS]", "").replace("[FAILED]", "").strip()
                keywords.update(KnowledgeVault._tokenize(title))
        return keywords

    @staticmethod
    def _tokenize(text: str) -> set:
        """Segment text into normalized tokens using jieba for Chinese support."""
        if not text:
            return set()
        cleaned = text.replace("#", " ").replace(",", " ").replace("，", " ")
        return {t.lower() for t in jieba.cut(cleaned) if len(t.strip()) >= 2}

    @staticmethod
    def _compute_relevance(query_tokens: set, keywords: set) -> int:
        """Compute keyword overlap relevance score."""
        if not query_tokens or not keywords:
            return 0
        relevance = len(query_tokens & keywords)
        if relevance == 0:
            for qt in query_tokens:
                for kw in keywords:
                    if qt in kw or kw in qt:
                        relevance += 1
                        break
        return relevance

    @staticmethod
    def _read_pending(path: Path) -> list:
        if not path.exists():
            return []
        entries = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries

    @staticmethod
    def _purge_cluster(tags: set, pending_path: Path):
        """Remove entries whose tags overlap with the promoted cluster."""
        remaining = []
        for line in pending_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                remaining.append(line)
                continue
            if tags & set(entry.get("tags", [])):
                continue
            remaining.append(line)
        pending_path.write_text(
            "\n".join(remaining) + "\n" if remaining else "",
            encoding="utf-8",
        )
