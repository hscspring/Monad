"""
MONAD Core Loop
The central orchestration: Input → Reasoner.solve() → Reflection

MONAD thinks like a rational person:
  Analyze → Self-check → Learn → Execute → Reflect

All process steps are printed for user visibility.
"""

from cognition.reasoner import Reasoner
from execution.executor import Executor
from knowledge.vault import KnowledgeVault
from learning.reflection import Reflection
from learning.skill_builder import SkillBuilder
from interface.output import Output
from interface.voice_input import VoiceInput


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

        self.output = Output()

    def start(self):
        """Start the MONAD interactive loop."""
        self.output.banner()
        Output.status("MONAD Initialized.")
        Output.status("State: Rational Mode.")

        # Show current capabilities & skills
        Output.system(f"基础能力: {', '.join(self.executor.capability_names)}")
        skills = self.vault.load_skills()
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

                if user_input.lower() in ("quit", "exit", "bye", "q"):
                    Output.status("MONAD Offline.")
                    break

                self.output.divider()
                Output.phase("接收到新任务")
                Output.system(f"用户输入: {user_input}")
                self._process(user_input)
                self.output.divider()
                Output.status("Awaiting Objective.\n")

            except KeyboardInterrupt:
                print()
                Output.status("MONAD Offline.")
                break
            except Exception as e:
                Output.error(str(e))
                import traceback
                traceback.print_exc()
                Output.status("Awaiting Objective.\n")

    def _process(self, user_input: str):
        """Process a single user request through the full MONAD pipeline."""

        # ── Phase: Reasoning ─────────────────────────────
        Output.phase("Phase: 推理与执行")
        result = self.reasoner.solve(
            user_input=user_input,
            execute_fn=self.executor.execute,
        )

        # ── Phase: Show Answer ───────────────────────────
        if result.get("answer"):
            Output.result(result["answer"])

        # ── Phase: Reflection ────────────────────────────
        if result.get("actions"):
            Output.phase("Phase: 反思与学习")

            # Build summary for reflection
            objective = {
                "goal": user_input,
                "actions": [a["capability"] for a in result["actions"]],
            }
            exec_result = {
                "success": result.get("success", False),
                "summary": result.get("answer", ""),
                "steps": [
                    {
                        "step": i + 1,
                        "action": a["capability"],
                        "description": str(a.get("params", {}))[:100],
                        "result": result.get("answer", ""),
                        "success": result.get("success", False),
                    }
                    for i, a in enumerate(result["actions"])
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

        # Show stats
        n_thoughts = len(result.get("thoughts", []))
        n_actions = len(result.get("actions", []))
        Output.system(f"本次任务统计: {n_thoughts} 次思考, {n_actions} 次行动, 结果: {'成功' if result.get('success') else '失败'}")

    def run_once(self, user_input: str) -> dict:
        """Run once for testing."""
        return self.reasoner.solve(
            user_input=user_input,
            execute_fn=self.executor.execute,
        )
