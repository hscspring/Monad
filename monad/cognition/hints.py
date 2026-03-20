"""
MONAD Cognition: Action Hints
Post-action contextual hints to guide the LLM to the next logical step.
"""

import re


def action_hint(capability: str, params: dict, result: str,
                user_input: str = "") -> str:
    """Generate contextual hints to guide the LLM to the next logical step."""
    if capability == "shell":
        return _shell_hint(params, result)
    if capability == "desktop_control":
        return _desktop_hint(params, result, user_input)
    return ""


# ── Regex Helpers ────────────────────────────────────────────────

_RE_OPEN_APP = re.compile(r'open\s+-a\s+["\']?(\w+)')
_RE_SEND_TO = re.compile(r'["\']发送给\s*(\S+?)["\']')
_RE_QUOTED_MSG = re.compile(r'[""「\'"]([^"""\'」]{1,50})[""」\'"]')


def extract_open_app(cmd: str) -> str | None:
    """Extract app name from 'open -a <app>' commands."""
    m = _RE_OPEN_APP.search(cmd)
    return m.group(1) if m else None


def extract_send_to_contact(text: str) -> str | None:
    """Extract contact name from '发送给 <name>' patterns."""
    m = _RE_SEND_TO.search(text)
    return m.group(1) if m else None


def extract_quoted_message(text: str) -> str | None:
    """Extract the first quoted message from user input."""
    m = _RE_QUOTED_MSG.search(text)
    return m.group(1) if m else None


# ── Shell Hints ──────────────────────────────────────────────────

def _shell_hint(params: dict, result: str) -> str:
    cmd = params.get("command", "")
    app = extract_open_app(cmd)
    if app and "error" not in result.lower() and "unable" not in result.lower():
        return (
            f"[Hint: '{app}' has been opened. Your next steps should be: "
            f"1) desktop_control activate {app} — to bring it to foreground, "
            f"2) desktop_control wait 2 — let UI load, "
            f"3) desktop_control screenshot — to see the UI elements. "
            f"Do NOT run open -a again.]"
        )
    return ""


# ── Desktop Hints ────────────────────────────────────────────────

def _desktop_hint(params: dict, result: str, user_input: str) -> str:
    action = params.get("action", "")

    if action.startswith("activate"):
        return _hint_activate(result)
    if action == "screenshot" and "UI elements" in result:
        return _hint_screenshot(result)
    if action.startswith("hotkey"):
        return _hint_hotkey(action, result)
    if action.startswith("wait"):
        return _hint_wait()
    if action.startswith("type"):
        return _hint_type(action)
    if action.startswith("click"):
        return _hint_click(action, result, user_input)
    return ""


def _hint_activate(result: str) -> str:
    if "foreground" not in result.lower():
        return ""
    if "Auto-screenshot" in result:
        return (
            "[Hint: App is in foreground and UI elements are shown above. "
            "Use click/type/hotkey to interact NOW. Do NOT run open/activate/screenshot again. "
            "Refer to the desktop_control tool docs for app-specific shortcuts.]"
        )
    return (
        "[Hint: App is now in foreground. Next: desktop_control screenshot "
        "to see UI elements, then click/type to interact.]"
    )


def _hint_screenshot(result: str) -> str:
    contact = extract_send_to_contact(result)
    if contact:
        return (
            f'[Hint: "发送给{contact}" button visible. '
            f'Click it to open chat, then type message and hotkey return.]'
        )
    if any(kw in result for kw in ("Search", "搜索", "search")):
        return (
            "[Hint: Search box is open. Type the CONTACT NAME to search, "
            "then wait 1 + screenshot to see results. "
            "Do NOT type the message content yet.]"
        )
    return (
        "[Hint: Screen captured. Use click/type/hotkey to interact. "
        "Do NOT take another screenshot until you've performed an action. "
        "Refer to desktop_control tool docs for app-specific workflows.]"
    )


def _hint_hotkey(action: str, result: str) -> str:
    if "Pressed hotkey" not in result:
        return ""
    keys = action.replace("hotkey", "").strip().lower()
    if keys in ("cmd f", "cmd k"):
        return (
            "[Hint: Search shortcut pressed. Now type the CONTACT NAME (not the message). "
            "Then wait 1 + screenshot to see results.]"
        )
    return ""


def _hint_wait() -> str:
    return (
        "[Hint: Wait complete. NOW take a screenshot immediately: "
        "desktop_control screenshot — to see the current state of the UI. "
        "Do NOT skip the screenshot. Do NOT repeat previous actions.]"
    )


def _hint_type(action: str) -> str:
    typed_text = action[4:].strip() if len(action) > 4 else ""
    return (
        f'[Hint: Typed "{typed_text}". Wait for search results, then screenshot: '
        f'1) desktop_control wait 1  '
        f'2) desktop_control screenshot — find the contact in the RESULT LIST (larger y value). '
        f'IMPORTANT: Do NOT use "click {typed_text}" — that may hit the search INPUT box. '
        f'Instead use click_xy <x> <y> with the exact coordinates of the contact in the result list.]'
    )


def _hint_click(action: str, result: str, user_input: str) -> str:
    if "Also matched:" in result:
        return (
            "[Hint: Multiple elements matched your click target. If the clicked element "
            "was a search input (not a result), the UI won't change. Check the 'Also matched' "
            "alternatives and try clicking one with more context text (e.g. a search result item).]"
        )

    contact = extract_send_to_contact(result)
    if contact and "发送给" in result:
        if "发送给" in action:
            msg = extract_quoted_message(user_input) or "<消息内容>"
            return (
                f'[Hint: "发送给{contact}" clicked — chat is now open. '
                f'The input box is already focused. Do these steps IN ORDER:\n'
                f'1. desktop_control wait 1\n'
                f'2. desktop_control type {msg}\n'
                f'3. desktop_control hotkey return\n'
                f'Do NOT click the input area, do NOT screenshot first, just type directly.]'
            )
        return (
            f'[Hint: Click succeeded and "发送给{contact}" button appeared. '
            f'Click it to open the chat: click 发送给{contact} '
            f'— then type your message and hotkey return to send.]'
        )

    if "WARNING: Only one" in result and "SEARCH INPUT" in result:
        return (
            "[Hint: The click may have landed on the SEARCH INPUT field (where you typed), "
            "not the contact in the RESULT LIST below. "
            "Do: desktop_control wait 1 → desktop_control screenshot. "
            "In the screenshot, look for the contact name at a LOWER position (larger y). "
            "If you see it, use click_xy <x> <y> with those exact coordinates to click it.]"
        )

    if "Clicked" in result:
        msg = extract_quoted_message(user_input)
        if msg:
            return (
                f"[Hint: Click executed. The chat window should now be open. "
                f"Your EXACT next steps — do them IN ORDER, no skipping:\n"
                f"1. desktop_control wait 1\n"
                f"2. desktop_control screenshot — confirm the chat is open\n"
                f"3. desktop_control type {msg}\n"
                f"4. desktop_control hotkey return — SEND the message\n"
                f"5. desktop_control screenshot — confirm message was sent\n"
                f"Do NOT activate, do NOT open, do NOT search again.]"
            )
        return (
            "[Hint: Click executed. Now wait for the UI to respond: "
            "desktop_control wait 1 — then desktop_control screenshot "
            "to confirm whether the chat/page opened. "
            "Do NOT click/activate/open again without first seeing the updated screen.]"
        )
    return ""
