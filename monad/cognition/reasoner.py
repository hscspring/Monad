"""
MONAD Cognition: Reasoner
Multi-turn ReAct reasoning engine.

MONAD thinks like a rational person:
  Analyze problem → Check capabilities → Learn if needed → Execute → Reflect
"""

import json
import re

from loguru import logger

from monad.cognition.hints import action_hint, extract_open_app
from monad.cognition.parser import parse_response
from monad.cognition.planning import (
    BASIC_CAPABILITIES,
    action_satisfies_planned_capability,
    parse_plan_steps,
)
from monad.cognition.prompts import (
    ACTION_LOOP_MSG,
    ASK_USER_EXHAUSTED_MSG,
    COMPLETION_CHECK_SYSTEM,
    PARSE_ERROR_MSG,
    PLAN_SYSTEM_TEMPLATE,
    THOUGHT_DEFAULT_MSG,
    THOUGHT_HARD_LIMIT_MSG,
    THOUGHT_LOOP_MSG,
    THOUGHT_SOFT_LIMIT_MSG,
    build_reasoner_system,
)
from monad.config import (
    CONFIG, MAX_TURNS, HISTORY_CAP,
    THOUGHT_SOFT_LIMIT, THOUGHT_HARD_LIMIT,
    ASK_USER_LIMIT, MAX_ANSWER_REJECTIONS,
    SIMILARITY_THRESHOLD, TRUNCATE_THOUGHT,
    TRUNCATE_SHORT, TRUNCATE_MEDIUM, TRUNCATE_LONG, truncate,
)
from monad.core.llm import llm_call
from monad.execution.context import TaskState
from monad.interface.output import Output
from monad.knowledge.vault import KnowledgeVault

_BASIC_CAPABILITIES = BASIC_CAPABILITIES


class Reasoner:
    """Multi-turn ReAct reasoning engine.

    Implements the think → act → observe loop until the task is solved.
    """

    def __init__(self, vault: KnowledgeVault = None):
        self.vault = vault or KnowledgeVault()
        self._known_skills: list[str] = self._load_skill_names()
        self._system_prompt = build_reasoner_system(str(CONFIG.skills_path))

    def solve(self, user_input: str, execute_fn=None) -> dict:
        """Solve a user's request through multi-turn reasoning.

        Args:
            user_input: The user's natural language request
            execute_fn: Function to execute capabilities (capability_name, **params) -> str

        Returns:
            dict with 'answer', 'thoughts', 'actions', 'success'
        """
        Output.phase("Phase 1: 加载知识上下文")
        context = self._build_context(user_input)

        Output.phase("Phase 2: 任务分解")
        plan = self._decompose_task(user_input)
        if plan:
            for i, s in enumerate(plan):
                Output.system(f"  Step {i + 1}: {s['step']} → [{s['capability']}]")
        else:
            Output.system("单步任务，跳过分解")

        state = _SolveState()

        for turn in range(MAX_TURNS):
            Output.phase(f"Reasoning Turn {turn + 1}/{MAX_TURNS}")

            prompt = self._build_prompt(context, state.history, plan)

            Output.system("正在调用 LLM 进行推理...")
            try:
                raw_response = llm_call(prompt, system=self._system_prompt, temperature=0.2)
            except Exception as e:
                logger.error(f"LLM call failed in solve(): {e}")
                Output.error(f"LLM 调用失败: {str(e)}")
                state.llm_failures += 1
                if state.llm_failures >= 3:
                    return state.fail(f"LLM 连续调用失败 {state.llm_failures} 次: {str(e)}")
                Output.warn(f"LLM 调用失败 ({state.llm_failures}/3)，消耗本轮重试...")
                continue

            parsed = parse_response(raw_response)
            Output.system(f"LLM 返回类型: {parsed['type']}")

            if parsed["type"] == "thought":
                self._handle_thought(parsed, state)
                continue

            state.consecutive_thoughts = 0

            if parsed["type"] == "action":
                should_continue = self._handle_action(
                    parsed, raw_response, state, execute_fn, user_input, plan)
                if should_continue:
                    continue

            elif parsed["type"] == "answer":
                result = self._handle_answer(
                    parsed, raw_response, state, user_input, plan)
                if result is not None:
                    return result
                continue

            elif parsed["type"] == "error":
                self._handle_parse_error(raw_response, state)

        Output.error(f"推理轮次已用尽 ({MAX_TURNS} 轮)")
        return state.fail("推理轮次已用尽，无法完成任务。请尝试更简单的描述。")

    # ── Phase Handlers ───────────────────────────────────────────

    def _handle_thought(self, parsed: dict, state: "_SolveState"):
        """Handle a thought response from the LLM."""
        content = parsed["content"]
        state.consecutive_thoughts += 1
        state.thoughts.append(content)

        capped = truncate(content, TRUNCATE_THOUGHT)
        state.history.append({"role": "assistant", "content":
            json.dumps({"type": "thought", "content": capped}, ensure_ascii=False)
        })
        Output.thinking(content)

        is_loop = (
            len(state.thoughts) >= 2
            and _thought_similarity(state.thoughts[-1], state.thoughts[-2]) > SIMILARITY_THRESHOLD
        )

        if is_loop:
            Output.warn("检测到重复思考，强制要求执行动作")
            state.inject_user_msg(THOUGHT_LOOP_MSG)
        elif state.consecutive_thoughts >= THOUGHT_HARD_LIMIT:
            Output.warn(f"连续思考 {state.consecutive_thoughts} 轮，强制要求动作")
            state.inject_user_msg(THOUGHT_HARD_LIMIT_MSG)
        elif state.consecutive_thoughts >= THOUGHT_SOFT_LIMIT:
            state.inject_user_msg(THOUGHT_SOFT_LIMIT_MSG)
        else:
            state.inject_user_msg(THOUGHT_DEFAULT_MSG)

    def _handle_action(self, parsed: dict, raw_response: str,
                       state: "_SolveState", execute_fn, user_input: str,
                       plan: list | None) -> bool:
        """Handle an action response. Returns True if loop should continue."""
        capability = parsed.get("capability", "")
        params = parsed.get("params", {})

        if self._guard_action_limits(state, capability, params, raw_response,
                                     execute_fn, user_input):
            return True

        state.history.append({"role": "assistant", "content": raw_response})
        self._log_action(capability, params)

        result, state_key = self._execute_and_store(
            state, capability, params, execute_fn, user_input)

        observation = self._build_action_observation(
            state, capability, result, state_key, user_input, plan)
        state.history.append({"role": "user", "content": observation})
        return True

    def _guard_action_limits(self, state: "_SolveState", capability: str,
                             params: dict, raw_response: str,
                             execute_fn, user_input: str) -> bool:
        """Check ask_user limits and loop detectors. Returns True if handled."""
        if capability == "ask_user":
            state.consecutive_ask_user += 1
            if state.consecutive_ask_user > ASK_USER_LIMIT:
                Output.warn(f"连续 ask_user {state.consecutive_ask_user} 次，强制跳过")
                state.history.append({"role": "assistant", "content": raw_response})
                state.inject_user_msg(ASK_USER_EXHAUSTED_MSG)
                return True
        else:
            state.consecutive_ask_user = 0

        state.actions.append({"capability": capability, "params": params})

        if self._detect_action_loop(state, capability, params, raw_response, execute_fn, user_input):
            return True
        if self._detect_click_loop(state, capability, params, raw_response):
            return True
        if self._intercept_redundant_open(state, capability, params, raw_response, execute_fn, user_input):
            return True
        return False

    def _execute_and_store(self, state: "_SolveState", capability: str,
                           params: dict, execute_fn, user_input: str) -> tuple[str, str]:
        """Execute action, store in TaskState, track app. Returns (result, state_key)."""
        if execute_fn:
            result = execute_fn(capability, task_state=state.task_state, **params)
        else:
            result = f"Error: No executor available for '{capability}'"
        Output.observation(truncate(result, TRUNCATE_LONG))

        state_key = state.task_state.store(capability, result)
        self._track_active_app(state, capability, params, result)
        return result, state_key

    def _build_action_observation(self, state: "_SolveState", capability: str,
                                  result: str, state_key: str,
                                  user_input: str, plan: list | None) -> str:
        """Build the observation string fed back to the LLM."""
        verification = self._verify_action(capability,
                                           state.actions[-1].get("params", {}), result)
        if verification:
            result += "\n" + verification
            Output.observation(f"[验证] {verification}")

        hint = action_hint(capability, state.actions[-1].get("params", {}),
                           result, user_input)
        if hint:
            result += "\n" + hint

        if plan:
            self._update_plan(plan, capability, state.actions[-1].get("params", {}))

        observation = f"Observation from {capability} (stored as {state_key}):\n{result}"
        state_summary = state.task_state.summary()
        if state_summary:
            observation += f"\n\n{state_summary}"
        if plan:
            remaining = _plan_incomplete_steps(plan)
            if remaining:
                observation += f"\n\n{_format_plan(plan)}"
        return observation

    def _handle_answer(self, parsed: dict, raw_response: str,
                       state: "_SolveState", user_input: str,
                       plan: list | None) -> dict | None:
        """Handle an answer response. Returns result dict or None to continue."""
        if state.answer_rejections < MAX_ANSWER_REJECTIONS:
            if plan:
                self._reconcile_plan_from_actions(plan, state.actions)
                remaining = _plan_incomplete_steps(plan)
                if not remaining:
                    is_complete, incomplete_reason = True, ""
                else:
                    is_complete, incomplete_reason = self._check_task_completion(
                        user_input,
                        state.actions,
                        parsed.get("content", ""),
                        plan=plan,
                    )
                    if is_complete:
                        for s in plan:
                            s["done"] = True
            else:
                is_complete, incomplete_reason = self._check_task_completion(
                    user_input, state.actions, parsed.get("content", "")
                )

            if not is_complete:
                state.answer_rejections += 1
                Output.warn(f"任务未完成 ({state.answer_rejections}/{MAX_ANSWER_REJECTIONS}): {incomplete_reason}")
                state.history.append({"role": "assistant", "content": raw_response})
                hint = _format_plan(plan) + "\n" if plan else ""
                state.inject_user_msg(
                    f"[SYSTEM] 任务尚未完成，缺失步骤：{incomplete_reason}\n"
                    f"{hint}不要回答，立刻执行下一个缺失的操作。"
                )
                return None

        Output.phase("任务完成")
        return state.success(parsed["content"])

    @staticmethod
    def _handle_parse_error(raw_response: str, state: "_SolveState"):
        """Handle a parse error from the LLM response."""
        Output.warn(f"LLM 返回格式异常，正在重试... (原始: {truncate(raw_response, 150)})")
        state.history.append({"role": "assistant", "content": truncate(raw_response, 300)})
        state.inject_user_msg(PARSE_ERROR_MSG)

    # ── Loop Detection ───────────────────────────────────────────

    @staticmethod
    def _auto_screenshot(state: "_SolveState", execute_fn,
                         user_input: str, context_msg: str):
        """Execute an automatic screenshot and inject results into state."""
        auto_result = execute_fn(
            "desktop_control", task_state=state.task_state, action="screenshot")
        state.task_state.store("desktop_control", auto_result)
        Output.action("desktop_control", "[自动] 截屏")
        Output.observation(truncate(auto_result, TRUNCATE_LONG))
        hint = action_hint("desktop_control", {"action": "screenshot"}, auto_result, user_input)
        if hint:
            auto_result += "\n" + hint
        state.inject_user_msg(
            f"{context_msg}\n\n"
            f"Observation from desktop_control:\n{auto_result}\n\n"
            f"Now use click <text> to click a UI element, or type <text> to enter text. "
            f"Do NOT run open/activate again."
        )
        state.recent_action_sigs.clear()

    def _detect_action_loop(self, state: "_SolveState", capability: str,
                            params: dict, raw_response: str, execute_fn,
                            user_input: str) -> bool:
        """Detect 3x repeated identical actions. Returns True if handled."""
        action_sig = f"{capability}:{json.dumps(params, sort_keys=True, ensure_ascii=False)}"
        state.recent_action_sigs.append(action_sig)

        if len(state.recent_action_sigs) < 3 or len(set(state.recent_action_sigs[-3:])) != 1:
            return False

        stuck_action = params.get("action", "") or params.get("command", "")
        is_app_launch_loop = (
            "open -a" in stuck_action or "activate" in stuck_action.lower()
            or capability == "shell" and "open -a" in params.get("command", "")
        )

        state.history.append({"role": "assistant", "content": raw_response})

        if is_app_launch_loop and execute_fn:
            Output.warn(f"检测到重复动作 ({capability})，自动执行 screenshot 推进流程")
            self._auto_screenshot(
                state, execute_fn, user_input,
                f"[SYSTEM] You were stuck repeating '{stuck_action}'. The app IS already open. "
                f"I auto-executed screenshot for you. Here are the current screen elements:")
        else:
            Output.warn(f"检测到重复动作 ({capability})，强制切换策略")
            state.inject_user_msg(ACTION_LOOP_MSG.format(capability=capability))
        return True

    @staticmethod
    def _detect_click_loop(state: "_SolveState", capability: str,
                           params: dict, raw_response: str) -> bool:
        """Detect repeated clicks on the same target. Returns True if handled."""
        if capability != "desktop_control":
            return False

        action_str = params.get("action", "")
        if not action_str.startswith("click "):
            return False

        click_target = action_str[6:].strip()
        state.click_target_counts[click_target] = state.click_target_counts.get(click_target, 0) + 1

        if state.click_target_counts[click_target] < 3:
            return False

        count = state.click_target_counts[click_target]
        Output.warn(f'检测到重复点击 "{click_target}" {count} 次，强制换策略')
        state.history.append({"role": "assistant", "content": raw_response})
        state.inject_user_msg(
            f'[SYSTEM] STOP. You have clicked "{click_target}" {count} times '
            f'but the UI has not changed. This means you are clicking the WRONG element. '
            f'Try one of these:\n'
            f'1. Click a more specific element with context\n'
            f'2. Use click_xy with coordinates of the actual search result below the input\n'
            f'3. Press Enter/Return to confirm the search, then screenshot to see results\n'
            f'4. Use hotkey to navigate (e.g. hotkey down, then hotkey enter)'
        )
        return True

    def _intercept_redundant_open(self, state: "_SolveState", capability: str,
                                  params: dict, raw_response: str,
                                  execute_fn, user_input: str) -> bool:
        """Intercept redundant 'open -a' when app is already active. Returns True if handled."""
        if capability != "shell" or not state.active_app or not execute_fn:
            return False

        shell_cmd = params.get("command", "")
        requested_app = extract_open_app(shell_cmd)
        if not requested_app:
            return False

        from monad.tools.desktop_control import _is_same_app
        if not _is_same_app(requested_app, state.active_app):
            return False

        Output.warn(f'"{state.active_app}" 已在前台，跳过重复 open，自动截屏')
        state.history.append({"role": "assistant", "content": raw_response})
        self._auto_screenshot(
            state, execute_fn, user_input,
            f'[SYSTEM] "{state.active_app}" is ALREADY open and in the foreground. '
            f'Do NOT run "open -a" or "activate" again. '
            f'I auto-executed screenshot for you:')
        return True

    # ── Action Tracking ──────────────────────────────────────────

    @staticmethod
    def _track_active_app(state: "_SolveState", capability: str,
                          params: dict, result: str):
        """Track the currently active app from successful activate/open commands."""
        if capability == "desktop_control":
            act_str = params.get("action", "")
            if act_str.startswith("activate") and ("verified" in result or "foreground" in result):
                app_name = act_str.split(None, 1)[1].strip() if " " in act_str else ""
                if app_name:
                    state.active_app = app_name
        elif capability == "shell" and not state.active_app:
            shell_cmd = params.get("command", "")
            app = extract_open_app(shell_cmd)
            if app and "error" not in result.lower() and "unable" not in result.lower():
                state.active_app = app

    @staticmethod
    def _log_action(capability: str, params: dict):
        """Log the action being taken to Output."""
        if capability == "python_exec":
            Output.action("python_exec", "执行 Python 代码")
            Output.code(params.get("code", ""))
        elif capability == "shell":
            Output.action("shell", f"执行命令: {params.get('command', '')}")
        elif capability == "web_fetch":
            url = params.get("url", "")
            sel = params.get("selector", "")
            desc = f"感知网页: {url} (模式: {params.get('mode', 'auto')})"
            if sel:
                desc += f" [选择器: {sel}]"
            Output.action("web_fetch", desc)
        elif capability == "ask_user":
            Output.action("ask_user", f"需要询问用户: {params.get('question', '')}")
        else:
            Output.action(capability, truncate(str(params), TRUNCATE_MEDIUM))

    # ── Verification ─────────────────────────────────────────────

    @staticmethod
    def _verify_action(capability: str, params: dict, result: str) -> str:
        """Verify file-creation actions actually produced the expected artifacts."""
        if capability not in ("python_exec", "shell"):
            return ""

        code = params.get("code", "") + params.get("command", "")
        skills_path = str(CONFIG.skills_path)
        if skills_path not in code and "/skills/" not in code:
            return ""

        match = re.search(r'skills/([a-zA-Z0-9_-]+)', code)
        if not match:
            return ""

        skill_name = match.group(1)
        skill_dir = CONFIG.skill_dir(skill_name)
        yaml_ok = (skill_dir / "skill.yaml").is_file()
        py_ok = (skill_dir / "executor.py").is_file()

        parts = []
        if yaml_ok and py_ok:
            parts.append(f"✅ Verified: skill '{skill_name}' — skill.yaml and executor.py exist")
        else:
            if not yaml_ok:
                parts.append(f"⚠️ skill.yaml NOT found at {skill_dir}/skill.yaml")
            if not py_ok:
                parts.append(f"⚠️ executor.py NOT found at {skill_dir}/executor.py")
        return " | ".join(parts)

    def _check_task_completion(
        self,
        user_input: str,
        actions: list,
        proposed_answer: str,
        plan: list[dict] | None = None,
    ) -> tuple:
        """Use LLM to check if all subtasks are done. Fail-open on errors."""
        action_lines = []
        for i, a in enumerate(actions, 1):
            cap = a.get("capability", "")
            p = a.get("params", {})
            if cap == "python_exec":
                desc = truncate(p.get("code", "").replace("\n", " "), 150)
            elif cap == "shell":
                desc = p.get("command", "")
            elif cap == "web_fetch":
                desc = p.get("url", "")
            elif cap == "desktop_control":
                desc = p.get("action", "")
            else:
                desc = truncate(str(p), TRUNCATE_SHORT)
            action_lines.append(f"{i}. [{cap}] {desc}")

        parts = [
            f"用户请求：{user_input}\n",
            f"\n已执行的动作：\n" + "\n".join(action_lines),
            f"\n\nAgent 准备回答（摘要）：{truncate(proposed_answer, TRUNCATE_LONG)}",
        ]
        if plan:
            parts.append(
                f"\n\n{_format_plan(plan)}\n"
                f"（等效完成：若某步计划为 web_fetch，但实际用 python_exec+HTTP 抓取，也算完成该步。）"
            )
        parts.append("\n\n任务是否全部完成？")
        prompt = "".join(parts)

        try:
            raw = llm_call(prompt, system=COMPLETION_CHECK_SYSTEM,
                           temperature=0, max_tokens=100)
            raw = raw.strip()
            if raw.startswith("COMPLETE"):
                return (True, "")
            if raw.startswith("INCOMPLETE"):
                reason = raw.split("|", 1)[1].strip() if "|" in raw else "部分步骤未执行"
                return (False, reason)
            return (True, "")
        except Exception:
            return (True, "")

    # ── Context & Prompt Building ────────────────────────────────

    def _build_context(self, user_input: str) -> str:
        """Build context from MONAD's knowledge base."""
        sections = []
        knowledge = self.vault.load_all_context(query=user_input)

        if knowledge.get("axioms"):
            sections.append(f"## Your Principles\n{knowledge['axioms']}")
            Output.system(f"已加载系统公理 ({len(knowledge['axioms'])} 字符)")

        if knowledge.get("skills"):
            sections.append(f"## Your Learned Skills (USE THESE FIRST)\n{knowledge['skills']}")
            Output.skill_check(f"已学会的技能: {truncate(knowledge['skills'], TRUNCATE_MEDIUM)}")
        else:
            Output.skill_check("尚无已学技能，将在工作中学习")

        if knowledge.get("environment"):
            sections.append(f"## Environment Knowledge\n{knowledge['environment']}")
            Output.system(f"已加载环境知识 ({len(knowledge['environment'])} 字符)")

        if knowledge.get("user_context"):
            sections.append(f"## Known User Context\n{knowledge['user_context']}")
            Output.system(f"已加载用户记忆 ({len(knowledge['user_context'])} 字符)")

        if knowledge.get("protocols"):
            sections.append(f"## Behavioral Protocols\n{knowledge['protocols']}")

        if knowledge.get("experiences"):
            sections.append(f"## Past Experiences\n{knowledge['experiences']}")
            Output.system(f"已加载过往经验总结 ({len(knowledge['experiences'])} 字符)")

        sections.append(f"## User Request\n{user_input}")
        return "\n\n".join(sections)

    @staticmethod
    def _build_prompt(context: str, history: list,
                      plan: list[dict] | None = None) -> str:
        """Build the full prompt for the LLM."""
        parts = [context]

        if plan:
            parts.append("\n" + _format_plan(plan))

        trimmed = history[-HISTORY_CAP:] if len(history) > HISTORY_CAP else history

        if trimmed:
            if len(trimmed) < len(history):
                parts.append(f"\n## Reasoning History (latest {len(trimmed)} of {len(history)} entries)")
            else:
                parts.append("\n## Reasoning History")
            for msg in trimmed:
                role = "You" if msg["role"] == "assistant" else "System"
                parts.append(f"\n[{role}]: {msg['content']}")

        return "\n".join(parts)

    # ── Task Planning ────────────────────────────────────────────

    def _decompose_task(self, user_input: str) -> list[dict]:
        """Decompose user request into an ordered step plan via LLM."""
        skills_summary = ", ".join(self._known_skills) if self._known_skills else "(无)"
        system = PLAN_SYSTEM_TEMPLATE.format(skills=skills_summary)

        try:
            raw = llm_call(
                f"用户请求：{user_input}", system=system, temperature=0, max_tokens=400
            )
            steps = parse_plan_steps(raw)
            if not steps:
                return []
            return steps
        except Exception as exc:
            Output.warn(
                f"任务分解失败 ({exc.__class__.__name__}: {exc})，将作为单步任务执行"
            )
            return []

    def _reconcile_plan_from_actions(self, plan: list[dict], actions: list[dict]) -> None:
        """Replay the action log with semantic matching so plan progress stays consistent."""
        for s in plan:
            s["done"] = False
        for act in actions:
            cap = act.get("capability", "")
            params = act.get("params", {}) or {}
            self._update_plan(plan, cap, params)

    def _update_plan(self, plan: list[dict], capability: str, params: dict) -> None:
        """Mark the first undone step that this action satisfies as done."""
        known_skills = frozenset(self._known_skills)
        for step in plan:
            if step["done"]:
                continue
            if action_satisfies_planned_capability(
                step["capability"], capability, params, known_skills
            ):
                step["done"] = True
                return
        known = _BASIC_CAPABILITIES | set(self._known_skills)
        for step in plan:
            if not step["done"] and step["capability"] not in known:
                step["done"] = True
                return


    def _load_skill_names(self) -> list[str]:
        """Extract skill names from vault."""
        names = []
        for line in self.vault.load_skills().split("\n"):
            if line.startswith("Skill: "):
                names.append(line[7:].strip())
        return names


# ── Solve State ──────────────────────────────────────────────────


class _SolveState:
    """Mutable state for a single solve() invocation."""
    __slots__ = (
        "history", "thoughts", "actions",
        "consecutive_thoughts", "consecutive_ask_user",
        "recent_action_sigs", "click_target_counts",
        "active_app", "answer_rejections", "llm_failures",
        "task_state",
    )

    def __init__(self):
        self.history: list[dict] = []
        self.thoughts: list[str] = []
        self.actions: list[dict] = []
        self.consecutive_thoughts: int = 0
        self.consecutive_ask_user: int = 0
        self.recent_action_sigs: list[str] = []
        self.click_target_counts: dict[str, int] = {}
        self.active_app: str | None = None
        self.answer_rejections: int = 0
        self.llm_failures: int = 0
        self.task_state: TaskState = TaskState()

    def inject_user_msg(self, content: str):
        """Append a system-injected user message to history."""
        self.history.append({"role": "user", "content": content})

    def success(self, answer: str) -> dict:
        """Return a success result dict."""
        return {
            "answer": answer,
            "thoughts": self.thoughts,
            "actions": self.actions,
            "step_results": self._build_step_results(),
            "success": True,
        }

    def fail(self, answer: str) -> dict:
        """Return a failure result dict."""
        return {
            "answer": answer,
            "thoughts": self.thoughts,
            "actions": self.actions,
            "step_results": self._build_step_results(),
            "success": False,
        }

    def _build_step_results(self) -> list[dict]:
        """Build per-action result list from task_state for the learning pipeline."""
        results = []
        for i, a in enumerate(self.actions):
            cap = a["capability"]
            key = f"step_{i + 1}_{cap}"
            result_text = self.task_state.get(key, "")
            results.append({
                "capability": cap,
                "params": a.get("params", {}),
                "result": result_text,
                "success": bool(result_text) and "[error]" not in result_text[:200].lower(),
            })
        return results


# ── Static Helpers ───────────────────────────────────────────────

def _thought_similarity(a: str, b: str) -> float:
    """Jaccard similarity between two thought strings (word-level)."""
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def _format_plan(plan: list[dict]) -> str:
    """Format plan as a checklist for LLM context injection."""
    lines = ["[PLAN]"]
    next_found = False
    for i, s in enumerate(plan):
        if s["done"]:
            lines.append(f"  ✅ {i + 1}. {s['step']}")
        else:
            marker = " ← NEXT" if not next_found else ""
            lines.append(f"  ⬜ {i + 1}. {s['step']} [{s['capability']}]{marker}")
            if not next_found:
                next_found = True
    return "\n".join(lines)


def _plan_incomplete_steps(plan: list[dict]) -> list[str]:
    """Return descriptions of undone steps."""
    return [s["step"] for s in plan if not s["done"]]
