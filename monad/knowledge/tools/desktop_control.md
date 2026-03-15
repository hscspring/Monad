# desktop_control

Control any desktop application via screenshot + OCR + keyboard/mouse input.

## Actions

| Action | Example | Description |
|--------|---------|-------------|
| `activate <app>` | `activate Lark` | Bring an app to the foreground + auto-screenshot |
| `screenshot` | `screenshot` | Capture screen, OCR all visible text elements with coordinates |
| `click <text>` | `click 搜索` | Click the element containing the specified text |
| `double_click <text>` | `double_click report.pdf` | Double-click matching element |
| `click_xy <x> <y>` | `click_xy 320 450` | Click at exact screen coordinates |
| `type <text>` | `type Hello world` | Type text via keyboard |
| `hotkey <keys>` | `hotkey cmd space` | Press key combination |
| `find <text>` | `find 发送` | Check if text exists on screen, return its coordinates |
| `wait <seconds>` | `wait 2` | Wait for UI to update |

## Typical Workflow

1. `desktop_control activate Lark` — bring app to foreground (auto-screenshots)
2. `desktop_control screenshot` — see what's on screen
3. `desktop_control click <target>` or `desktop_control click_xy <x> <y>` — interact
4. `desktop_control wait 1` — let UI update
5. `desktop_control screenshot` — verify result
6. Repeat until task is complete

## Messaging Workflow (WeChat / Feishu)

1. `activate WeChat` — bring to foreground
2. `hotkey cmd f` (WeChat) or `hotkey cmd k` (Feishu/Lark) — open search
3. `type <contact_name>` — enter contact name
4. `wait 1` → `screenshot` — confirm search results appeared
5. `click_xy <x> <y>` — click the contact in the result list (use coordinates, not text match)
6. `wait 1` → `screenshot` — confirm chat window opened
7. `type <message>` — type the message
8. `hotkey return` — send
9. `screenshot` — verify sent

## Notes

- **Always `activate` first**: `open -a` may not bring the app to the foreground. `activate` ensures visibility and auto-screenshots.
- The `screenshot` action returns text (OCR results with coordinates), not images.
- **Use `click_xy` for search results**: After searching, use coordinates to click results — text matching may hit the search input instead of the result list.
- **Wait then screenshot**: After `type`, `click`, or `hotkey`, always `wait 1` then `screenshot` to see the updated UI.
- Hotkey names: cmd/ctrl/alt/shift/enter/tab/space/escape/backspace/up/down/left/right
- Requires optional dependencies: `pip install monad-core[desktop]`
