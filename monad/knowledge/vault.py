"""
MONAD Knowledge Vault
Reads and writes knowledge from/to the file system.
The file system IS the database.
"""

import os
import json
import yaml
from datetime import datetime
from pathlib import Path
from monad.config import CONFIG

PROMOTE_THRESHOLD = 3


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
        """Load system axioms (MONAD behavioral principles)."""
        return self._load_dir(self.config.axioms_path)

    def load_environment(self) -> str:
        """Load world knowledge."""
        return self._load_dir(self.config.environment_path)

    def load_tools_docs(self) -> str:
        """Load tool description documents."""
        return self._load_dir(self.config.tools_docs_path)

    def load_protocols(self) -> str:
        """Load behavioral protocols."""
        return self._load_dir(self.config.protocols_path)

    def load_user_context(self) -> str:
        """Load known user facts, moods, and preferences."""
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
            if yaml_path.exists():
                try:
                    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                    name = data.get("name", skill_dir.name)
                    goal = data.get("goal", "")
                    inputs = data.get("inputs", [])
                    steps = data.get("steps", [])
                    triggers = data.get("triggers", [])
                    entry = (
                        f"Skill: {name}\n"
                        f"  Goal: {goal}\n"
                        f"  Inputs: {', '.join(inputs)}\n"
                        f"  Steps: {' → '.join(steps)}"
                    )
                    if triggers:
                        entry += f"\n  Triggers: {'; '.join(triggers)}"
                    skills.append(entry)
                except Exception:
                    continue
        return "\n\n".join(skills)

    def load_experiences(self, query: str = "") -> str:
        """Load relevant experiences scored by relevance + recency.

        Scoring formula per entry:
          relevance  = number of overlapping keywords (direct + substring)
          recency    = position bonus (newer entries = higher index = more bonus)
          score      = relevance * 2 + recency

        Always includes the most recent RECENT_FALLBACK entries regardless of
        relevance. Failed experiences are excluded.

        Args:
            query: Current user request, used for relevance matching.
        """
        filepath = self.config.experiences_path / "accumulated_experiences.md"
        if not filepath.exists():
            return ""

        text = filepath.read_text(encoding="utf-8")
        blocks = text.split("\n---\n")

        entries = []  # (block_text, keywords_set)
        for block in blocks:
            stripped = block.strip()
            if not stripped or "[FAILED]" in stripped:
                continue
            keywords = set()
            for line in stripped.split("\n"):
                line_s = line.strip()
                if line_s.lower().startswith("tags:") or line_s.startswith("5."):
                    raw = line_s.split(":", 1)[-1] if ":" in line_s else line_s
                    for token in raw.replace("#", " ").replace("，", " ").replace(",", " ").split():
                        token = token.strip().lower()
                        if len(token) >= 2:
                            keywords.add(token)
                elif line_s.startswith("### 历史任务:"):
                    title = line_s.split(":", 1)[-1]
                    title = title.replace("[SUCCESS]", "").replace("[FAILED]", "").strip()
                    for token in title.lower().replace(",", " ").replace("，", " ").split():
                        token = token.strip()
                        if len(token) >= 2:
                            keywords.add(token)
            entries.append((stripped, keywords))

        if not entries:
            return ""

        MAX_EXPERIENCES = 10
        RECENT_FALLBACK = 3

        query_tokens = set()
        if query:
            for t in query.lower().replace(",", " ").replace("，", " ").split():
                t = t.strip()
                if len(t) >= 2:
                    query_tokens.add(t)

        total = len(entries)
        scored = []  # (index, score)
        for i, (block_text, keywords) in enumerate(entries):
            relevance = 0
            if query_tokens and keywords:
                relevance = len(query_tokens & keywords)
                if relevance == 0:
                    for qt in query_tokens:
                        for kw in keywords:
                            if qt in kw or kw in qt:
                                relevance += 1
                                break
            recency = (i + 1) / total  # 0→1, newest = 1
            score = relevance * 2 + recency
            scored.append((i, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_indices = {idx for idx, _ in scored[:MAX_EXPERIENCES - RECENT_FALLBACK]}

        recent_indices = set(range(max(0, total - RECENT_FALLBACK), total))

        selected = sorted(top_indices | recent_indices)[-MAX_EXPERIENCES:]

        return "\n\n---\n\n".join(entries[i][0] for i in selected)

    def load_all_context(self, query: str = "") -> dict:
        """Load all knowledge needed for Planner reasoning.

        Args:
            query: Current user request, passed to load_experiences()
                   for tag-based relevance filtering.
        """
        return {
            "axioms": self.load_axioms(),
            "environment": self.load_environment(),
            "tools": self.load_tools_docs(),
            "skills": self.load_skills(),
            "protocols": self.load_protocols(),
            "user_context": self.load_user_context(),
            "experiences": self.load_experiences(query=query),
        }

    # ── Write Operations ─────────────────────────────────────────

    def save_record(self, task: str, process: str, result: str, notes: str = "") -> Path:
        """Save a task execution experience log/record."""
        timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        # Sanitize task name for filename
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
        """Save experience to pending buffer; auto-promote when pattern recurs.

        New experiences land in pending.jsonl first. When the same tag pattern
        appears ≥ PROMOTE_THRESHOLD times, the latest entry is promoted to
        accumulated_experiences.md and the pending cluster is cleared.

        Failed experiences are stored with success=False and never promoted,
        preventing experience pollution.
        """
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

    def _try_promote(self, new_entry: dict, pending_path: Path, promoted_path: Path) -> bool:
        """Check if the new entry's tag cluster reaches promotion threshold."""
        new_tags = set(new_entry.get("tags", []))
        if not new_tags:
            return False

        pending = self._read_pending(pending_path)
        similar = [e for e in pending if e.get("success") and
                   new_tags & set(e.get("tags", []))]

        if len(similar) < PROMOTE_THRESHOLD:
            return False

        best = similar[-1]
        status_tag = "[SUCCESS]"
        tag_line = ""
        if best.get("tags"):
            tag_line = f"\nTags: {' '.join('#' + t for t in best['tags'])}\n"
        date_line = f"Date: {datetime.now().strftime('%Y-%m-%d')}\n"
        content = f"### 历史任务: {best['task']} {status_tag}\n{date_line}{best['summary']}{tag_line}\n\n---\n\n"
        with open(promoted_path, "a", encoding="utf-8") as f:
            f.write(content)

        self._purge_cluster(new_tags, pending_path)
        return True

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
        pending_path.write_text("\n".join(remaining) + "\n" if remaining else "",
                                encoding="utf-8")

    def save_skill(self, name: str, goal: str, inputs: list, steps: list,
                   code: str = "", triggers: list = None,
                   dependencies: dict = None) -> Path:
        """Save a new skill to the skill tree."""
        skill_dir = self.config.skills_path / name
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
        yaml_path = skill_dir / "skill.yaml"
        yaml_path.write_text(yaml.dump(skill_data, allow_unicode=True, default_flow_style=False), encoding="utf-8")

        # Save executor.py if code provided
        if code:
            exec_path = skill_dir / "executor.py"
            exec_path.write_text(code, encoding="utf-8")

        return skill_dir

    def save_to_cache(self, key: str, content: str) -> Path:
        """Save temporary task results to cache."""
        filepath = self.config.cache_path / f"{key}.md"
        filepath.write_text(content, encoding="utf-8")
        return filepath
