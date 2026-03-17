"""
MONAD Tool: Python Executor
The most important basic capability — execute Python code.
MONAD learns everything through this.
"""

import os
import sys
import io
import traceback
from pathlib import Path

MONAD_OUTPUT_DIR = Path(os.path.expanduser("~")) / ".monad" / "output"
MONAD_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run(code: str = "", **kwargs) -> str:
    """Execute Python code and return the output.

    This is MONAD's core learning capability.
    Through python_exec, MONAD can:
    - Call APIs
    - Process data
    - Read/write files
    - Check network
    - Do anything Python can do

    Args:
        code: Python code to execute

    Returns:
        stdout output + return value, or error message
    """
    if not code:
        return "Error: No code provided."

    # Capture stdout
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    captured_out = io.StringIO()
    captured_err = io.StringIO()

    try:
        sys.stdout = captured_out
        sys.stderr = captured_err

        # Snapshot output dir before execution
        before = set(MONAD_OUTPUT_DIR.iterdir()) if MONAD_OUTPUT_DIR.exists() else set()

        # Execute — inject MONAD_OUTPUT_DIR so LLM code can save files there
        exec_globals = {
            "__builtins__": __builtins__,
            "os": os,
            "sys": sys,
            "MONAD_OUTPUT_DIR": str(MONAD_OUTPUT_DIR),
        }
        # Lazy-inject MONAD tools so LLM code & skills can call them
        try:
            from monad.tools.web_fetch import run as _wf
            from monad.tools.shell import run as _sh
            exec_globals["web_fetch"] = _wf
            exec_globals["shell"] = _sh
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

        # Detect new files in output dir (file_link emitted by Executor)
        after = set(MONAD_OUTPUT_DIR.iterdir()) if MONAD_OUTPUT_DIR.exists() else set()
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
