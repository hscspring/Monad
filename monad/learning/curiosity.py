"""
MONAD Learning: Curiosity Engine
Targeted self-improvement: researches solutions for identified weaknesses
and applies updates to skills and protocols.

Every learning session must produce a concrete skill or protocol change.
No knowledge accumulation for its own sake.
"""

import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from monad.cognition.parser import clean_llm_output
from monad.config import CONFIG, DAILY_LEARNING_BUDGET, truncate
from monad.core.llm import llm_call
from monad.interface.output import Output
from monad.knowledge.vault import KnowledgeVault

RESEARCH_SYSTEM = """You are MONAD's Curiosity Engine — a targeted self-improvement module.

Given a specific improvement objective (from self-evaluation), you must:
1. Determine what information to search for on the web
2. Produce a concrete update to either a skill or a protocol

You will be given:
- The improvement objective (what to fix)
- Research results from web_fetch (web content)
- The current skill/protocol code (if updating existing)

Return valid JSON only:
{
  "search_query": "What to search for on the web (for the first call)",
  "action": "skill_update" or "protocol_update" or "new_protocol",
  "target": "skill or protocol name",
  "code": "Updated Python code for skill executor.py (if skill_update)",
  "content": "Updated markdown content (if protocol_update or new_protocol)",
  "summary": "One-sentence description of what was improved"
}

Rules:
- The update must be SPECIFIC and ACTIONABLE — real code or real protocol text
- For skill updates: provide complete, working executor.py code with def run(**kwargs)
- For protocol updates: provide complete markdown content
- Do NOT produce vague suggestions — produce actual code/content changes
- If the research is insufficient to produce a concrete fix, set action to "skip"
"""

_STATE_FILE = "curiosity_state.json"


class CuriosityEngine:
    """Researches solutions for capability gaps and applies skill/protocol updates."""

    def __init__(self, vault: KnowledgeVault = None, execute_fn=None):
        self.vault = vault or KnowledgeVault()
        self.execute_fn = execute_fn

    def run_session(self, eval_report: dict | None = None) -> str | None:
        """Run one self-improvement session.

        Args:
            eval_report: Output from SelfEvaluator.evaluate().

        Returns:
            Summary of improvements made, or None if nothing was improved.
        """
        if not self._check_budget():
            Output.system("今日自主学习预算已用完")
            return None

        objectives = self._get_objectives(eval_report)
        if not objectives:
            Output.system("无改进目标，跳过自主学习")
            return None

        improvements = []
        for obj in objectives[:2]:
            result = self._research_and_improve(obj)
            if result:
                improvements.append(result)

        self._increment_budget()

        if improvements:
            summary = "; ".join(improvements)
            Output.learning(f"自我改进完成: {summary}")
            return summary
        return None

    def _get_objectives(self, eval_report: dict | None) -> list[dict]:
        """Extract improvement objectives from self-evaluation report."""
        if not eval_report:
            return []
        weak_areas = eval_report.get("weak_areas", [])
        return [
            wa.get("improvement", {})
            for wa in weak_areas
            if wa.get("improvement", {}).get("objective")
        ]

    def _research_and_improve(self, objective: dict) -> str | None:
        """Research a single improvement objective and apply the fix."""
        obj_type = objective.get("type", "")
        target = objective.get("target", "")
        research_goal = objective.get("objective", "")

        Output.learning(f"研究目标: {research_goal}")

        research_content = self._do_research(research_goal)
        if not research_content:
            return None

        current_code = ""
        if obj_type == "skill_update" and target:
            current_code = self._load_skill_code(target)

        current_protocol = ""
        if obj_type == "protocol_update" and target:
            current_protocol = self._load_protocol(target)

        prompt = self._build_improve_prompt(
            objective, research_content, current_code, current_protocol
        )

        try:
            raw = llm_call(prompt, system=RESEARCH_SYSTEM, temperature=0.2)
            plan = json.loads(clean_llm_output(raw))
        except Exception as e:
            logger.warning(f"Curiosity LLM call failed: {e}")
            return None

        action = plan.get("action", "skip")
        if action == "skip":
            Output.system(f"研究结果不足以产生具体改进，跳过: {target}")
            return None

        return self._apply_improvement(plan)

    def _do_research(self, goal: str) -> str:
        """Use web_fetch to research a topic."""
        if not self.execute_fn:
            return ""
        try:
            search_url = f"https://www.google.com/search?q={goal.replace(' ', '+')}"
            result = self.execute_fn("web_fetch", url=search_url, mode="fast")
            return truncate(result, 4000)
        except Exception as e:
            logger.warning(f"Research web_fetch failed: {e}")
            return ""

    def _load_skill_code(self, skill_name: str) -> str:
        """Load current executor.py for a skill."""
        path = CONFIG.skill_dir(skill_name) / "executor.py"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def _load_protocol(self, protocol_name: str) -> str:
        """Load current protocol content."""
        path = CONFIG.protocols_path / f"{protocol_name}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def _build_improve_prompt(self, objective: dict, research: str,
                              current_code: str, current_protocol: str) -> str:
        parts = [
            f"Improvement Objective: {objective.get('objective', '')}",
            f"Type: {objective.get('type', '')}",
            f"Target: {objective.get('target', '')}",
            "",
            f"=== Research Results ===\n{research}",
        ]
        if current_code:
            parts.append(f"\n=== Current Skill Code ===\n```python\n{current_code}\n```")
        if current_protocol:
            parts.append(f"\n=== Current Protocol ===\n{current_protocol}")
        parts.append(
            "\nBased on the research, produce a CONCRETE update. "
            "Return valid JSON with the improved code or protocol content."
        )
        return "\n".join(parts)

    def _apply_improvement(self, plan: dict) -> str | None:
        """Apply the improvement plan to the filesystem."""
        action = plan.get("action", "")
        target = plan.get("target", "")
        summary = plan.get("summary", "")

        if action == "skill_update" and target:
            code = plan.get("code", "")
            if code and "def run" in code:
                skill_dir = CONFIG.skill_dir(target)
                if skill_dir.exists():
                    exec_path = skill_dir / "executor.py"
                    exec_path.write_text(code, encoding="utf-8")
                    Output.learning(f"技能已更新: {target}")
                    return f"skill_update: {target} — {summary}"
                else:
                    Output.warn(f"目标技能 {target} 不存在，跳过更新")
                    return None

        if action in ("protocol_update", "new_protocol") and target:
            content = plan.get("content", "")
            if content:
                path = CONFIG.protocols_path / f"{target}.md"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                Output.learning(f"协议已更新: {target}")
                return f"protocol_update: {target} — {summary}"

        return None

    def _check_budget(self) -> bool:
        """Check if daily learning budget is available."""
        state = self._load_state()
        today = datetime.now().strftime("%Y-%m-%d")
        if state.get("date") != today:
            return True
        return state.get("sessions", 0) < DAILY_LEARNING_BUDGET

    def _increment_budget(self) -> None:
        """Increment today's session counter."""
        state = self._load_state()
        today = datetime.now().strftime("%Y-%m-%d")
        if state.get("date") != today:
            state = {"date": today, "sessions": 0}
        state["sessions"] = state.get("sessions", 0) + 1
        self._save_state(state)

    def _load_state(self) -> dict:
        path = CONFIG.cache_path / _STATE_FILE
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_state(self, state: dict) -> None:
        path = CONFIG.cache_path / _STATE_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state), encoding="utf-8")
