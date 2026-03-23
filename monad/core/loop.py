"""
MONAD Core Loop
The central orchestration: Input → Reasoner.solve() → Reflection
"""

import queue

from loguru import logger

from monad.cognition.reasoner import Reasoner
from monad.config import QUIT_COMMANDS, TRUNCATE_SHORT, truncate
from monad.execution.executor import Executor
from monad.interface.output import Output
from monad.interface.voice_input import VoiceInput
from monad.knowledge.vault import KnowledgeVault
from monad.learning.personalization import Personalizer
from monad.learning.reflection import Reflection
from monad.learning.skill_builder import SkillBuilder
from monad.proactive.notify import notify
from monad.proactive.scheduler import ProactiveTask, Scheduler


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

        self.personalizer = Personalizer(vault=self.vault)
        Output.system("  ✓ 个性化学习就绪")

        self.proactive_queue: queue.Queue[ProactiveTask] = queue.Queue(maxsize=8)
        self.scheduler = Scheduler(self.proactive_queue)
        Output.system("  ✓ 主动调度器就绪")

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

        self.scheduler.start()
        Output.status("Awaiting Objective.\n")

        while True:
            try:
                user_input = self.input.listen()

                if not user_input:
                    self._process_proactive_if_any()
                    continue

                if user_input.lower() in QUIT_COMMANDS:
                    self.scheduler.stop()
                    Output.status("MONAD Offline.")
                    break

                self.scheduler.touch()
                Output.divider()
                Output.phase("接收到新任务")
                Output.system(f"用户输入: {user_input}")
                self._process(user_input)
                Output.divider()
                Output.status("Awaiting Objective.\n")

            except KeyboardInterrupt:
                print()
                self.scheduler.stop()
                Output.status("MONAD Offline.")
                break
            except Exception as e:
                logger.exception("Unhandled error in main loop")
                Output.error(str(e))
                Output.status("Awaiting Objective.\n")

    def _process_proactive_if_any(self) -> None:
        """Dequeue and process one proactive task if available."""
        try:
            ptask: ProactiveTask = self.proactive_queue.get_nowait()
        except queue.Empty:
            return

        self.scheduler.is_processing_proactive = True
        try:
            if ptask.task == "__self_improve__":
                self._run_self_improvement()
            else:
                Output.phase("Phase: 主动任务执行")
                Output.system(f"主动任务: {ptask.task} (来源: {ptask.job_id})")
                result = self.reasoner.solve(
                    user_input=ptask.task,
                    execute_fn=self.executor.execute,
                )
                answer = result.get("answer", "（无输出）")
                notify(f"主动任务完成: {ptask.job_id}", answer, channel=ptask.notify)
        except Exception as e:
            logger.exception(f"Proactive task {ptask.job_id} failed")
            Output.error(f"主动任务执行失败: {e}")
        finally:
            self.scheduler.is_processing_proactive = False

    def _run_self_improvement(self) -> None:
        """Run the self-evaluation + curiosity engine loop."""
        try:
            from monad.learning.self_eval import SelfEvaluator
            from monad.learning.curiosity import CuriosityEngine

            Output.phase("Phase: 自我改进")

            evaluator = SelfEvaluator(vault=self.vault)
            report = evaluator.evaluate()
            if report:
                Output.learning(f"自评估完成: 发现 {len(report.get('weak_areas', []))} 个薄弱环节")

            engine = CuriosityEngine(vault=self.vault, execute_fn=self.executor.execute)
            improved = engine.run_session(eval_report=report)
            if improved:
                notify("自我改进完成", improved, channel="auto")
            else:
                Output.system("本次自我改进未产生更新")
        except Exception as e:
            logger.exception("Self-improvement cycle failed")
            Output.error(f"自我改进失败: {e}")

    def _process(self, user_input: str):
        """Process a single user request through the full MONAD pipeline."""
        self.scheduler.touch()

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

            Output.learning("正在提取用户个性化信息...")
            self.personalizer.extract_and_update(user_input, exec_result)
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
