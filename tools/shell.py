"""
MONAD Tool: Shell
Execute shell commands and return output.
"""

import subprocess


def run(command: str = "", timeout: int = 30, **kwargs) -> str:
    """Execute a shell command and return its output.

    Args:
        command: The shell command to execute
        timeout: Maximum execution time in seconds (default: 30)
    """
    if not command:
        return "Error: No command specified."

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output_parts = []
        if result.stdout.strip():
            output_parts.append(result.stdout.strip())
        if result.stderr.strip():
            output_parts.append(f"[stderr] {result.stderr.strip()}")
        if result.returncode != 0:
            output_parts.append(f"[exit code: {result.returncode}]")

        return "\n".join(output_parts) if output_parts else "(no output)"

    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Shell error: {str(e)}"


TOOL_META = {
    "name": "shell",
    "description": "Execute a shell command and return the output.",
    "inputs": ["command", "timeout"],
}
