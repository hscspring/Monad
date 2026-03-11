"""
MONAD Interface: Output
Formatted output with MONAD state prefixes.
All process steps are printed so the user can see exactly what MONAD is doing.
"""

from datetime import datetime
import threading


class Output:
    """Handles formatted output for MONAD."""

    _local = threading.local()

    BANNER = r"""
    ╔══════════════════════════════════════╗
    ║          M O N A D  v0.2.3           ║
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
        if hasattr(cls._local, 'queue') and cls._local.queue is not None:
            cls._local.queue.put(msg)

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
        lines = [f"[MONAD] 📄 执行代码:", f"{'─' * 40}"]
        for line in code_str.strip().split('\n'):
            lines.append(f"  {line}")
        lines.append(f"{'─' * 40}")
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
        """Print a final result message."""
        Output._emit("[__WS_RESULT_START__]")
        lines = [
            f"\n[MONAD] 📦 结果:",
            f"{'═' * 40}",
            str(msg),
            f"{'═' * 40}\n"
        ]
        Output._emit("\n".join(lines))
        Output._emit("[__WS_RESULT_END__]")

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
        Output._emit("─" * 50)

    @staticmethod
    def phase(phase_name: str):
        """Print a phase transition marker."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        Output._emit(f"\n[MONAD {timestamp}] ── {phase_name} ──")
