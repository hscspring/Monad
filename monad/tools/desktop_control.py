"""
MONAD Tool: Desktop Control
Control any desktop application via screenshot + OCR + keyboard/mouse input.

Lightweight, cross-platform approach:
  - Screenshot: mss (fast, cross-platform)
  - OCR: rapidocr-onnxruntime (Chinese+English, ONNX-based)
  - Input: pynput (keyboard + mouse, actively maintained)

The LLM never sees images — OCR results are converted to a structured text
list of UI elements with coordinates, keeping the interaction text-only.
"""

import os
import platform
import time
import json
import tempfile
from pathlib import Path

IS_MAC = platform.system() == "Darwin"
IS_WIN = platform.system() == "Windows"

_ocr_engine = None
_SCREENSHOT_PATH = os.path.join(tempfile.gettempdir(), "monad_screen.png")


def _get_ocr():
    """Lazy-init OCR engine."""
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    return _ocr_engine


def _get_window_id(process_name):
    """Get CGWindowID for the main window of a process (macOS)."""
    if not IS_MAC:
        return None
    try:
        import Quartz
        windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID
        )
        for w in windows:
            if w.get("kCGWindowOwnerName", "") == process_name:
                name = w.get("kCGWindowName", "")
                if name:
                    return w["kCGWindowNumber"]
        for w in windows:
            if w.get("kCGWindowOwnerName", "") == process_name:
                return w["kCGWindowNumber"]
    except (ImportError, Exception):
        pass
    return None


def _screenshot_window(process_name):
    """Capture a specific window using macOS screencapture (works even if occluded)."""
    wid = _get_window_id(process_name)
    if wid is None:
        return None, None
    import subprocess
    result = subprocess.run(
        ["screencapture", "-l", str(wid), "-o", "-x", _SCREENSHOT_PATH],
        capture_output=True, text=True, timeout=5
    )
    if result.returncode != 0:
        return None, None
    bounds = _get_window_bounds(process_name)
    if not bounds:
        return _SCREENSHOT_PATH, None
    return _SCREENSHOT_PATH, bounds


def _screenshot(region=None):
    """Capture screen to file. Returns path to PNG."""
    import mss
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        if region:
            monitor = {
                "left": region.get("left", monitor["left"]),
                "top": region.get("top", monitor["top"]),
                "width": region.get("width", monitor["width"]),
                "height": region.get("height", monitor["height"]),
            }
        shot = sct.grab(monitor)
        mss.tools.to_png(shot.rgb, shot.size, output=_SCREENSHOT_PATH)
    return _SCREENSHOT_PATH


def _ocr(image_path):
    """Run OCR on image. Returns list of {text, x, y, w, h, confidence}."""
    engine = _get_ocr()
    result, _ = engine(image_path)
    if not result:
        return []

    elements = []
    for bbox, text, conf in result:
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        x1, y1 = int(min(xs)), int(min(ys))
        x2, y2 = int(max(xs)), int(max(ys))
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        elements.append({
            "text": text,
            "x": cx, "y": cy,
            "left": x1, "top": y1,
            "width": x2 - x1, "height": y2 - y1,
            "confidence": round(conf, 2),
        })
    return elements


def _click(x, y, button="left"):
    """Click at screen coordinates."""
    from pynput.mouse import Controller as MouseController, Button
    mouse = MouseController()
    mouse.position = (x, y)
    time.sleep(0.1)
    btn = Button.left if button == "left" else Button.right
    mouse.click(btn)


def _double_click(x, y):
    """Double-click at screen coordinates."""
    from pynput.mouse import Controller as MouseController, Button
    mouse = MouseController()
    mouse.position = (x, y)
    time.sleep(0.1)
    mouse.click(Button.left, 2)


def _type_text(text, interval=0.02):
    """Type text string via keyboard."""
    from pynput.keyboard import Controller as KeyController
    kb = KeyController()
    for ch in text:
        kb.type(ch)
        time.sleep(interval)


def _hotkey(*keys):
    """Press a hotkey combo, e.g. _hotkey('cmd', 'space') or _hotkey('ctrl', 'a')."""
    from pynput.keyboard import Controller as KeyController, Key
    kb = KeyController()

    key_map = {
        "cmd": Key.cmd, "command": Key.cmd, "meta": Key.cmd,
        "ctrl": Key.ctrl, "control": Key.ctrl,
        "alt": Key.alt, "option": Key.alt,
        "shift": Key.shift,
        "enter": Key.enter, "return": Key.enter,
        "tab": Key.tab,
        "space": Key.space,
        "backspace": Key.backspace,
        "delete": Key.delete,
        "escape": Key.esc, "esc": Key.esc,
        "up": Key.up, "down": Key.down,
        "left": Key.left, "right": Key.right,
        "home": Key.home, "end": Key.end,
    }

    resolved = []
    for k in keys:
        k_lower = k.lower()
        if k_lower in key_map:
            resolved.append(key_map[k_lower])
        elif len(k) == 1:
            resolved.append(k)
        else:
            resolved.append(k_lower)

    for k in resolved[:-1]:
        kb.press(k)
    time.sleep(0.05)
    if resolved:
        kb.press(resolved[-1])
        kb.release(resolved[-1])
    for k in reversed(resolved[:-1]):
        kb.release(k)


_MAX_ELEMENTS = 50
_MIN_TEXT_LEN = 2
_GARBLE_RE = None


def _is_garbled(text):
    """Check if text looks like OCR noise rather than real UI text."""
    global _GARBLE_RE
    if _GARBLE_RE is None:
        import re
        _GARBLE_RE = re.compile(r'^[^\w\u4e00-\u9fff]{1,4}$')
    t = text.strip()
    if len(t) < _MIN_TEXT_LEN:
        return True
    if _GARBLE_RE.match(t):
        return True
    if len(t) <= 3:
        import re
        alnum = len(re.findall(r'[\w\u4e00-\u9fff]', t))
        if alnum / len(t) < 0.6:
            return True
    return False


_SELF_NOISE_RE = None


def _is_self_noise(text):
    """Detect MONAD's own terminal output appearing in screenshots."""
    global _SELF_NOISE_RE
    if _SELF_NOISE_RE is None:
        import re
        _SELF_NOISE_RE = re.compile(
            r'\[?MONAD\]|Reasoning\s*Turn|desktop_control\]|python_exec\]|'
            r'web_fetch\]|shell\]:|'
            r'at\s*[（(]\s*\d+\s*[,，]\s*\d+\s*[）)].*size\s*\d+x\d+|'
            r'size\s+\d+x\d+.*at\s*[（(]',
            re.IGNORECASE
        )
    return bool(_SELF_NOISE_RE.search(text))


def _filter_elements(elements, app_bounds=None):
    """Remove OCR noise, terminal self-output, and limit to relevant elements.

    If app_bounds is provided ({left, top, width, height} in logical coords),
    only elements within or near the app window are kept. This prevents MONAD's
    own terminal output from leaking into the element list. A margin is added
    to include overlay panels (search dropdowns, popovers) that extend beyond
    the window edges.
    """
    MARGIN = 60  # logical pixels beyond window bounds for overlays
    if app_bounds:
        b_left = app_bounds["left"] - MARGIN
        b_top = app_bounds["top"] - MARGIN
        b_right = app_bounds["left"] + app_bounds["width"] + MARGIN
        b_bottom = app_bounds["top"] + app_bounds["height"] + MARGIN

    filtered = []
    for e in elements:
        if _is_garbled(e["text"]):
            continue
        if e["confidence"] < 0.5:
            continue
        if _is_self_noise(e["text"]):
            continue
        if app_bounds:
            if not (b_left <= e["x"] <= b_right and b_top <= e["y"] <= b_bottom):
                continue
        filtered.append(e)
    filtered.sort(key=lambda e: e["width"] * e["height"], reverse=True)
    return filtered[:_MAX_ELEMENTS]


def _get_window_bounds(process_name):
    """Get the frontmost window bounds {left, top, width, height} in logical pixels (macOS).

    Tries osascript first, falls back to Quartz CGWindowList.
    """
    if not IS_MAC:
        return None
    import subprocess
    script = (
        f'tell application "System Events" to tell process "{process_name}" to '
        f'get {{position, size}} of window 1'
    )
    try:
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            nums = [int(x.strip()) for x in r.stdout.strip().split(",")]
            if len(nums) == 4:
                return {"left": nums[0], "top": nums[1],
                        "width": nums[2], "height": nums[3]}
    except Exception:
        pass
    # Fallback: Quartz
    try:
        import Quartz
        windows = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID
        )
        for w in windows:
            if w.get("kCGWindowOwnerName", "") == process_name:
                b = w.get("kCGWindowBounds", {})
                if b:
                    return {"left": int(b["X"]), "top": int(b["Y"]),
                            "width": int(b["Width"]), "height": int(b["Height"])}
    except Exception:
        pass
    return None


def _get_frontmost_app():
    """Return the name of the frontmost application (macOS only)."""
    if not IS_MAC:
        return None
    import subprocess
    try:
        r = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first application process whose frontmost is true'],
            capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return None


_APP_ALIASES = {
    "lark": {"feishu", "飞书"},
    "feishu": {"lark", "飞书"},
    "飞书": {"lark", "feishu"},
    "wechat": {"weixin", "微信"},
    "weixin": {"wechat", "微信"},
    "微信": {"wechat", "weixin"},
}


def _is_same_app(requested: str, actual: str) -> bool:
    """Check if requested and actual app names refer to the same application."""
    r, a = requested.lower().strip(), actual.lower().strip()
    if r in a or a in r:
        return True
    aliases = _APP_ALIASES.get(r, set())
    return any(alias in a for alias in aliases)


def _activate_app(app_name):
    """Bring an application to the foreground."""
    import subprocess
    if IS_MAC:
        script = f'tell application "{app_name}" to activate'
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            time.sleep(1.5)
            front = _get_frontmost_app()
            if front and _is_same_app(app_name, front):
                return f'Activated "{app_name}" (verified in foreground)'
            return f'Activated "{app_name}" (foreground app is now: {front or "unknown"})'
        return f'Failed to activate "{app_name}": {result.stderr.strip()}'
    elif IS_WIN:
        code = (
            f'Add-Type -Name W -Namespace W -Member \'[DllImport("user32.dll")]'
            f'public static extern bool SetForegroundWindow(IntPtr h);\';'
            f'$p = Get-Process -Name "{app_name}" -ErrorAction SilentlyContinue | Select -First 1;'
            f'if($p){{[W.W]::SetForegroundWindow($p.MainWindowHandle)}}'
            f'else{{Write-Error "Process not found"}}'
        )
        result = subprocess.run(["powershell", "-Command", code],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            time.sleep(1.5)
            return f'Activated "{app_name}" (brought to foreground)'
        return f'Failed to activate "{app_name}": {result.stderr.strip()}'
    else:
        return f'activate is not supported on {platform.system()} yet. Use wmctrl or xdotool.'


def _find_all_matches(elements, target_text):
    """Find all elements matching target text. Returns (best_match, all_matches).

    Matching priority for exact matches:
    - Multiple exact matches: prefer the one with largest y. In search UIs, the input
      field is at the top (small y) and the result list is below (larger y). Clicking
      the input text is almost always wrong; the intended result is further down.
    - 1 exact: return it directly.

    Partial matches: prefer shorter text (more specific).
    """
    target = target_text.lower().strip()
    exact = [e for e in elements if e["text"].lower().strip() == target]
    partial = [e for e in elements if target in e["text"].lower() and e["text"].lower().strip() != target]
    all_matches = exact + partial
    if not all_matches:
        return None, []
    if len(exact) >= 2:
        exact.sort(key=lambda e: e["y"])
        best = exact[-1]  # largest y = lowest on screen = result list, not input field
    elif exact:
        best = exact[0]
    else:
        partial.sort(key=lambda e: len(e["text"]))
        best = partial[0]
    return best, all_matches


def _find_element(elements, target_text):
    """Find the best matching element by text (case-insensitive substring match)."""
    best, _ = _find_all_matches(elements, target_text)
    return best




def _adjust_coords_to_screen(elements, img_path, window_bounds):
    """Convert OCR pixel coords from a window screenshot to screen logical coords.

    screencapture -l on Retina produces 2x pixel images.
    Screen coords = window_position + ocr_pixel / scale_factor.
    Modifies elements in place.
    """
    try:
        from PIL import Image
        img = Image.open(img_path)
        img_w, img_h = img.size
    except Exception:
        return
    w_left = max(0, window_bounds["left"])
    w_top = window_bounds["top"]
    w_w = window_bounds["width"]
    w_h = window_bounds["height"]
    scale_x = img_w / w_w if w_w > 0 else 1
    scale_y = img_h / w_h if w_h > 0 else 1
    for e in elements:
        e["x"] = int(e["x"] / scale_x) + w_left
        e["y"] = int(e["y"] / scale_y) + w_top
        e["left"] = int(e["left"] / scale_x) + w_left
        e["top"] = int(e["top"] / scale_y) + w_top
        e["width"] = int(e["width"] / scale_x)
        e["height"] = int(e["height"] / scale_y)


def _capture_and_locate(target_text):
    """Capture the full screen, OCR, and find the target element.

    Uses mss full-screen capture so overlay panels (search dropdowns, popovers)
    are always included. mss returns logical-resolution images on macOS, so OCR
    coordinates map directly to screen logical coords usable by pynput — no scaling.

    Elements are filtered to the frontmost app's window region (+margin) to
    exclude MONAD's own terminal output from the results.

    Returns (target_element, alternatives_info_str) or an error string.
    The alternatives_info_str is empty when there's only one match.
    """
    front_app = _get_frontmost_app()
    app_bounds = _get_window_bounds(front_app) if front_app else None
    img_path = _screenshot()
    elements = _ocr(img_path)
    if app_bounds:
        elements = _filter_elements(elements, app_bounds)
    best, all_matches = _find_all_matches(elements, target_text)
    if best:
        alt_info = ""
        others = [m for m in all_matches if m is not best]
        if others:
            alt_parts = [f'"{m["text"]}" at ({m["x"]},{m["y"]})' for m in others[:5]]
            alt_info = f" Also matched: {', '.join(alt_parts)}."
            if len(others) >= 2:
                alt_info += (
                    f" WARNING: {len(others) + 1} elements match '{target_text}'. "
                    f"If this click had no effect, use click_xy <x> <y> to target the correct one."
                )
        return best, alt_info
    clean = [e["text"] for e in _filter_elements(elements)[:20]]
    return f'Element "{target_text}" not found. Visible elements: {clean}'


def run(action: str = "", **kwargs) -> str:
    """Execute a desktop control action.

    Args:
        action: One of:
            - "screenshot": Capture screen and OCR, return UI elements list
            - "click <text>": Click on UI element matching text
            - "double_click <text>": Double-click on element matching text
            - "click_xy <x> <y>": Click at exact coordinates
            - "type <text>": Type text via keyboard
            - "hotkey <key1> <key2> ...": Press hotkey combo (e.g. "hotkey cmd space")
            - "wait <seconds>": Wait for UI to update
            - "find <text>": Check if text element exists on screen
            - "activate <app>": Bring an app to the foreground (e.g. "activate Lark")

        Also accepts params as separate kwargs (e.g. action="click", text="OK").

    Returns:
        Result string describing what happened and current screen state.
    """
    if not action:
        return "Error: No action specified. Use: screenshot, click, type, hotkey, find, wait, click_xy, activate"

    parts = action.strip().split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if not arg:
        if cmd in ("click", "double_click", "find"):
            arg = kwargs.get("text", "") or kwargs.get("target", "")
        elif cmd == "type":
            arg = kwargs.get("text", "") or kwargs.get("content", "")
        elif cmd == "hotkey":
            keys = kwargs.get("keys", "")
            arg = " ".join(keys) if isinstance(keys, list) else keys
        elif cmd == "click_xy":
            x, y = kwargs.get("x", ""), kwargs.get("y", "")
            if x and y:
                arg = f"{x} {y}"
        elif cmd == "wait":
            arg = str(kwargs.get("seconds", kwargs.get("duration", "")))
        elif cmd == "activate":
            arg = kwargs.get("app", "") or kwargs.get("name", "")

    try:
        if cmd == "activate":
            if not arg:
                return "Error: activate requires app name. Usage: activate Lark"
            activate_result = _activate_app(arg)
            if "verified in foreground" not in activate_result and "foreground app is now" not in activate_result:
                return activate_result
            front_app = _get_frontmost_app()
            try:
                img_path = _screenshot()
            except Exception:
                return activate_result
            elements = _ocr(img_path)
            if not elements:
                return activate_result
            app_bounds = _get_window_bounds(front_app) if front_app else None
            elements = _filter_elements(elements, app_bounds)
            if not elements:
                return activate_result
            scope = f"{front_app} screen" if front_app else "full screen"
            lines = [activate_result,
                     f"[Auto-screenshot of {scope}] Found {len(elements)} UI elements:"]
            for e in elements:
                lines.append(f'  "{e["text"]}" at ({e["x"]},{e["y"]}) size {e["width"]}x{e["height"]}')
            lines.append("\nNow use click/type/hotkey to interact. To search for a contact: hotkey cmd k")
            return "\n".join(lines)

        elif cmd == "screenshot":
            front_app = _get_frontmost_app()
            scope = f"{front_app} screen" if front_app else "full screen"
            img_path = _screenshot()
            elements = _ocr(img_path)
            if not elements:
                return f"Screen captured ({scope}) but no text elements detected."
            app_bounds = _get_window_bounds(front_app) if front_app else None
            elements = _filter_elements(elements, app_bounds)
            if not elements:
                return f"Screen captured ({scope}) but all elements were filtered as noise. Try clicking or waiting."
            lines = [f"[{scope}] Found {len(elements)} UI elements:"]
            for e in elements:
                lines.append(f'  "{e["text"]}" at ({e["x"]},{e["y"]}) size {e["width"]}x{e["height"]}')
            return "\n".join(lines)

        elif cmd == "click":
            if not arg:
                return "Error: click requires target text. Usage: click <text>"
            result = _capture_and_locate(arg)
            if isinstance(result, str):
                return result
            target, alt_info = result
            _click(target["x"], target["y"])
            header_hint = ""
            if target["y"] < 60:
                header_hint = (
                    f' NOTE: This element is near the top of the window (y={target["y"]}), '
                    f'likely a window header/title. If this is a chat app, the chat with '
                    f'"{target["text"]}" may ALREADY be open. Try: type <message> to send '
                    f'a message directly, or click the input area at the bottom of the window.'
                )
            elif target["y"] < 120 and not alt_info:
                # Single match near the top of the window — could be the search INPUT field
                # (where the user typed the text), not the search RESULT below it.
                header_hint = (
                    f' WARNING: Only one "{target["text"]}" found at y={target["y"]} (near window top). '
                    f'This may be the SEARCH INPUT field, not the result list below. '
                    f'If the UI did not change, take a screenshot to check if the search results '
                    f'appeared below. The contact in the results list will be at a larger y coordinate.'
                )
            return f'Clicked "{target["text"]}" at ({target["x"]},{target["y"]}).{alt_info}{header_hint}'

        elif cmd == "double_click":
            if not arg:
                return "Error: double_click requires target text."
            result = _capture_and_locate(arg)
            if isinstance(result, str):
                return result
            target, alt_info = result
            _double_click(target["x"], target["y"])
            return f'Double-clicked "{target["text"]}" at ({target["x"]},{target["y"]}).{alt_info}'

        elif cmd == "click_xy":
            coords = arg.split()
            if len(coords) < 2:
                return "Error: click_xy requires x y. Usage: click_xy 320 450"
            x, y = int(coords[0]), int(coords[1])
            _click(x, y)
            return f"Clicked at ({x},{y})"

        elif cmd == "type":
            if not arg:
                return "Error: type requires text. Usage: type Hello world"
            _type_text(arg)
            return f"Typed: {arg[:50]}{'...' if len(arg) > 50 else ''}"

        elif cmd == "hotkey":
            if not arg:
                return "Error: hotkey requires keys. Usage: hotkey cmd space"
            keys = arg.split()
            _hotkey(*keys)
            return f"Pressed hotkey: {' + '.join(keys)}"

        elif cmd == "find":
            if not arg:
                return "Error: find requires target text."
            result = _capture_and_locate(arg)
            if isinstance(result, str):
                return result
            target, alt_info = result
            return f'Found "{target["text"]}" at ({target["x"]},{target["y"]}).{alt_info}'

        elif cmd == "wait":
            secs = float(arg) if arg else 1.0
            secs = min(secs, 10.0)
            time.sleep(secs)
            return f"Waited {secs}s"

        else:
            return f"Unknown action: {cmd}. Available: screenshot, click, double_click, click_xy, type, hotkey, find, wait"

    except ImportError as e:
        pkg = str(e).split("'")[-2] if "'" in str(e) else str(e)
        return f"Missing dependency: {pkg}. Install with: pip install mss pynput rapidocr-onnxruntime"
    except Exception as e:
        return f"Desktop control error: {type(e).__name__}: {e}"


TOOL_META = {
    "name": "desktop_control",
    "description": "Control any desktop application via screenshot + OCR + keyboard/mouse. "
                   "Actions: activate <app>, screenshot, click <text>, type <text>, hotkey <keys>, "
                   "find <text>, click_xy <x> <y>, double_click <text>, wait <seconds>.",
    "inputs": ["action"],
}
