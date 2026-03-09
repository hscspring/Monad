"""
MONAD Interface: Voice Input (stub)
Currently uses text input. Whisper integration planned for future.
"""


class VoiceInput:
    """Input handler. Currently text-based, Whisper support planned."""

    def listen(self) -> str:
        """Wait for user input.

        Returns:
            User input as text string, or empty string for quit
        """
        try:
            text = input("\n[You] > ").strip()
            return text
        except (EOFError, KeyboardInterrupt):
            return ""
