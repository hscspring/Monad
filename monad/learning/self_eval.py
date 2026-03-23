"""
MONAD Learning: Self-Evaluator
Analyzes past experiences to identify failure patterns and capability gaps.
Produces improvement objectives that the Curiosity Engine can act on.
"""

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from loguru import logger

from monad.cognition.parser import clean_llm_output
from monad.config import CONFIG, truncate
from monad.core.llm import llm_call
from monad.interface.output import Output
from monad.knowledge.vault import KnowledgeVault

SELF_EVAL_SYSTEM = """You are MONAD's Self-Evaluator module.
You analyze MONAD's past task execution history to identify capability gaps and suggest improvements.

You will receive:
1. Statistics: success/failure counts grouped by tag categories
2. Failure details: summaries of failed tasks
3. Existing skills: what MONAD already knows

Your job is to produce a JSON report:
{
  "weak_areas": [
    {
      "category": "tag or area name",
      "failure_rate": 0.4,
      "diagnosis": "Why tasks in this area tend to fail",
      "improvement": {
        "type": "skill_update" or "protocol_update" or "new_skill",
        "target": "skill or protocol name (for updates) or new name",
        "objective": "Specific research objective to fix this weakness"
      }
    }
  ],
  "overall_assessment": "One-paragraph summary of MONAD's current capability state"
}

Rules:
- Focus on ACTIONABLE improvements that can be fixed by updating skill code or protocols
- Each improvement objective must be specific enough to research on the web
- Prioritize high-failure-rate categories
- Maximum 3 weak areas per evaluation
- Return valid JSON only, no markdown"""


class SelfEvaluator:
    """Analyzes past performance and identifies improvement areas."""

    def __init__(self, vault: KnowledgeVault = None):
        self.vault = vault or KnowledgeVault()

    def evaluate(self) -> dict | None:
        """Run a self-evaluation cycle.

        Returns an evaluation report dict, or None if insufficient data.
        """
        pending = self._load_pending()
        if len(pending) < 3:
            Output.system("经验数据不足（<3），跳过自评估")
            return None

        stats = self._compute_stats(pending)
        failures = [e for e in pending if not e.get("success")]

        if not failures:
            Output.system("无失败经验，暂无需改进")
            return {"weak_areas": [], "overall_assessment": "All recent tasks succeeded."}

        existing_skills = self.vault.load_skills()
        prompt = self._build_prompt(stats, failures, existing_skills)

        try:
            raw = llm_call(prompt, system=SELF_EVAL_SYSTEM, temperature=0.2)
            report = json.loads(clean_llm_output(raw))
        except Exception as e:
            logger.warning(f"Self-evaluation LLM call failed: {e}")
            report = self._fallback_report(stats, failures)

        self._save_report(report)
        return report

    def _load_pending(self) -> list[dict]:
        """Load all entries from pending.jsonl."""
        path = self.config.experiences_path / "pending.jsonl"
        if not path.exists():
            return []
        entries = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return entries

    @property
    def config(self):
        return self.vault.config

    def _compute_stats(self, entries: list[dict]) -> dict:
        """Compute per-tag success/failure statistics."""
        tag_success: Counter = Counter()
        tag_failure: Counter = Counter()
        for e in entries:
            tags = e.get("tags", [])
            if e.get("success"):
                for t in tags:
                    tag_success[t] += 1
            else:
                for t in tags:
                    tag_failure[t] += 1

        stats: dict[str, dict] = {}
        all_tags = set(tag_success.keys()) | set(tag_failure.keys())
        for tag in all_tags:
            s, f = tag_success[tag], tag_failure[tag]
            total = s + f
            stats[tag] = {
                "success": s,
                "failure": f,
                "total": total,
                "failure_rate": round(f / total, 2) if total else 0,
            }
        return stats

    def _build_prompt(self, stats: dict, failures: list[dict],
                      existing_skills: str) -> str:
        stats_lines = []
        for tag, s in sorted(stats.items(), key=lambda x: x[1]["failure_rate"], reverse=True):
            stats_lines.append(
                f"  {tag}: {s['success']} ok / {s['failure']} failed "
                f"(failure rate: {s['failure_rate']:.0%})"
            )

        failure_summaries = []
        for f in failures[-10:]:
            failure_summaries.append(
                f"  Task: {truncate(f.get('task', ''), 100)}\n"
                f"  Tags: {', '.join(f.get('tags', []))}\n"
                f"  Summary: {truncate(f.get('summary', ''), 200)}"
            )

        return (
            "=== Tag Statistics ===\n" + "\n".join(stats_lines) + "\n\n"
            "=== Recent Failures (up to 10) ===\n" + "\n---\n".join(failure_summaries) + "\n\n"
            f"=== Existing Skills ===\n{existing_skills or '(none)'}\n\n"
            "Analyze the failures and suggest specific improvement objectives."
        )

    def _fallback_report(self, stats: dict, failures: list[dict]) -> dict:
        """Generate a simple report without LLM when the call fails."""
        weak = []
        sorted_tags = sorted(stats.items(), key=lambda x: x[1]["failure_rate"], reverse=True)
        for tag, s in sorted_tags[:3]:
            if s["failure_rate"] > 0:
                weak.append({
                    "category": tag,
                    "failure_rate": s["failure_rate"],
                    "diagnosis": f"Failed {s['failure']} out of {s['total']} tasks",
                    "improvement": {
                        "type": "protocol_update",
                        "target": tag,
                        "objective": f"Research best practices for {tag} tasks",
                    },
                })
        return {
            "weak_areas": weak,
            "overall_assessment": f"Evaluated {sum(s['total'] for s in stats.values())} tasks across {len(stats)} categories.",
        }

    def _save_report(self, report: dict) -> Path:
        """Save the evaluation report to records/."""
        timestamp = datetime.now().strftime("%Y_%m_%d")
        path = self.config.records_path / f"self_eval_{timestamp}.md"

        lines = ["# MONAD Self-Evaluation Report", ""]
        lines.append(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        assessment = report.get("overall_assessment", "")
        if assessment:
            lines.append(f"## Overall Assessment\n{assessment}\n")

        weak_areas = report.get("weak_areas", [])
        if weak_areas:
            lines.append("## Weak Areas\n")
            for wa in weak_areas:
                lines.append(f"### {wa.get('category', '?')} (failure rate: {wa.get('failure_rate', 0):.0%})")
                lines.append(f"- Diagnosis: {wa.get('diagnosis', '')}")
                imp = wa.get("improvement", {})
                lines.append(f"- Action: {imp.get('type', '')} → {imp.get('target', '')}")
                lines.append(f"- Objective: {imp.get('objective', '')}")
                lines.append("")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
