"""
MONAD Learning: Skill Builder
Automatically generates reusable skills from task execution patterns.
"""

import json
from monad.core.llm import llm_call
from monad.knowledge.vault import KnowledgeVault
from monad.interface.output import Output


SKILL_BUILDER_SYSTEM = """You are MONAD's Skill Builder module.
Your job is to analyze a completed task and determine if a reusable skill can be created from it.

You MUST return valid JSON and NOTHING else. No markdown, no extra text.

Return format:
{
  "should_create": true/false,
  "skill": {
    "name": "skill_name_in_snake_case",
    "goal": "What this skill accomplishes",
    "inputs": ["required_input_1", "required_input_2"],
    "steps": ["step1_description", "step2_description"],
    "code": "def run(**kwargs):\\n    # working Python code for this skill\\n    pass"
  },
  "reason": "Why this should/shouldn't become a skill"
}

Rules:
- Only create a skill if the task pattern is likely to be reused.
- Skill names must be snake_case.
- The code field should contain REAL, WORKING Python code based on what was actually executed.
- If the task is too specific or one-off, set should_create to false."""


class SkillBuilder:
    """Generates reusable skills from task execution patterns."""

    def __init__(self, vault: KnowledgeVault = None):
        self.vault = vault or KnowledgeVault()

    def evaluate_and_build(self, objective: dict, execution_result: dict) -> dict | None:
        """Evaluate if a task should become a skill, and build it if so."""
        if not execution_result.get("success"):
            Output.system("任务未成功，跳过技能评估")
            return None

        prompt = self._build_prompt(objective, execution_result)

        Output.system("正在调用 LLM 评估是否生成新技能...")
        try:
            response = llm_call(prompt, system=SKILL_BUILDER_SYSTEM, temperature=0.2)

            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            result = json.loads(cleaned)
        except Exception as e:
            Output.warn(f"技能评估失败: {str(e)}")
            return None

        reason = result.get("reason", "")
        if not result.get("should_create"):
            Output.system(f"评估结果: 不需要生成新技能 ({reason})")
            return None

        skill = result.get("skill", {})
        if not skill.get("name"):
            Output.warn("评估结果缺少技能名称，跳过")
            return None

        # Check if skill already exists
        existing = self.vault.load_skills()
        if skill["name"] in existing:
            Output.system(f"技能 '{skill['name']}' 已存在，跳过")
            return None

        # Save the skill
        Output.learning(f"正在保存新技能: {skill['name']}...")
        self.vault.save_skill(
            name=skill["name"],
            goal=skill.get("goal", ""),
            inputs=skill.get("inputs", []),
            steps=skill.get("steps", []),
            code=skill.get("code", ""),
        )

        Output.learning(f"🌱 新技能已创建: {skill['name']} — {skill.get('goal', '')}")
        return skill

    def _build_prompt(self, objective: dict, execution_result: dict) -> str:
        """Build skill evaluation prompt."""
        goal = objective.get("goal", "Unknown")
        steps = execution_result.get("steps", [])

        step_details = []
        for s in steps:
            step_details.append(f"  {s.get('action')}({s.get('description', '')})")

        return (
            f"Task completed successfully.\n\n"
            f"Goal: {goal}\n"
            f"Steps executed:\n" + "\n".join(step_details) + "\n\n"
            f"Should this task become a reusable skill?"
        )
