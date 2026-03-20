"""
MONAD Execution: TaskState
Shared state for a single task execution — the State Monad in practice.

Each solve() invocation creates a TaskState. Action results are automatically
stored (full, untruncated) and keyed by turn + capability. Downstream tools
(python_exec, skills) can read prior results directly from the state dict
instead of relying on the LLM to re-serialize data through its context window.

Design: s → (a, s')  — every action transforms the state.
"""

from __future__ import annotations


class TaskState(dict):
    """Shared key-value state that lives for one task execution.

    Inherits from dict so python_exec code can use it naturally:
        content = task_state["step_3_web_fetch"]
        task_state["my_key"] = processed_data

    The auto-generated keys follow the pattern: step_{n}_{capability}
    """

    def __init__(self):
        super().__init__()
        self._counter: int = 0

    def store(self, capability: str, result: str) -> str:
        """Store an action result and return the auto-generated key."""
        self._counter += 1
        key = f"step_{self._counter}_{capability}"
        self[key] = result
        return key

    def latest(self, capability: str | None = None) -> str | None:
        """Return the most recent result, optionally filtered by capability."""
        for key in reversed(list(self.keys())):
            if capability is None or capability in key:
                return self[key]
        return None

    def summary(self) -> str:
        """Compact summary for LLM context injection — keys and sizes only."""
        if not self:
            return ""
        lines = ["[task_state available — use task_state[\"key\"] in python_exec]"]
        for key, val in self.items():
            lines.append(f"  {key} ({len(val)} chars)")
        return "\n".join(lines)
