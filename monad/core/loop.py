"""
MONAD Core Loop
The central orchestration: Input → Reasoner.solve() → Reflection
"""

from loguru import logger

from monad.cognition.reasoner import Reasoner
from monad.config import QUIT_COMMANDS, TRUNCATE_SHORT, truncate
from monad.execution.executor import Executor
from monad.interface.output import Output
from monad.interface.voice_input import VoiceInput
from monad.knowledge.vault import KnowledgeVault
from monad.learning.reflection import Reflection
from monad.learning.skill_builder import SkillBuilder


class MonadLoop:
    """The MONAD core execution loop."""

    def __init__(self):
        Output.system("初始化 MONAD 各模块...")

        self.input = VoiceInput()
        Output.system("  ✓ 输入模块就绪")

        self.vault = KnowledgeVault()
        Output.system("  ✓ 知识库就绪")

        self.executor = Executor()
        Output.system(f"  ✓ 执行引擎就绪 (基础能力: {', '.join(self.executor.capability_names)})")

        self.reasoner = Reasoner(vault=self.vault)
        Output.system("  ✓ 推理引擎就绪")

        self.reflection = Reflection(self.vault)
        Output.system("  ✓ 反思引擎就绪")

        self.skill_builder = SkillBuilder(vault=self.vault)
        Output.system("  ✓ 技能生成引擎就绪")

    def start(self):
        """Start the MONAD interactive loop."""
        Output.banner()
        Output.status("MONAD Initialized.")
        Output.status("State: Rational Mode.")

        skills = self.vault.load_skills()
        Output.system(f"基础能力: {', '.join(self.executor.capability_names)}")
        if skills:
            Output.system(f"已学技能:\n{skills}")
        else:
            Output.system("尚无已学技能，将在执行任务中自主学习。")

        Output.status("Awaiting Objective.\n")

        while True:
            try:
                user_input = self.input.listen()

                if not user_input:
                    continue

                if user_input.lower() in QUIT_COMMANDS:
                    Output.status("MONAD Offline.")
                    break

                Output.divider()
                Output.phase("接收到新任务")
                Output.system(f"用户输入: {user_input}")
                self._process(user_input)
                Output.divider()
                Output.status("Awaiting Objective.\n")

            except KeyboardInterrupt:
                print()
                Output.status("MONAD Offline.")
                break
            except Exception as e:
                logger.exception("Unhandled error in main loop")
                Output.error(str(e))
                Output.status("Awaiting Objective.\n")

    def _process(self, user_input: str):
        """Process a single user request through the full MONAD pipeline."""

        Output.phase("Phase: 推理与执行")
        result = self.reasoner.solve(
            user_input=user_input,
            execute_fn=self.executor.execute,
        )

        if result.get("answer"):
            Output.result(result["answer"])

        if not result.get("success") and result.get("actions"):
            self._run_teardowns(result["actions"])

        if result.get("actions"):
            Output.phase("Phase: 反思与学习")

            objective = {
                "goal": user_input,
                "actions": [a["capability"] for a in result["actions"]],
            }
            step_results = result.get("step_results", [])
            exec_result = {
                "success": result.get("success", False),
                "summary": result.get("answer", ""),
                "actions_full": result["actions"],
                "step_results_full": step_results,
                "steps": [
                    {
                        "step": i + 1,
                        "action": sr.get("capability", a["capability"]),
                        "description": truncate(str(a.get("params", {})), TRUNCATE_SHORT),
                        "result": truncate(sr.get("result", ""), TRUNCATE_SHORT),
                        "success": sr.get("success", False),
                    }
                    for i, (a, sr) in enumerate(
                        zip(result["actions"],
                            step_results or [{}] * len(result["actions"])))
                ],
            }

            Output.learning("正在分析本次执行经验...")
            self.reflection.learn(objective, exec_result)

            Output.learning("正在评估是否应生成新技能...")
            skill = self.skill_builder.evaluate_and_build(objective, exec_result)
            if skill:
                Output.learning(f"新技能已生成: {skill.get('name', '?')} — {skill.get('goal', '')}")
            else:
                Output.learning("本次任务未生成新技能")
        else:
            Output.system("无执行动作，跳过反思阶段")

        n_thoughts = len(result.get("thoughts", []))
        n_actions = len(result.get("actions", []))
        Output.system(
            f"本次任务统计: {n_thoughts} 次思考, {n_actions} 次行动, "
            f"结果: {'成功' if result.get('success') else '失败'}"
        )

    def _run_teardowns(self, actions: list[dict]):
        """Run teardown skills for any capabilities that require cleanup."""
        seen = set()
        for action in actions:
            cap = action.get("capability", "")
            if cap in seen:
                continue
            seen.add(cap)
            teardown = self.executor.get_skill_teardown(cap)
            if teardown:
                Output.phase("Phase: 资源清理")
                Output.system(f"执行 teardown: {teardown} (因 {cap} 需要清理)")
                try:
                    self.executor.execute(teardown)
                except Exception as e:
                    logger.warning(f"Teardown '{teardown}' failed: {e}")
                    Output.warn(f"Teardown '{teardown}' 执行失败: {e}")

    def run_once(self, user_input: str) -> dict:
        """Run once for testing."""
        return self.reasoner.solve(
            user_input=user_input,
            execute_fn=self.executor.execute,
        )
