# Tool: web_fetch

MONAD 的互联网感知能力——直接看到网页上的内容。

## Description

Fetch and extract web page content. MONAD's internet perception capability (eyes 👁️).
Through web_fetch, MONAD can directly see what's on any web page without writing code.

## Three Modes

| 模式 | 参数 | 适用场景 | 速度 |
|------|------|----------|------|
| `fast` | mode="fast"（默认） | 大多数普通网页 | ⚡ 最快 |
| `stealth` | mode="stealth" | Cloudflare/反爬保护的页面 | 🐢 较慢 |
| `browser` | mode="browser" | 需要 JS 渲染的 SPA/动态页面 | 🐌 最慢 |

## Input

- **url**: 目标网页 URL（必填）
- **mode**: 抓取模式——"fast"、"stealth"、"browser"（默认 "fast"）
- **selector**: CSS 选择器，精确提取页面元素（可选）
- **wait_selector**: 等待元素出现后再提取，仅 browser 模式（可选）
- **timeout**: 超时秒数（默认 30）

## Output

页面文本内容（最多 5000 字符），或通过 selector 提取的元素文本。

## Usage Examples

### 搜索信息
```json
{"type": "action", "capability": "web_fetch", "params": {"url": "https://www.bing.com/search?q=今日新闻"}}
```

### 抓取指定网页
```json
{"type": "action", "capability": "web_fetch", "params": {"url": "https://news.ycombinator.com", "selector": ".titleline a"}}
```

### 绕过 Cloudflare
```json
{"type": "action", "capability": "web_fetch", "params": {"url": "https://protected-site.com", "mode": "stealth"}}
```

### JS 渲染页面
```json
{"type": "action", "capability": "web_fetch", "params": {"url": "https://spa-app.com", "mode": "browser", "selector": ".content"}}
```

## 工具选择策略

1. 需要网页内容 → 优先用 web_fetch（而非 python_exec + requests）
2. fast 失败 → 尝试 stealth → 再尝试 browser
3. 需要对抓取结果做复杂处理 → 先 web_fetch 获取，再 python_exec 处理
