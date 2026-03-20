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
import re
import time
import tempfile

from monad.config import (
    MAX_OCR_ELEMENTS, MIN_OCR_TEXT_LEN,
    OCR_CONFIDENCE_THRESHOLD, WINDOW_FILTER_MARGIN, TIMEOUT_SUBPROCESS,
)

IS_MAC = platform.system() == "Darwin"
IS_WIN = platform.system() == "Windows"

_ocr_engine = None
_SCREENSHOT_PATH = os.path.join(tempfile.gettempdir(), "monad_screen.png")


# ── OCR ──────────────────────────────────────────────────────────

def _get_ocr():
    """Lazy-init OCR engine."""
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    return _ocr_engine


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
        elements.append({
            "text": text,
            "x": (x1 + x2) // 2, "y": (y1 + y2) // 2,
            "left": x1, "top": y1,
            "width": x2 - x1, "height": y2 - y1,
            "confidence": round(conf, 2),
        })
    return elements


# ── Window Management (macOS) ────────────────────────────────────

def _list_windows(process_name=None):
    """List on-screen windows, optionally filtered by process name.

    Returns list of dicts with kCGWindowOwnerName, kCGWindowName,
    kCGWindowNumber, kCGWindowBounds.
    """
    if not IS_MAC:
        return []
    try:
        import Quartz
        raw = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID,
        )
        if process_name:
            return [w for w in raw if w.get("kCGWindowOwnerName", "") == process_name]
        return list(raw)
    except (ImportError, Exception):
        return []


def _get_window_id(process_name):
    """Get CGWindowID for the main window of a process (macOS)."""
    windows = _list_windows(process_name)
    for w in windows:
        if w.get("kCGWindowName", ""):
            return w["kCGWindowNumber"]
    return windows[0]["kCGWindowNumber"] if windows else None


def _get_window_bounds(process_name):
    """Get the LARGEST window bounds for a process in logical pixels (macOS)."""
    windows = _list_windows(process_name)
    best, best_area = None, 0
    for w in windows:
        b = w.get("kCGWindowBounds", {})
        if not b:
            continue
        area = b.get("Width", 0) * b.get("Height", 0)
        if area > best_area:
            best_area = area
            best = {
                "left": int(b["X"]), "top": int(b["Y"]),
                "width": int(b["Width"]), "height": int(b["Height"]),
            }
    return best


def _get_frontmost_app():
    """Return the name of the frontmost application (macOS only)."""
    if not IS_MAC:
        return None
    import subprocess
    try:
        r = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first application process whose frontmost is true'],
            capture_output=True, text=True, timeout=TIMEOUT_SUBPROCESS)
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return None


# ── Screenshot ───────────────────────────────────────────────────

def _screenshot_window(process_name):
    """Capture a specific window using macOS screencapture."""
    wid = _get_window_id(process_name)
    if wid is None:
        return None, None
    import subprocess
    result = subprocess.run(
        ["screencapture", "-l", str(wid), "-o", "-x", _SCREENSHOT_PATH],
        capture_output=True, text=True, timeout=TIMEOUT_SUBPROCESS,
    )
    if result.returncode != 0:
        return None, None
    bounds = _get_window_bounds(process_name)
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


# ── Input Simulation ─────────────────────────────────────────────

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
    """Press a hotkey combo, e.g. _hotkey('cmd', 'space')."""
    from pynput.keyboard import Controller as KeyController, Key
    kb = KeyController()

    key_map = {
        "cmd": Key.cmd, "command": Key.cmd, "meta": Key.cmd,
        "ctrl": Key.ctrl, "control": Key.ctrl,
        "alt": Key.alt, "option": Key.alt,
        "shift": Key.shift,
        "enter": Key.enter, "return": Key.enter,
        "tab": Key.tab, "space": Key.space,
        "backspace": Key.backspace, "delete": Key.delete,
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


# ── OCR Filtering ────────────────────────────────────────────────

_GARBLE_RE = re.compile(r'^[^\w\u4e00-\u9fff]{1,4}$')
_ALNUM_RE = re.compile(r'[\w\u4e00-\u9fff]')
_SELF_NOISE_RE = re.compile(
    r'MONAD[】\]」]|[【\[「]MONAD|'
    r'Reasoning\s*Turn|desktop_control|python_exec|'
    r'web_fetch|shell\]|'
    r'LLM\s*返回类型|正在调用\s*LLM|LLM\s*进行推理|'
    r'检测到空洞回答|强制要求执行|声称完成操作|'
    r'已在前台.*跳过重复|自动截屏|截屏替代|'
    r'at\s*[（(]\s*\d+\s*[,，]\s*\d+\s*[）)].*size\s*\d+x\d+|'
    r'size\s+\d+x\d+.*at\s*[（(]|'
    r'\d+x\d+.*at\s*[（(]\s*\d+',
    re.IGNORECASE
)


def _is_garbled(text):
    """Check if text looks like OCR noise rather than real UI text."""
    t = text.strip()
    if len(t) < MIN_OCR_TEXT_LEN:
        return True
    if _GARBLE_RE.match(t):
        return True
    if len(t) <= 3:
        alnum = len(_ALNUM_RE.findall(t))
        if alnum / len(t) < 0.6:
            return True
    return False


def _filter_elements(elements, app_bounds=None):
    """Remove OCR noise, terminal self-output, and limit to relevant elements."""
    if app_bounds:
        b_left = app_bounds["left"] - WINDOW_FILTER_MARGIN
        b_top = app_bounds["top"] - WINDOW_FILTER_MARGIN
        b_right = app_bounds["left"] + app_bounds["width"] + WINDOW_FILTER_MARGIN
        b_bottom = app_bounds["top"] + app_bounds["height"] + WINDOW_FILTER_MARGIN

    filtered = []
    for e in elements:
        if _is_garbled(e["text"]):
            continue
        if e["confidence"] < OCR_CONFIDENCE_THRESHOLD:
            continue
        if _SELF_NOISE_RE.search(e["text"]):
            continue
        if app_bounds:
            if not (b_left <= e["x"] <= b_right and b_top <= e["y"] <= b_bottom):
                continue
        filtered.append(e)
    filtered.sort(key=lambda e: e["width"] * e["height"], reverse=True)
    return filtered[:MAX_OCR_ELEMENTS]


# ── Element Matching ─────────────────────────────────────────────

def _find_all_matches(elements, target_text):
    """Find all elements matching target text. Returns (best_match, all_matches)."""
    target = target_text.lower().strip()
    exact = [e for e in elements if e["text"].lower().strip() == target]
    partial = [e for e in elements if target in e["text"].lower() and e["text"].lower().strip() != target]
    all_matches = exact + partial
    if not all_matches:
        return None, []
    if len(exact) >= 2:
        exact.sort(key=lambda e: e["y"])
        best = exact[-1]
    elif exact:
        best = exact[0]
    else:
        partial.sort(key=lambda e: len(e["text"]))
        best = partial[0]
    return best, all_matches


# ── App Aliases ──────────────────────────────────────────────────

_APP_ALIASES = {
    "lark": {"feishu", "飞书"}, "feishu": {"lark", "飞书"}, "飞书": {"lark", "feishu"},
    "wechat": {"weixin", "微信"}, "weixin": {"wechat", "微信"}, "微信": {"wechat", "weixin"},
}


def _is_same_app(requested: str, actual: str) -> bool:
    """Check if requested and actual app names refer to the same application."""
    r, a = requested.lower().strip(), actual.lower().strip()
    if r in a or a in r:
        return True
    aliases = _APP_ALIASES.get(r, set())
    return any(alias in a for alias in aliases)


# ── Activate ─────────────────────────────────────────────────────

def _activate_app(app_name):
    """Bring an application to the foreground."""
    import subprocess
    if IS_MAC:
        script = f'tell application "{app_name}" to activate'
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True, timeout=TIMEOUT_SUBPROCESS)
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
                                capture_output=True, text=True, timeout=TIMEOUT_SUBPROCESS)
        if result.returncode == 0:
            time.sleep(1.5)
            return f'Activated "{app_name}" (brought to foreground)'
        return f'Failed to activate "{app_name}": {result.stderr.strip()}'
    else:
        return f'activate is not supported on {platform.system()} yet. Use wmctrl or xdotool.'


# ── Coordinate Adjustment ────────────────────────────────────────

def _adjust_coords_to_screen(elements, img_path, window_bounds):
    """Convert OCR pixel coords from a window screenshot to screen logical coords."""
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


# ── Capture & Locate ─────────────────────────────────────────────

def _capture_and_locate(target_text):
    """Capture full screen, OCR, find target element.

    Returns (target_element, alternatives_info_str) or an error string.
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


def _screenshot_and_list_elements():
    """Capture screen, OCR, filter, return formatted element list string."""
    front_app = _get_frontmost_app()
    scope = f"{front_app} screen" if front_app else "full screen"
    img_path = _screenshot()
    elements = _ocr(img_path)
    if not elements:
        return f"Screen captured ({scope}) but no text elements detected."
    app_bounds = _get_window_bounds(front_app) if front_app else None
    elements = _filter_elements(elements, app_bounds)
    if not elements:
        return f"Screen captured ({scope}) but all elements were filtered as noise."
    return _format_elements(elements, scope)


def _format_elements(elements, scope="screen"):
    """Format element list into a readable string."""
    lines = [f"[{scope}] Found {len(elements)} UI elements:"]
    for e in elements:
        lines.append(f'  "{e["text"]}" at ({e["x"]},{e["y"]}) size {e["width"]}x{e["height"]}')
    return "\n".join(lines)


# ── Command Handlers ─────────────────────────────────────────────

def _cmd_activate(arg, **kwargs):
    if not arg:
        return "Error: activate requires app name. Usage: activate Lark"
    result = _activate_app(arg)
    if "verified in foreground" not in result and "foreground app is now" not in result:
        return result
    # Auto-screenshot after successful activation
    front_app = _get_frontmost_app()
    try:
        img_path = _screenshot()
    except Exception:
        return result
    elements = _ocr(img_path)
    if not elements:
        return result
    app_bounds = _get_window_bounds(front_app) if front_app else None
    elements = _filter_elements(elements, app_bounds)
    if not elements:
        return result
    scope = f"{front_app} screen" if front_app else "full screen"
    return f"{result}\n{_format_elements(elements, f'Auto-screenshot of {scope}')}\n\nNow use click/type/hotkey to interact."


def _cmd_screenshot(arg="", **kwargs):
    return _screenshot_and_list_elements()


def _cmd_click(arg, **kwargs):
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
        header_hint = (
            f' WARNING: Only one "{target["text"]}" found at y={target["y"]} (near window top). '
            f'This may be the SEARCH INPUT field, not the result list below. '
            f'If the UI did not change, take a screenshot to check if the search results '
            f'appeared below. The contact in the results list will be at a larger y coordinate.'
        )
    return f'Clicked "{target["text"]}" at ({target["x"]},{target["y"]}).{alt_info}{header_hint}'


def _cmd_double_click(arg, **kwargs):
    if not arg:
        return "Error: double_click requires target text."
    result = _capture_and_locate(arg)
    if isinstance(result, str):
        return result
    target, alt_info = result
    _double_click(target["x"], target["y"])
    return f'Double-clicked "{target["text"]}" at ({target["x"]},{target["y"]}).{alt_info}'


def _cmd_click_xy(arg, **kwargs):
    coords = arg.split()
    if len(coords) < 2:
        return "Error: click_xy requires x y. Usage: click_xy 320 450"
    x, y = int(coords[0]), int(coords[1])
    _click(x, y)
    return f"Clicked at ({x},{y})"


def _cmd_type(arg, **kwargs):
    if not arg:
        return "Error: type requires text. Usage: type Hello world"
    _type_text(arg)
    return f"Typed: {arg[:50]}{'...' if len(arg) > 50 else ''}"


def _cmd_hotkey(arg, **kwargs):
    if not arg:
        return "Error: hotkey requires keys. Usage: hotkey cmd space"
    keys = arg.split()
    _hotkey(*keys)
    return f"Pressed hotkey: {' + '.join(keys)}"


def _cmd_find(arg, **kwargs):
    if not arg:
        return "Error: find requires target text."
    result = _capture_and_locate(arg)
    if isinstance(result, str):
        return result
    target, alt_info = result
    return f'Found "{target["text"]}" at ({target["x"]},{target["y"]}).{alt_info}'


def _cmd_wait(arg, **kwargs):
    secs = float(arg) if arg else 1.0
    secs = min(secs, 10.0)
    time.sleep(secs)
    return f"Waited {secs}s"


_COMMANDS = {
    "activate": _cmd_activate,
    "screenshot": _cmd_screenshot,
    "click": _cmd_click,
    "double_click": _cmd_double_click,
    "click_xy": _cmd_click_xy,
    "type": _cmd_type,
    "hotkey": _cmd_hotkey,
    "find": _cmd_find,
    "wait": _cmd_wait,
}


# ── Main Entry Point ─────────────────────────────────────────────

def run(action: str = "", **kwargs) -> str:
    """Execute a desktop control action.

    Args:
        action: One of: screenshot, click <text>, double_click <text>,
                click_xy <x> <y>, type <text>, hotkey <key1> <key2> ...,
                wait <seconds>, find <text>, activate <app>
    """
    if not action:
        return f"Error: No action specified. Available: {', '.join(_COMMANDS)}"

    parts = action.strip().split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    # Resolve arg from kwargs if not inline
    if not arg:
        _kwarg_map = {
            "click": ("text", "target"),
            "double_click": ("text", "target"),
            "find": ("text", "target"),
            "type": ("text", "content"),
            "click_xy": None,
            "hotkey": None,
            "wait": None,
            "activate": ("app", "name"),
        }
        kw_keys = _kwarg_map.get(cmd)
        if kw_keys:
            for k in kw_keys:
                if kwargs.get(k):
                    arg = kwargs[k]
                    break
        elif cmd == "click_xy":
            x, y = kwargs.get("x", ""), kwargs.get("y", "")
            if x and y:
                arg = f"{x} {y}"
        elif cmd == "hotkey":
            keys = kwargs.get("keys", "")
            arg = " ".join(keys) if isinstance(keys, list) else keys
        elif cmd == "wait":
            arg = str(kwargs.get("seconds", kwargs.get("duration", "")))

    handler = _COMMANDS.get(cmd)
    if not handler:
        return f"Unknown action: {cmd}. Available: {', '.join(_COMMANDS)}"

    try:
        return handler(arg)
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
