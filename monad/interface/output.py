"""
MONAD Interface: Output
Formatted output with MONAD state prefixes.
All process steps are printed so the user can see exactly what MONAD is doing.
"""

from datetime import datetime
import threading

from monad.config import (
    VERSION, DIVIDER_WIDTH, CODE_DIVIDER_WIDTH,
    WS_RESULT_START, WS_RESULT_END,
    WS_ASK_USER_START, WS_ASK_USER_END,
    WS_FILE_START, WS_FILE_END,
)


class Output:
    """Handles formatted output for MONAD."""

    _local = threading.local()

    BANNER = f"""
    ╔══════════════════════════════════════╗
    ║          M O N A D  v{VERSION:<16s} ║
    ║    Personal AGI Operating Core       ║
    ╚══════════════════════════════════════╝
    """

    @classmethod
    def set_queue(cls, q):
        """Set a thread-local queue to collect output messages."""
        cls._local.queue = q

    @classmethod
    def _emit(cls, msg: str):
        """Emit a message to standard output and route to queue if registered."""
        print(msg)
        q = getattr(cls._local, "queue", None)
        if q is not None:
            if hasattr(q, "put"):
                q.put(msg)
            else:
                q(msg)

    @staticmethod
    def banner():
        """Print the MONAD startup banner."""
        Output._emit(Output.BANNER)

    @staticmethod
    def status(state: str):
        """Print a status message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        Output._emit(f"[MONAD {timestamp}] {state}")

    @staticmethod
    def system(msg: str):
        """Print a system message."""
        Output._emit(f"[MONAD] ⚙️  {msg}")

    @staticmethod
    def thinking(msg: str):
        """Print a thinking/reasoning message — shows MONAD's thought process."""
        Output._emit(f"[MONAD] 🧠 思考: {msg}")

    @staticmethod
    def action(capability: str, detail: str):
        """Print an action being taken."""
        Output._emit(f"[MONAD] ⚡ 行动 [{capability}]: {detail}")

    @staticmethod
    def code(code_str: str):
        """Print the code MONAD is about to execute."""
        divider = "─" * CODE_DIVIDER_WIDTH
        lines = [f"[MONAD] 📄 执行代码:", divider]
        for line in code_str.strip().split('\n'):
            lines.append(f"  {line}")
        lines.append(divider)
        Output._emit("\n".join(lines))

    @staticmethod
    def observation(msg: str):
        """Print an observation/result from an action."""
        Output._emit(f"[MONAD] 👁️  观察: {msg}")

    @staticmethod
    def skill_check(msg: str):
        """Print skill self-check status."""
        Output._emit(f"[MONAD] 🔍 自检: {msg}")

    @staticmethod
    def learning(msg: str):
        """Print a learning/reflection message."""
        Output._emit(f"[MONAD] 📝 学习: {msg}")

    @staticmethod
    def result(msg: str):
        """Print the final answer — shown in the chat panel."""
        Output._emit(WS_RESULT_START)
        Output._emit(str(msg))
        Output._emit(WS_RESULT_END)

    @staticmethod
    def file_link(filepath: str, url: str):
        """Emit a file-output marker so the frontend shows a download link."""
        Output._emit(f"{WS_FILE_START}{filepath}|{url}{WS_FILE_END}")

    @staticmethod
    def ask_user_marker(question: str):
        """Emit the ask_user marker for the web frontend."""
        Output._emit(f"{WS_ASK_USER_START}{question}{WS_ASK_USER_END}")

    @staticmethod
    def error(msg: str):
        """Print an error message."""
        Output._emit(f"[MONAD] ❌ 错误: {msg}")

    @staticmethod
    def warn(msg: str):
        """Print a warning message."""
        Output._emit(f"[MONAD] ⚠️  警告: {msg}")

    @staticmethod
    def divider():
        """Print a visual divider."""
        Output._emit("─" * DIVIDER_WIDTH)

    @staticmethod
    def phase(phase_name: str):
        """Print a phase transition marker."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        Output._emit(f"\n[MONAD {timestamp}] ── {phase_name} ──")
