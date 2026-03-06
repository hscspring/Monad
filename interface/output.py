"""
MONAD Interface: Output
Formatted output with MONAD state prefixes.
All process steps are printed so the user can see exactly what MONAD is doing.
"""

from datetime import datetime


class Output:
    """Handles formatted output for MONAD."""

    BANNER = r"""
    ╔══════════════════════════════════════╗
    ║          M O N A D  v0.1             ║
    ║    Personal AGI Operating Core       ║
    ╚══════════════════════════════════════╝
    """

    @staticmethod
    def banner():
        """Print the MONAD startup banner."""
        print(Output.BANNER)

    @staticmethod
    def status(state: str):
        """Print a status message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[MONAD {timestamp}] {state}")

    @staticmethod
    def system(msg: str):
        """Print a system message."""
        print(f"[MONAD] ⚙️  {msg}")

    @staticmethod
    def thinking(msg: str):
        """Print a thinking/reasoning message — shows MONAD's thought process."""
        print(f"[MONAD] 🧠 思考: {msg}")

    @staticmethod
    def action(capability: str, detail: str):
        """Print an action being taken."""
        print(f"[MONAD] ⚡ 行动 [{capability}]: {detail}")

    @staticmethod
    def code(code_str: str):
        """Print the code MONAD is about to execute."""
        print(f"[MONAD] 📄 执行代码:")
        print(f"{'─' * 40}")
        for line in code_str.strip().split('\n'):
            print(f"  {line}")
        print(f"{'─' * 40}")

    @staticmethod
    def observation(msg: str):
        """Print an observation/result from an action."""
        print(f"[MONAD] 👁️  观察: {msg}")

    @staticmethod
    def skill_check(msg: str):
        """Print skill self-check status."""
        print(f"[MONAD] 🔍 自检: {msg}")

    @staticmethod
    def learning(msg: str):
        """Print a learning/reflection message."""
        print(f"[MONAD] 📝 学习: {msg}")

    @staticmethod
    def result(msg: str):
        """Print a final result message."""
        print(f"\n[MONAD] 📦 结果:")
        print(f"{'═' * 40}")
        print(msg)
        print(f"{'═' * 40}\n")

    @staticmethod
    def error(msg: str):
        """Print an error message."""
        print(f"[MONAD] ❌ 错误: {msg}")

    @staticmethod
    def warn(msg: str):
        """Print a warning message."""
        print(f"[MONAD] ⚠️  警告: {msg}")

    @staticmethod
    def divider():
        """Print a visual divider."""
        print("─" * 50)

    @staticmethod
    def phase(phase_name: str):
        """Print a phase transition marker."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n[MONAD {timestamp}] ── {phase_name} ──")
