"""
MONAD Tool: Python Executor
The most important basic capability — execute Python code.
MONAD learns everything through this.
"""

import os
import sys
import io
import traceback

from monad.config import CONFIG


def run(code: str = "", _task_state=None, **kwargs) -> str:
    """Execute Python code and return the output.

    This is MONAD's core learning capability.
    Through python_exec, MONAD can do anything Python can do.

    Args:
        code: Python code to execute
        _task_state: Injected by executor — shared state dict for
            reading prior step results and storing new ones.

    Returns:
        stdout output + return value, or error message
    """
    if not code:
        return "Error: No code provided."

    output_dir = CONFIG.output_path
    output_dir.mkdir(parents=True, exist_ok=True)

    old_stdout = sys.stdout
    old_stderr = sys.stderr
    captured_out = io.StringIO()
    captured_err = io.StringIO()

    try:
        sys.stdout = captured_out
        sys.stderr = captured_err

        before = set(output_dir.iterdir()) if output_dir.exists() else set()

        exec_globals = {
            "__builtins__": __builtins__,
            "os": os,
            "sys": sys,
            "MONAD_OUTPUT_DIR": str(output_dir),
        }
        if _task_state is not None:
            exec_globals["task_state"] = _task_state
        try:
            from monad.tools.web_fetch import run as _wf
            from monad.tools.shell import run as _sh
            exec_globals["web_fetch"] = _wf
            exec_globals["shell"] = _sh
        except ImportError:
            pass
        try:
            from monad.tools._schedule_helpers import (
                schedule_task, monitor_condition,
                list_schedules, cancel_schedule,
            )
            exec_globals["schedule_task"] = schedule_task
            exec_globals["monitor_condition"] = monitor_condition
            exec_globals["list_schedules"] = list_schedules
            exec_globals["cancel_schedule"] = cancel_schedule
        except ImportError:
            pass
        exec(code, exec_globals)

        stdout_val = captured_out.getvalue()
        stderr_val = captured_err.getvalue()

        result_parts = []
        if stdout_val.strip():
            result_parts.append(stdout_val.strip())
        if stderr_val.strip():
            result_parts.append(f"[stderr] {stderr_val.strip()}")

        after = set(output_dir.iterdir()) if output_dir.exists() else set()
        new_files = after - before
        if new_files:
            for f in sorted(new_files):
                result_parts.append(f"[file saved] {f.name} → /output/{f.name}")

        return "\n".join(result_parts) if result_parts else "(executed successfully, no output)"

    except Exception:
        error = traceback.format_exc()
        stdout_val = captured_out.getvalue()
        parts = []
        if stdout_val.strip():
            parts.append(stdout_val.strip())
        parts.append(f"[Error]\n{error}")
        return "\n".join(parts)

    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


TOOL_META = {
    "name": "python_exec",
    "description": "Execute Python code. MONAD's core learning capability.",
    "inputs": ["code"],
}
