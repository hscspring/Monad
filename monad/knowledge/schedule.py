"""
MONAD Knowledge: Schedule Awareness
Reads today's calendar events and reminders on macOS via osascript.
Gracefully returns empty on non-macOS or permission errors.
"""

from __future__ import annotations

import platform
import subprocess
from datetime import datetime

from loguru import logger

_CALENDAR_SCRIPT = """\
set output to ""
set today to current date
set time of today to 0
set tomorrow to today + 1 * days

tell application "Calendar"
    repeat with cal in calendars
        set evts to (every event of cal whose start date ≥ today and start date < tomorrow)
        repeat with e in evts
            set t to start date of e
            set h to text -2 thru -1 of ("0" & (hours of t as text))
            set m to text -2 thru -1 of ("0" & (minutes of t as text))
            set output to output & h & ":" & m & " " & summary of e & linefeed
        end repeat
    end repeat
end tell
return output
"""

_REMINDERS_SCRIPT = """\
set output to ""
tell application "Reminders"
    repeat with l in lists
        set todos to (every reminder of l whose completed is false)
        repeat with r in todos
            set output to output & "- " & name of r & linefeed
        end repeat
    end repeat
end tell
return output
"""


def read_today_schedule() -> str:
    """Return today's calendar events + active reminders as a formatted string.

    Returns empty string on non-macOS or if the user hasn't granted
    Calendar/Reminders access.
    """
    if platform.system() != "Darwin":
        return ""

    parts: list[str] = []
    today = datetime.now().strftime("%Y-%m-%d")

    cal = _run_osascript(_CALENDAR_SCRIPT)
    if cal:
        parts.append(f"📅 今日日程 ({today}):\n{cal.strip()}")

    rem = _run_osascript(_REMINDERS_SCRIPT)
    if rem:
        parts.append(f"✅ 待办提醒:\n{rem.strip()}")

    return "\n\n".join(parts)


def _run_osascript(script: str) -> str:
    """Execute an AppleScript and return stdout, or empty on any error."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout
    except Exception as e:
        logger.debug(f"osascript failed (expected if no permission): {e}")
    return ""
