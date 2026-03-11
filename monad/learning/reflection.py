"""
MONAD Learning: Reflection
Analyzes task execution results and saves experiences to knowledge vault.
"""

import re
from monad.core.llm import llm_call
from monad.knowledge.vault import KnowledgeVault
from monad.interface.output import Output


def _clean_llm_output(text: str) -> str:
    """Strip <think> blocks and XML tag leakage from LLM output."""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'<think>.*$', '', text, flags=re.DOTALL)
    text = re.sub(r'</?(?:think|minimax:tool_call|invoke|parameter)[^>]*>', '', text)
    return text.strip()


REFLECTION_SYSTEM = """You are MONAD's Reflection module.
After a task is completed, you analyze the execution and produce a concise experience summary in Chinese.

You must return a structured summary with the following sections:
1. 过程: Brief description of what was done
2. 结果: Success or failure, and why
3. 经验: What was learned that could be useful in the future
4. 改进: How could this be done better next time
5. Tags: 3-5 keywords representing this task (e.g., #Python #Search)

Be concise and practical. Focus on actionable insights. Respond in Chinese."""


class Reflection:
    """Learns from task execution by analyzing results and saving experiences."""

    def __init__(self, vault: KnowledgeVault = None):
        self.vault = vault or KnowledgeVault()

    def learn(self, objective: dict, execution_result: dict) -> str:
        """Analyze execution results and save experience."""
        prompt = self._build_prompt(objective, execution_result)

        Output.system("正在调用 LLM 分析执行经验...")
        try:
            raw = llm_call(prompt, system=REFLECTION_SYSTEM, temperature=0.3)
            summary = _clean_llm_output(raw)
        except Exception as e:
            Output.error(f"反思失败: {str(e)}")
            summary = f"Reflection failed: {str(e)}"

        Output.learning(f"反思总结:\n{summary[:300]}")

        # Save to knowledge vault
        task_desc = objective.get("goal", "Unknown task")
        process = execution_result.get("summary", "")
        result_status = "Success" if execution_result.get("success") else "Partial/Failed"

        # Save detailed log to records
        filepath = self.vault.save_record(
            task=task_desc,
            process=process,
            result=result_status,
            notes=summary,
        )
        Output.learning(f"执行记录已保存: {filepath.name}")

        # Extract tags from reflection summary
        tags = self._extract_tags(summary)

        # Save concise experience for future context
        success = execution_result.get("success", False)
        exp_path = self.vault.save_experience(task_desc, summary, success=success, tags=tags)
        Output.learning(f"反思经验已沉淀: {exp_path.name}")
        return summary

    @staticmethod
    def _extract_tags(summary: str) -> list:
        """Extract tags from reflection summary.

        Looks for lines like "Tags: #web_fetch #PDF #解析" or
        "5. Tags: web_fetch, PDF, 解析" in the LLM output.
        """
        tags = []
        for line in summary.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            # Match lines starting with "Tags:" or "5. Tags:" or "5."
            lower = stripped.lower()
            if lower.startswith("tags:") or lower.startswith("5. tags:") or lower.startswith("5."):
                raw = stripped.split(":", 1)[-1] if ":" in stripped else stripped
                for token in raw.replace("#", " ").replace("，", " ").replace(",", " ").split():
                    token = token.strip().strip("#").lower()
                    if len(token) >= 2:
                        tags.append(token)
                break
        return tags

    def _build_prompt(self, objective: dict, execution_result: dict) -> str:
        """Build reflection prompt."""
        goal = objective.get("goal", "Unknown")
        actions = objective.get("actions", [])
        success = execution_result.get("success", False)
        steps = execution_result.get("steps", [])

        step_details = []
        for s in steps:
            status = "OK" if s.get("success") else "FAILED"
            step_details.append(f"  Step {s.get('step')}: {s.get('description')} [{status}] → {s.get('result', '')[:200]}")

        return (
            f"Goal: {goal}\n"
            f"Planned Actions: {', '.join(actions)}\n"
            f"Overall Success: {success}\n\n"
            f"Execution Details:\n" + "\n".join(step_details) + "\n\n"
            f"Analyze this execution and provide your reflection."
        )
