# desktop_control

Control any desktop application via screenshot + OCR + keyboard/mouse input.

## Actions

| Action | Example | Description |
|--------|---------|-------------|
| `activate <app>` | `activate Lark` | Bring an app to the foreground |
| `screenshot` | `screenshot` | Capture screen, OCR all visible text elements with coordinates |
| `click <text>` | `click 搜索` | Click the element containing the specified text |
| `double_click <text>` | `double_click report.pdf` | Double-click matching element |
| `click_xy <x> <y>` | `click_xy 320 450` | Click at exact screen coordinates |
| `type <text>` | `type Hello world` | Type text via keyboard |
| `hotkey <keys>` | `hotkey cmd space` | Press key combination |
| `find <text>` | `find 发送` | Check if text exists on screen, return its coordinates |
| `wait <seconds>` | `wait 2` | Wait for UI to update |

## Typical Workflow

1. Use `shell` to open the target app: `open -a "Lark"` (macOS) or `start lark` (Windows)
2. `desktop_control activate Lark` — bring the app to the foreground
3. `desktop_control wait 2` — let the UI load
4. `desktop_control screenshot` — see what's on screen
5. `desktop_control click <target>` — click a button or field
6. `desktop_control type <text>` — enter text
7. `desktop_control screenshot` — verify the result
8. Repeat until task is complete

## Notes

- **Always `activate` first**: `open -a` may not bring the app to the foreground. Use `activate` to ensure it's visible before taking screenshots.
- The `screenshot` action returns a text list of UI elements (not an image), keeping interaction lightweight. OCR noise is auto-filtered.
- Use `find` to check if an expected element has appeared before clicking.
- Use `wait` between actions if the UI needs time to respond.
- Hotkey names: cmd/ctrl/alt/shift/enter/tab/space/escape/backspace/up/down/left/right
- Requires optional dependencies: `pip install monad-core[desktop]`
