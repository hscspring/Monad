"""
MONAD Personalizer
Extracts user facts, goals, and mood from task interactions.
Updates user knowledge files for long-term adaptation.
"""

import json

from loguru import logger

from monad.cognition.parser import clean_llm_output
from monad.cognition.prompts import PERSONALIZATION_SYSTEM
from monad.config import TRUNCATE_LONG, truncate
from monad.core.llm import llm_call
from monad.interface.output import Output


class Personalizer:
    """Post-task user learning: extracts and persists user context."""

    def __init__(self, vault):
        self.vault = vault

    def extract_and_update(self, user_input: str, exec_result: dict) -> dict | None:
        """Analyze a completed task and update user knowledge files.

        Returns the extracted dict on success, None on failure or no-op.
        """
        prompt = (
            f"用户输入：\n{truncate(user_input, TRUNCATE_LONG)}\n\n"
            f"执行摘要：\n{truncate(exec_result.get('answer', ''), TRUNCATE_LONG)}"
        )

        try:
            raw = llm_call(prompt, system=PERSONALIZATION_SYSTEM, temperature=0.3)
        except Exception as e:
            logger.warning(f"Personalization LLM call failed: {e}")
            return None

        parsed = self._parse(raw)
        if parsed is None:
            return None

        changes = self._apply(parsed)
        if changes:
            Output.system(f"个性化学习: {', '.join(changes)}")
        return parsed

    def _parse(self, raw: str) -> dict | None:
        cleaned = clean_llm_output(raw)
        try:
            data = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            logger.debug(f"Personalization parse failed: {raw[:200]}")
            return None

        if not isinstance(data, dict):
            return None

        facts = data.get("facts", [])
        goals = data.get("goals", [])
        mood = data.get("mood", "")

        if not facts and not goals and not mood:
            return None

        return {"facts": facts, "goals": goals, "mood": mood}

    def _apply(self, data: dict) -> list[str]:
        """Write extracted data to vault. Returns list of what changed."""
        changes = []

        facts = data.get("facts", [])
        if facts and isinstance(facts, list):
            self.vault.update_user_facts(facts)
            changes.append(f"{len(facts)} 条新事实")

        goals = data.get("goals", [])
        if goals and isinstance(goals, list):
            self.vault.update_user_goals(goals)
            changes.append(f"{len(goals)} 个目标更新")

        mood = data.get("mood", "")
        if mood and isinstance(mood, str):
            self.vault.update_user_mood(mood)
            changes.append("心情已更新")

        return changes
