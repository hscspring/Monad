"""
MONAD Proactive: Notification
Routes proactive task results to the appropriate channel based on launch mode.
"""

import subprocess

from loguru import logger

import monad.config as config_module
from monad.interface.output import Output


def notify(title: str, content: str, channel: str = "auto") -> None:
    """Send a notification through the appropriate channel.

    Args:
        title: Notification title / subject.
        content: Notification body text.
        channel: "auto" (follow launch mode), "web", "feishu", "cli", "desktop".
    """
    if channel == "auto":
        channel = config_module.LAUNCH_MODE

    try:
        if channel == "web":
            _notify_web(title, content)
        elif channel == "feishu":
            _notify_feishu(title, content)
        elif channel == "cli":
            _notify_cli(title, content)
        elif channel == "desktop":
            _notify_desktop(title, content)
        else:
            _notify_cli(title, content)
    except Exception as e:
        logger.warning(f"Notification failed ({channel}): {e}")
        _notify_cli(title, content)


def _notify_web(title: str, content: str) -> None:
    """Push notification via Output (reaches WebSocket log stream)."""
    Output.system(f"[Proactive] {title}")
    Output.result(content)


def _notify_feishu(title: str, content: str) -> None:
    """Send via Feishu — requires feishu module's client to be available."""
    from monad.proactive._feishu_bridge import send_proactive_feishu

    send_proactive_feishu(f"{title}\n\n{content}")


def _notify_cli(title: str, content: str) -> None:
    """Print to terminal via Output."""
    Output.system(f"[Proactive] {title}")
    Output.result(content)


def _notify_desktop(title: str, content: str) -> None:
    """macOS desktop notification via osascript."""
    import platform

    if platform.system() != "Darwin":
        _notify_cli(title, content)
        return
    script = (
        f'display notification "{_escape_applescript(content)}" '
        f'with title "MONAD" subtitle "{_escape_applescript(title)}"'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            timeout=5, capture_output=True,
        )
    except Exception:
        _notify_cli(title, content)


def _escape_applescript(text: str) -> str:
    """Escape text for AppleScript string literals."""
    return text.replace("\\", "\\\\").replace('"', '\\"')[:200]
