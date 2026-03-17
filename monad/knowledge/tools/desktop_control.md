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

1. `activate <App>` — bring app to foreground (auto-screenshots)
2. `screenshot` — see what's on screen
3. `click <target>` or `click_xy <x> <y>` — interact
4. `wait 1` — let UI update
5. `screenshot` — verify result
6. Repeat until task is complete

## Messaging Workflow (WeChat / Feishu)

### Search Shortcuts

- **飞书 (Lark)**: `hotkey cmd k`
- **微信 (WeChat)**: `hotkey cmd f`

### Full Messaging Flow

1. `activate <App>` — bring to foreground
2. Press search shortcut (see above)
3. `type <联系人名>` — enter contact name
4. `wait 1` → `screenshot` — confirm search results appeared (async rendering)
5. `click_xy <x> <y>` — click contact in the **result list** (use coordinates, NOT text match — text match may hit the search input instead)
6. If "发送给 XXX" button appears → click it to enter the chat
7. `type <消息内容>` — type the message
8. `hotkey return` — send
9. `screenshot` — verify sent

### Critical Rules

- **发消息必须完成全流程**：缺少 `type` 步骤 = 消息没输入。缺少 `hotkey return` = 消息没发出去。
- **聊天可能已经打开**：如果联系人名字出现在窗口顶部（y 坐标很小），说明聊天已打开。不需要再搜索，直接 `type <消息>` → `hotkey return` 发送。反复点击标题栏上的名字不会有效果。
- **"发送给 XXX" 面板**：cmd+k 搜索后点击联系人会弹出"发送给 XXX"按钮，**必须点击该按钮**才能进入聊天。点击后聊天打开，直接 type 消息。
- **不要点击输入框**：聊天窗口打开后，输入焦点**默认在消息输入框**。直接 `type` 即可。**不要**点击底部工具栏（如 "Aa"、"@"、表情图标等），那不是输入框——会弹出格式菜单或触发系统截图工具。
- **搜索结果用坐标点击**：`click <联系人名>` 会匹配到搜索框里的输入文字，要用 `click_xy` 点击结果列表里的联系人（y 坐标明显大于搜索框）。
- **搜索场景的 click 陷阱**：click 返回 "Also matched" 时，优先点击带上下文的选项（如 `click 问一问：百合`），搜索框里的文字点了不会跳转。
- **点击后必须等待再截图**：点击后先 `wait 1`，再 `screenshot` 确认界面已切换。不要连续点击同一元素。

## General Notes

- **Always `activate` first**: `open -a` may not bring the app to foreground. `activate` ensures visibility and auto-screenshots.
- The `screenshot` action returns text (OCR results with coordinates), not images.
- Hotkey names: cmd/ctrl/alt/shift/enter/tab/space/escape/backspace/up/down/left/right
- Requires optional dependencies: `pip install monad-core[desktop]`
