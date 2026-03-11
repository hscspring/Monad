"""
MONAD Knowledge Vault
Reads and writes knowledge from/to the file system.
The file system IS the database.
"""

import os
import yaml
from datetime import datetime
from pathlib import Path
from monad.config import CONFIG


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
        """Load relevant experiences by tag matching, filtering out failed ones.

        Uses keyword overlap between the user query and experience tags
        to select relevant past experiences. Always includes the most
        recent few as fallback context.

        Args:
            query: Current user request, used for relevance matching.
        """
        filepath = self.config.experiences_path / "accumulated_experiences.md"
        if not filepath.exists():
            return ""

        text = filepath.read_text(encoding="utf-8")
        blocks = text.split("\n---\n")

        # Parse all successful blocks with their tags + title keywords
        entries = []  # (block_text, keywords_set)
        for block in blocks:
            stripped = block.strip()
            if not stripped or "[FAILED]" in stripped:
                continue
            keywords = set()
            for line in stripped.split("\n"):
                line_s = line.strip()
                # Extract from Tags line
                if line_s.lower().startswith("tags:") or line_s.startswith("5."):
                    raw = line_s.split(":", 1)[-1] if ":" in line_s else line_s
                    for token in raw.replace("#", " ").replace("，", " ").replace(",", " ").split():
                        token = token.strip().lower()
                        if len(token) >= 2:
                            keywords.add(token)
                # Extract from title line (e.g. "### 历史任务: 分析 kexue.fm [SUCCESS]")
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

        # Tokenize query for matching
        query_tokens = set()
        if query:
            for t in query.lower().replace(",", " ").replace("，", " ").split():
                t = t.strip()
                if len(t) >= 2:
                    query_tokens.add(t)

        # Score each entry: keyword overlap + substring match
        matched = []
        for i, (block_text, keywords) in enumerate(entries):
            if not query_tokens or not keywords:
                continue
            overlap = query_tokens & keywords
            if not overlap:
                for qt in query_tokens:
                    for kw in keywords:
                        if qt in kw or kw in qt:
                            overlap = {qt}
                            break
                    if overlap:
                        break
            if overlap:
                matched.append(i)

        # Always include the most recent N as fallback
        recent_indices = set(range(max(0, len(entries) - RECENT_FALLBACK), len(entries)))

        # Combine: matched + recent, deduplicated, capped
        selected_indices = sorted(set(matched) | recent_indices)
        selected_indices = selected_indices[-MAX_EXPERIENCES:]

        result = [entries[i][0] for i in selected_indices]
        return "\n\n---\n\n".join(result)

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
        """Save a concise experience (Query + Reflection) for future context.

        Args:
            query: The original user request
            reflection: LLM-generated reflection summary
            success: Whether the task succeeded. Failed experiences are
                     tagged [FAILED] and excluded from future reasoning
                     context to prevent experience pollution.
            tags: Keywords for relevance matching on future loads.
        """
        filepath = self.config.experiences_path / "accumulated_experiences.md"
        status_tag = "[SUCCESS]" if success else "[FAILED]"
        tag_line = ""
        if tags:
            tag_line = f"\nTags: {' '.join('#' + t for t in tags)}\n"
        content = f"### 历史任务: {query} {status_tag}\n{reflection}{tag_line}\n\n---\n\n"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def save_skill(self, name: str, goal: str, inputs: list, steps: list,
                   code: str = "", triggers: list = None) -> Path:
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
