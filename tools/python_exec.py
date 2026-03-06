"""
MONAD Tool: Python Executor
The most important basic capability — execute Python code.
MONAD learns everything through this.
"""

import sys
import io
import traceback


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

        # Execute in a namespace that persists across calls
        exec_globals = {"__builtins__": __builtins__}
        exec(code, exec_globals)

        stdout_val = captured_out.getvalue()
        stderr_val = captured_err.getvalue()

        result_parts = []
        if stdout_val.strip():
            result_parts.append(stdout_val.strip())
        if stderr_val.strip():
            result_parts.append(f"[stderr] {stderr_val.strip()}")

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
