"""
MONAD Learning: Skill Builder
Automatically generates reusable skills from task execution patterns.
Supports both creating new skills and updating existing ones when overlap is detected.
"""

import json
import tempfile
from pathlib import Path

from loguru import logger

from monad.config import truncate
from monad.core.llm import llm_call
from monad.interface.output import Output
from monad.knowledge.vault import KnowledgeVault

_SKILL_PARAM_PREVIEW = 2000
_SKILL_RESULT_PREVIEW = 4000

SKILL_BUILDER_SYSTEM = """You are MONAD's Skill Builder module.
Your job is to analyze a completed task and determine:
1. Whether a reusable skill should be saved.
2. Whether an EXISTING skill already covers this — if so, update it instead of creating a new one.

You will be given the task details AND a list of existing skills.

You MUST return valid JSON and NOTHING else. No markdown, no extra text.

Return ONE of these formats:

Option A — No skill needed:
{"action": "skip", "reason": "Why no skill is needed"}

Option B — Update an existing skill (PREFERRED when there's overlap):
{"action": "update", "target": "existing_skill_name", "reason": "Why this existing skill should be updated",
 "skill": {"goal": "updated goal description", "inputs": ["param1"], "steps": ["step1"], "triggers": ["trigger1"],
            "code": "def run(**kwargs):\\n    # updated working Python code\\n    pass"}}

Option C — Create a new skill (ONLY when no existing skill is related):
{"action": "create", "reason": "Why a new skill is needed",
 "skill": {"name": "skill_name_in_snake_case", "goal": "What this skill accomplishes",
            "inputs": ["param1"], "steps": ["step1"], "triggers": ["trigger1"],
            "code": "def run(**kwargs):\\n    # working Python code\\n    pass"}}

Option D — Composite skill (orchestration only, v0.5+): chain existing skills with the same kwargs:
{"action": "create", "reason": "...",
 "skill": {"name": "my_pipeline", "goal": "...", "inputs": ["q"], "steps": ["run A then B"],
            "composition": {"sequence": ["skill_a", "skill_b"]},
            "code": ""}}

Use composition ONLY when the task is clearly a deterministic pipeline of existing skills; leave code empty and list sub-skills in order.

Rules:
- ALWAYS prefer "update" over "create" when an existing skill has overlapping functionality.
- Only use "create" when the task pattern is reusable AND no existing skill is even remotely related.
- Skill names must be snake_case and GENERAL (e.g. "web_to_markdown" not "convert_wechat_article_to_markdown").
- The code field must contain REAL, WORKING Python code based on what was actually executed.
- If the task is too specific or one-off, use "skip".

IMPORTANT — when to SKIP (do NOT create skills for these):
- Analyzing a SPECIFIC person, website, or entity (e.g. "分析 yam.gift 博主" → skip, because the analysis content is unique each time and cannot be hardcoded)
- Tasks where the core value is LLM reasoning/analysis, not repeatable code logic
- Any skill that would need to hardcode analysis results, advice, or conclusions — that's a hollow skill
- **Desktop automation tasks** (e.g. sending messages via Feishu/WeChat/Lark, clicking UI elements): these require real-time visual feedback loops (screenshot → analyze → decide) that CANNOT be pre-scripted. The LLM reasoning loop with desktop_control handles these dynamically. A skill with hardcoded sleep() + click sequences is ALWAYS hollow.

Code quality requirements:
- For analysis/report tasks: the code MUST call web_fetch() or shell() to fetch real data, and MUST use LLM to generate analysis — NEVER hardcode analysis text
- For PDF tasks: MUST register CJK fonts (UnicodeCIDFont('STSong-Light')) for Chinese support
- MUST save output to MONAD_OUTPUT_DIR, not to the home directory or current directory
- MUST use injected tools (web_fetch, shell) instead of importing requests directly
- NEVER create skills that call desktop_control() in a fixed sequence — desktop automation needs adaptive LLM reasoning"""


class SkillBuilder:
    """Generates reusable skills from task execution patterns."""

    def __init__(self, vault: KnowledgeVault = None):
        self.vault = vault or KnowledgeVault()

    def evaluate_and_build(self, objective: dict, execution_result: dict) -> dict | None:
        """Evaluate if a task should become a skill, and build it if so."""
        if not execution_result.get("success"):
            Output.system("任务未成功，跳过技能评估")
            return None

        existing_skills = self.vault.load_skills()
        prompt = self._build_prompt(objective, execution_result, existing_skills)

        Output.system("正在调用 LLM 评估是否生成新技能...")
        try:
            response = llm_call(prompt, system=SKILL_BUILDER_SYSTEM, temperature=0.2)
            result = _parse_json_response(response)
        except Exception as e:
            logger.warning(f"Skill evaluation failed: {e}")
            Output.warn(f"技能评估失败: {str(e)}")
            return None

        action = result.get("action", "skip")
        reason = result.get("reason", "")

        if action == "skip":
            Output.system(f"评估结果: 不需要生成新技能 ({reason})")
            return None
        if action == "update":
            return self._handle_update(result)
        if action == "create":
            return self._handle_create(result)

        Output.warn(f"未知的技能评估动作: {action}")
        return None

    def _handle_update(self, result: dict) -> dict | None:
        """Update an existing skill with improved code."""
        target = result.get("target", "")
        skill = result.get("skill", {})
        reason = result.get("reason", "")

        if not target:
            Output.warn("评估要求更新技能但未指定目标，跳过")
            return None

        code = skill.get("code", "") or ""
        if not self._validate_skill_code(code, skill):
            return None

        Output.learning(f"正在更新已有技能: {target} ({reason})")
        self._save_skill_from_dict(target, skill, code)
        Output.learning(f"♻️ 技能已更新: {target}")
        return {"name": target, "updated": True, **skill}

    def _handle_create(self, result: dict) -> dict | None:
        """Create a brand-new skill."""
        skill = result.get("skill", {})
        name = skill.get("name", "")

        if not name:
            Output.warn("评估结果缺少技能名称，跳过")
            return None

        code = skill.get("code", "") or ""
        if not self._validate_skill_code(code, skill):
            return None

        Output.learning(f"正在保存新技能: {name}...")
        self._save_skill_from_dict(name, skill, code)
        Output.learning(f"🌱 新技能已创建: {name} — {skill.get('goal', '')}")
        return skill

    def _validate_skill_code(self, code: str, skill: dict) -> bool:
        """Review + smoke-test code, or verify composition. Returns True if valid."""
        composition = skill.get("composition")
        if code and "def run" in code:
            passed, review = self._review_code(code, skill.get("goal", ""))
            if not passed:
                Output.warn(f"技能代码质量不过关: {review}")
                return False
            ok, smoke = self._smoke_run_skill_code(code, skill.get("inputs", []))
            if not ok:
                Output.warn(f"技能代码未通过执行烟测: {smoke}")
                return False
            return True
        if composition:
            Output.system("组合技能 (composition)：跳过代码审阅与烟测")
            return True
        Output.warn("技能代码缺少 run() 且无 composition，跳过")
        return False

    def _save_skill_from_dict(self, name: str, skill: dict, code: str) -> None:
        """Persist a skill to vault from the LLM response dict."""
        self.vault.save_skill(
            name=name,
            goal=skill.get("goal", ""),
            inputs=skill.get("inputs", []),
            steps=skill.get("steps", []),
            code=code,
            triggers=skill.get("triggers"),
            dependencies=skill.get("dependencies"),
            composition=skill.get("composition"),
        )

    @staticmethod
    def _review_code(code: str, goal: str) -> tuple[bool, str]:
        """Use LLM to review generated skill code quality.

        Returns (passed, reason). Fail-open on LLM errors.
        """
        prompt = f"""Review this auto-generated skill code for quality issues.

Goal: {goal}

```python
{code}
```

Check for these problems:
1. Hardcoded results — does the code contain hardcoded analysis text, advice, or conclusions instead of dynamically generating them (via web_fetch + LLM)?
2. Missing CJK fonts — if it generates PDFs with reportlab, does it register a CJK font (e.g. UnicodeCIDFont, TTFont) for Chinese text?
3. Wrong output path — does it save files to MONAD_OUTPUT_DIR (injected variable), or does it incorrectly fall back to home directory / current directory?
4. Bypassing injected tools — does it `import requests` directly instead of using the injected `web_fetch()` function?
5. Hollow logic — does the core logic actually accomplish the goal, or is it just a template that returns canned text?
6. Desktop automation anti-pattern — does the code call desktop_control() in a hardcoded sequence with time.sleep()? Desktop UI automation requires real-time visual feedback (screenshot → analyze → decide) that cannot be pre-scripted. Such skills are ALWAYS hollow.

Return JSON only:
{{"pass": true/false, "reason": "one-sentence explanation if failed, empty string if passed"}}"""

        try:
            response = llm_call(prompt, system="You are a code reviewer. Return valid JSON only.", temperature=0)
            result = _parse_json_response(response)
            return result.get("pass", True), result.get("reason", "")
        except Exception:
            return True, ""

    @staticmethod
    def _smoke_run_skill_code(code: str, inputs: list) -> tuple[bool, str]:
        """Execute skill code in an isolated namespace with stub tools (smoke test)."""
        tmp = Path(tempfile.mkdtemp(prefix="monad_skill_smoke_"))
        ns: dict = {
            "__builtins__": __builtins__,
            "MONAD_OUTPUT_DIR": str(tmp),
        }

        def _stub(**_kwargs) -> str:
            return "[stub_ok]"

        ns["web_fetch"] = _stub
        ns["shell"] = _stub
        ns["python_exec"] = _stub
        ns["ask_user"] = _stub
        ns["desktop_control"] = _stub
        ns["task_state"] = {}

        try:
            exec(compile(code, "<skill_smoke>", "exec"), ns, ns)
            run_fn = ns.get("run")
            if not callable(run_fn):
                return False, "no callable run() after exec"
            kwargs = {}
            for inp in inputs or []:
                key = str(inp)
                lk = key.lower()
                if "url" in lk or "link" in lk or "endpoint" in lk:
                    kwargs[key] = "https://example.com"
                else:
                    kwargs[key] = ""
            run_fn(**kwargs)
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"
        return True, ""

    @staticmethod
    def _build_prompt(objective: dict, execution_result: dict,
                      existing_skills: str) -> str:
        """Build skill evaluation prompt including existing skills for dedup."""
        goal = objective.get("goal", "Unknown")
        steps = execution_result.get("steps", [])
        actions_full = execution_result.get("actions_full") or []
        step_results_full = execution_result.get("step_results_full") or []

        step_details = []
        for s in steps:
            step_details.append(f"  {s.get('action')}({s.get('description', '')})")

        trace_lines: list[str] = []
        for i, act in enumerate(actions_full):
            cap = act.get("capability", "")
            params = act.get("params", {})
            try:
                param_preview = json.dumps(params, ensure_ascii=False)[:_SKILL_PARAM_PREVIEW]
            except (TypeError, ValueError):
                param_preview = truncate(str(params), _SKILL_PARAM_PREVIEW)
            sr = step_results_full[i] if i < len(step_results_full) else {}
            res_text = sr.get("result", "") if isinstance(sr, dict) else ""
            res_preview = truncate(str(res_text), _SKILL_RESULT_PREVIEW)
            ok = sr.get("success", True) if isinstance(sr, dict) else True
            trace_lines.append(
                f"--- Step {i + 1} | [{cap}] | success={ok} ---\n"
                f"Params: {param_preview}\n"
                f"Result (preview): {res_preview}\n"
            )

        parts = [
            f"Task completed successfully.\n",
            f"Goal: {goal}",
            f"Steps summary (may be truncated):\n" + "\n".join(step_details),
        ]
        if trace_lines:
            parts.append(
                "\nDetailed execution trace (use this to write accurate skill code):\n"
                + "\n".join(trace_lines)
            )

        if existing_skills:
            parts.append(f"\n--- Existing Skills (check for overlap!) ---\n{existing_skills}")
        else:
            parts.append("\n--- No existing skills yet ---")

        parts.append(
            "\nDecide: skip, update an existing skill, or create a new one? "
            "PREFER updating if any existing skill is related."
        )
        return "\n".join(parts)


def _parse_json_response(response: str) -> dict:
    """Parse JSON from LLM response, stripping markdown fences."""
    cleaned = response.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    return json.loads(cleaned)
