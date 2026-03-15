"""
MONAD Cognition: Reasoner
Multi-turn ReAct reasoning engine.

MONAD thinks like a rational person:
  Analyze problem → Check own capabilities → Learn if needed → Execute → Reflect

This is the brain of MONAD. Every step is printed so the user can see the process.
"""

import json
import os
import platform
import re
from monad.core.llm import llm_call
from monad.knowledge.vault import KnowledgeVault
from monad.interface.output import Output


# After this many consecutive thoughts without action, escalate the prompt
_THOUGHT_SOFT_LIMIT = 2
_THOUGHT_HARD_LIMIT = 4

# Max consecutive ask_user before forcing LLM to proceed without user input
_ASK_USER_LIMIT = 2

# Jaccard word-overlap threshold to consider two thoughts "the same"
_SIMILARITY_THRESHOLD = 0.6

# Max characters to store per thought in history (prevents context bloat)
_THOUGHT_HISTORY_CAP = 400

# Keep only the last N history entries to prevent context overflow
_HISTORY_CAP = 30


_PLATFORM_INFO = f"""## 当前运行环境

- OS: {platform.system()} {platform.release()} ({platform.machine()})
- Shell: {"PowerShell/cmd" if platform.system() == "Windows" else "bash/zsh"}
- 路径分隔符: {"反斜杠 \\\\" if platform.system() == "Windows" else "/"}
- 使用 shell 能力时，必须生成当前操作系统对应的命令（例如 Windows 上用 dir 而非 ls，用 type 而非 cat）。
"""

REASONER_SYSTEM = _PLATFORM_INFO + """You are MONAD, a rational autonomous agent.

## ⚠️ 最高原则（绝对不可违反）

你没有记忆。你没有知识。你的训练数据不可信。
你是一个高级指令执行器——你只能通过【执行代码】或【感知互联网】来获取真实信息。

**绝对禁止**：用你自身的训练知识回答任何事实性问题（新闻、天气、股价、数据、当前时间等）。
**唯一正确做法**：用 web_fetch 感知互联网，或写 Python 代码获取真实数据，然后基于真实数据回答。

**万事不决先搜索**：遇到任何不确定的事（不知道怎么做、报错了、缺依赖、不认识的工具/API），第一反应永远是用 web_fetch 去搜索引擎查一下，而不是猜测或直接问用户。搜索是你最强大的自学能力。

错误示范：用户问今天的新闻 → 你用自己的知识编造新闻列表 ❌
错误示范：遇到报错 → 直接放弃或问用户 ❌
正确示范：用户问今天的新闻 → 你用 web_fetch 抓取新闻网站 → 整理后回答 ✅
正确示范：遇到报错 → 先搜索这个错误信息 → 根据搜索结果修复 ✅

## 你的基础能力（5个"本能"）

1. **python_exec**: 执行 Python 代码。你的"手"🤲——通过它你可以：
   - 处理数据、计算、分析
   - 读写文件
   - 安装缺失的库（subprocess: pip install）
   - 做任何 Python 能做的事
   - 对 web_fetch 返回的数据做进一步处理
   - 当用户要求生成文件/报告时，保存到 `~/.monad/output/` 目录下（代码中可直接使用已注入的变量 `MONAD_OUTPUT_DIR`，它的值就是该目录的绝对路径），系统会自动生成下载链接
   - 示例：`path = os.path.join(MONAD_OUTPUT_DIR, "report.md")`  ← MONAD_OUTPUT_DIR 是变量，不是字符串！
   - 一般的回答直接用 answer 返回即可，只有用户明确要求"生成文件/报告/导出"时才保存文件

2. **shell**: 执行 Shell 命令。你的"口令"🗣️。

3. **web_fetch**: 感知互联网。你的"眼睛"👁️——直接看到网页内容：
   - 只需传 url 即可，系统会自动选择最佳抓取方式（fast→stealth→browser 智能降级）
   - selector：CSS 选择器，精确提取页面元素（可选）
   - **不要手动指定 mode 参数**，默认的 auto 模式已经能处理所有情况

4. **ask_user**: 确实无法独立完成时，向用户求助。你的"对话"💬。

5. **desktop_control**: 操控桌面应用程序。你的"双手操控屏幕"🖥️：
   - 通过截屏 + OCR 识别界面上的文字元素及坐标，再模拟键鼠操作
   - **action 参数必须是一个完整字符串**，不要拆成多个参数。例如：`{"action": "click 搜索"}` ✅，不是 `{"action": "click", "text": "搜索"}` ❌
   - 用法（action 参数）：
     - `activate <应用名>`: **首先使用**——把目标应用切到前台（如 `activate Lark`）。不 activate 就 screenshot 只会看到当前前台窗口。
     - `screenshot`: 截屏并 OCR，返回当前屏幕上所有可见文字元素及其坐标
     - `click <文字>`: 点击屏幕上包含指定文字的元素
     - `double_click <文字>`: 双击匹配的元素
     - `click_xy <x> <y>`: 点击精确坐标（当 OCR 无法匹配时使用）
     - `type <文字>`: 用键盘输入文字
     - `hotkey <key1> <key2>`: 按快捷键（如 `hotkey cmd space`、`hotkey ctrl a`）
     - `find <文字>`: 检查某个文字是否出现在屏幕上
     - `wait <秒>`: 等待界面更新
   - **标准使用流程**：
     1. `shell: open -a "AppName"` 打开应用
     2. `desktop_control: activate AppName` 确保应用在前台
     3. `desktop_control: wait 2` 等待界面加载
     4. `desktop_control: screenshot` 看到界面元素
     5. `desktop_control: click <目标>` / `type <内容>` 操作
     6. `desktop_control: screenshot` 确认结果
   - ⚠️ **重要注意事项**：
     - screenshot 是**全屏截图**，会同时看到前台和后台窗口的文字。必须根据 `[Frontmost app: XXX]` 标签确认你看到的是目标应用，而非其他窗口的内容。
     - **只有 click/type/hotkey 才是真正的交互操作**。仅 screenshot 不代表你做了任何事。任务要求你"点击"或"发消息"时，你必须实际执行 click/type 动作。
     - 每次操作后只做一次 screenshot 确认，不要重复截图。一次操作不成功就换方法，不要重试同样的操作。
     - 不要把屏幕上看到的历史文字（如之前执行的日志）当作当前任务的结果。
     - **搜索场景的 click 陷阱**：在搜索框输入关键词后，OCR 会同时看到搜索框里的输入文字和下方的搜索结果。如果 click 返回了 "Also matched: ..." 替代项，说明有多个匹配。**优先点击搜索结果列表中带上下文的选项**（如 `click 问一问：百合` 而非 `click 百合`），因为搜索框里的文字点了不会跳转。如果 click 后界面没变化，立刻尝试 "Also matched" 中的替代目标。
     - **搜索结果可见时直接点击**：如果 screenshot 后看到搜索结果中已经有目标联系人/项目（如 "百合"、"问一问：百合"），**直接点击该搜索结果进入**，不要先点其他导航/分类标签（如 "消息"）再去找，那样会跳出搜索页面导致目标消失。
     - **同名元素有多个位置**：UI 中同一文字可能出现在多个位置（导航栏、侧边栏、搜索分类等）。当 click 返回 "Also matched" 或 "WARNING: N elements match"，仔细看坐标，用 `click_xy <x> <y>` 精确点击你真正想要的那个。
     - **发消息必须完成全流程**：找到联系人 → 点击进入聊天 → `type <消息内容>` 输入文字 → 发送（Enter 或点击发送按钮）。缺少 `type` 步骤 = 消息没发出去。
     - **聊天可能已经打开**：如果 screenshot 显示联系人名字出现在窗口顶部（y 坐标很小），这是聊天窗口的标题栏——说明**这个聊天已经打开了**。不需要再搜索或点击联系人，直接 `type <消息>` 输入消息然后 `hotkey return` 发送即可。反复点击标题栏上的名字不会有任何效果。
     - **"发送给 XXX" 面板**：在飞书/微信 cmd+k 搜索后，点击联系人名字会弹出一个结果卡片，里面有一个"发送给 XXX"按钮。**必须点击这个按钮**才能进入聊天窗口。进入聊天后再 `type <消息>` 输入并 `hotkey return` 发送。不要在这一步做其他操作。
     - **各应用搜索快捷键不同**：飞书（Lark）用 `hotkey cmd k`；微信（WeChat）用 `hotkey cmd f`。搜索后必须截图确认搜索框已打开并有结果，再输入联系人名字。
     - **搜索后必须等待再截图**：`type <联系人名>` 输入搜索词后，**先 `wait 1`，再截图**确认搜索结果已出现。搜索结果是异步渲染的，不等待直接截图可能看不到结果。
     - **用坐标点击搜索结果**：搜索结果截图出来后，**不要用 `click <联系人名>` 文字匹配**（会匹配到搜索框里的输入文字，而不是下方的结果列表）。**必须看截图里联系人的坐标，用 `click_xy <x> <y>` 精确点击**。联系人名字在结果列表里，y 坐标会明显大于搜索框（搜索框通常 y < 80，联系人结果通常 y > 100）。
     - **点击后必须等待再截图**：点击联系人或搜索结果后，**先 `wait 1`，再截图**确认界面已切换到聊天。不要连续点击同一个元素——如果截图后界面没变，说明点击位置不对，需要分析元素坐标再重试。
     - **发消息完整流程**：搜索 → `wait 1` → 截图确认 → 用 `click_xy` 点击结果列表里的联系人 → `wait 1` → 截图确认聊天已打开 → `type <消息内容>` → `hotkey return` 发送 → 截图确认消息已发出。**缺少 `hotkey return` = 消息没发出去。**

你还有已学会的技能（skills），优先使用已有技能。

## 你的思考流程（每次任务必须遵循）

1. **分析**: 用户想要什么？意图明确吗？
   - 如果 query 本身有歧义、信息不足、需要明确 → **立刻 ask_user**（这是"分析"，不是"求助"）
   - 例如：用户说"帮我分析博客" → 哪个博客？= 必须先问
   - 例如：用户说"帮我分析 yam.gift" → 意图明确 = 直接执行
2. **自检**: 我有已学会的技能可以做这件事吗？
3. **判断**: 需要真实数据还是纯计算？需要互联网吗？
4. **选择工具**: 需要网页 → web_fetch；数据处理 → python_exec；系统操作 → shell
5. **执行**: 获取真实数据
6. **观察**: 结果对吗？数据拿到了吗？
7. **遇到障碍？先搜索！**: 报错/缺库/不熟悉 → web_fetch 搜索解决方案（不是问用户！）
8. **重试**: 根据搜索结果或分析，换一种方法再试
9. **回答**: 基于真实获取的数据，给用户组织一个清晰的回答

## 文件附件

当用户的消息中包含 `[attached: /path/to/file]` 时，表示用户上传了一个文件。
- 该文件已保存在指定路径，你可以直接用 python_exec 读取它
- 如果有已学的文档解析技能（如 parse_document），优先使用
- 如果没有对应技能，用 python_exec 根据文件类型选择合适的方式读取（如 open() 读文本，或安装相关库解析 PDF/DOCX 等）

## ⭐ URL优先原则（最重要）

**当用户给出了具体的 URL 或域名（如"帮我分析 kexue.fm"），你必须先用 web_fetch 直接访问该 URL，而不是去搜索引擎搜索！**
- 用户说"帮我分析 kexue.fm" → 第一步：web_fetch url="https://kexue.fm" ✅
- 用户说"帮我分析 kexue.fm" → 第一步：搜索 bing "kexue.fm 是什么" ❌
- 只有在直接访问失败后，才可以考虑搜索引擎作为补充

## 常见任务的正确处理方式

- **用户给了 URL/域名** → **先 web_fetch 直接访问该URL**，不要先搜索
- **搜索信息/新闻** → web_fetch url="https://www.bing.com/search?q=关键词"
- **查看任何网页** → web_fetch url="网页地址"（auto 模式自动选择最佳方式）
- **复杂数据处理** → 先 web_fetch 获取原始数据，再 python_exec 处理
- **记忆与分类用户状态** → python_exec 写入 `knowledge/user/` 目录
- **文件/系统操作** → python_exec 或 shell
- **用户附带了文件** → 用已学的文档解析技能或 python_exec 读取文件内容，再进行分析
- **用户要求你学习/创建一个新技能** → 按下面的技能创建规范操作

## 主动学习技能（Skill Creation）

当用户要求你"学习一个新技能"时，你**必须按顺序执行以下 action**（每一步都是一个独立的 action，不能跳过）：

**Step 0（最重要）** — 先检查已有技能，复用优先：
仔细阅读上方 "Your Learned Skills" 列表中每个技能的 Goal 和 Triggers。
- 如果某个已有技能**已经覆盖**当前需求 → 直接使用它，不要创建新的
- 如果某个已有技能**功能相近**但不完全匹配（例如 web_to_markdown 已存在，用户要求"学习把微信文章转markdown"）→ **修改已有技能的 executor.py 使其兼容**，不要新建
- 只有**完全没有相关技能**时，才继续 Step 1~4 创建新的

修改已有技能示例：
{"type": "action", "capability": "python_exec", "params": {"code": "# 读取已有技能代码\nwith open(os.path.expanduser('~/.monad/knowledge/skills/已有技能名/executor.py')) as f:\n    print(f.read())"}}
然后修改代码使其兼容新场景，写回同一个文件。

**Step 1** — shell 安装依赖：
{"type": "action", "capability": "shell", "params": {"command": "pip install 库名"}}

**Step 2** — python_exec 创建技能目录和文件：
{"type": "action", "capability": "python_exec", "params": {"code": "import os\nos.makedirs(os.path.expanduser('~/.monad/knowledge/skills/技能名'), exist_ok=True)\n\n# 写 skill.yaml\nyaml_content = '''name: 技能名\ngoal: 目标描述\ninputs:\n- param1\nsteps:\n- 步骤1\ntriggers:\n- 触发条件\n'''\nwith open(os.path.expanduser('~/.monad/knowledge/skills/技能名/skill.yaml'), 'w') as f:\n    f.write(yaml_content)\n\n# 写 executor.py\ncode_content = '''def run(**kwargs):\n    param1 = kwargs.get(\"param1\", \"\")\n    # 实现逻辑\n    return \"结果\"\n'''\nwith open(os.path.expanduser('~/.monad/knowledge/skills/技能名/executor.py'), 'w') as f:\n    f.write(code_content)\n\nprint('技能文件已写入')"}}

**Step 3** — python_exec 测试技能能跑通：
{"type": "action", "capability": "python_exec", "params": {"code": "import sys\nsys.path.insert(0, os.path.expanduser('~/.monad/knowledge/skills/技能名'))\nfrom executor import run\nresult = run(param1='测试值')\nprint(result)"}}

**Step 4** — 全部通过后才能 answer 汇报结果

技能目录结构（必须严格遵循）：
```
~/.monad/knowledge/skills/<skill_name>/
├── skill.yaml      # 元数据
└── executor.py     # Python 实现（必须有 run(**kwargs) 函数）
```

关键规则：
- executor.py 必须有 `def run(**kwargs)` 函数，返回字符串
- triggers 字段帮助你在未来任务中判断何时应该调用这个技能
- [CRITICAL] 你必须实际执行 python_exec 来写入文件！不要只在 thought 或 answer 里描述。**检查文件是否存在不等于创建文件**。你需要用 open() 和 write() 实际写入。
- [CRITICAL] 如果 pip install 超时或失败，先搜索解决方案，不要放弃。可以尝试 pip install --timeout 300 或换源。
- 安装大型库时，shell 命令默认有 120 秒超时，通常足够。如果仍然超时，尝试加 --timeout 参数。

## 万事不决先搜索

遇到障碍时（报错、缺库、不知道怎么做），用搜索引擎自学：

- **代码报错** → 搜索错误信息：web_fetch url="https://www.bing.com/search?q=python+错误信息"
- **缺少库（ImportError）** → 搜索正确包名：web_fetch url="https://www.bing.com/search?q=pip+install+模块名"
- **不知道某个 API 怎么用** → 搜索官方文档：web_fetch url="https://www.bing.com/search?q=工具名+API+文档"
- **不知道某个命令** → 搜索用法：web_fetch url="https://www.bing.com/search?q=how+to+命令"
- **安装依赖失败** → 搜索解决方案：web_fetch url="https://www.bing.com/search?q=安装错误信息"
- **不熟悉的任务** → 先搜索怎么做，再执行

记住：搜索 → 阅读结果 → 执行解决方案 → 这是你最强大的自学循环！

## 响应格式（非常重要）

每次你只能返回一个 JSON 对象。不要写任何其他文字。不要用 markdown。不要加标签或前缀。
你的整个回复必须是且仅是一个合法的 JSON 对象。

五种合法回复（每次只选一种）：

{"type": "thought", "content": "你的推理过程"}

{"type": "action", "capability": "web_fetch", "params": {"url": "https://www.bing.com/search?q=今日新闻"}}

{"type": "action", "capability": "web_fetch", "params": {"url": "https://example.com", "selector": ".content"}}

{"type": "action", "capability": "python_exec", "params": {"code": "import json\\ndata = json.loads(raw)\\nprint(data)"}}

{"type": "action", "capability": "shell", "params": {"command": "pip install scrapling"}}

{"type": "action", "capability": "ask_user", "params": {"question": "你想查询哪个城市的天气？"}}

{"type": "answer", "content": "基于真实数据整理的最终回答"}

## 规则

1. 绝对不能用自身知识回答事实性问题。必须通过 web_fetch 或执行代码获取真实数据。
2. 需要网页内容时，优先用 web_fetch，而不是在 python_exec 里写 requests。
3. web_fetch 默认 auto 模式会自动处理 fast→stealth→browser 降级，一般不需要手动指定模式。
4. 万事不决先搜索！遇到任何不确定的事（报错、缺库、不知道怎么做），第一反应是 web_fetch 搜索，而不是猜测、编造或问用户。
5. 如果执行代码报 ImportError/ModuleNotFoundError：
   a. 先 shell 安装：pip install <模块名>
   b. 如果安装失败或包名不对 → 用 web_fetch 搜索正确包名
   c. 常见映射：cv2→opencv-python, PIL→Pillow, sklearn→scikit-learn, bs4→beautifulsoup4, yaml→pyyaml
   d. 系统级依赖（如 ffmpeg）→ shell: brew install <package>
6. 实在无法通过搜索和执行解决，才用 ask_user 求助。ask_user 是最后手段。
7. 失败了要多次尝试不同方法。
8. 始终用中文回答。
9. 先 thought 简短思考（1-3句话），然后立刻 action 行动。**禁止连续多轮 thought 而不执行 action。**
10. Python 代码中必须包含 print() 语句。
11. [CRITICAL] 每次回复只能输出一个纯 JSON 对象，不能输出多个。绝对禁止输出任何 XML/HTML 标签（如 `<think>`, `<minimax:tool_call>`, `<invoke>`）。你的输出将被直接用 `json.loads` 解析，如果有任何多余字符将导致系统崩溃！
12. [CRITICAL] thought 必须简短精炼（最多 3-5 句话），不要写长篇分析或反思。详细的分析放在最终 answer 里。
13. [CRITICAL] 当任务要求"创建/生成/保存/安装"时，必须通过 action（python_exec/shell）实际执行。绝对不能只在 answer 里描述"我已完成"而没有实际执行任何写入操作。answer 是最终汇报，不是执行动作。"""

MAX_TURNS = 30


class Reasoner:
    """Multi-turn ReAct reasoning engine.

    Implements the think → act → observe loop until the task is solved.
    Every step is printed for the user to follow.
    """

    def __init__(self, vault: KnowledgeVault = None):
        self.vault = vault or KnowledgeVault()

    def solve(self, user_input: str, execute_fn=None) -> dict:
        """Solve a user's request through multi-turn reasoning.

        Args:
            user_input: The user's natural language request
            execute_fn: Function to execute capabilities (capability_name, **params) -> str

        Returns:
            dict with 'answer', 'thoughts', 'actions', 'success'
        """
        Output.phase("Phase 1: 加载知识上下文")
        context = self._build_context(user_input)

        history = []
        thoughts = []
        actions = []
        consecutive_thoughts = 0
        consecutive_ask_user = 0
        _recent_action_sigs = []  # tracks action signatures for loop detection
        _click_target_counts = {}  # tracks click target repetitions across turns
        _active_app = None  # tracks the last successfully activated app

        for turn in range(MAX_TURNS):
            Output.phase(f"Reasoning Turn {turn + 1}/{MAX_TURNS}")

            # Build prompt
            prompt = self._build_prompt(context, history)

            # Call LLM
            Output.system("正在调用 LLM 进行推理...")
            try:
                raw_response = llm_call(prompt, system=REASONER_SYSTEM, temperature=0.2)
            except Exception as e:
                Output.error(f"LLM 调用失败: {str(e)}")
                return {
                    "answer": f"LLM 调用失败: {str(e)}",
                    "thoughts": thoughts,
                    "actions": actions,
                    "success": False,
                }

            # Parse response
            parsed = self._parse_response(raw_response)
            Output.system(f"LLM 返回类型: {parsed['type']}")

            # ── Handle: THOUGHT ──────────────────────────────
            if parsed["type"] == "thought":
                content = parsed["content"]
                consecutive_thoughts += 1
                thoughts.append(content)

                # Store a capped version in history to prevent context bloat
                capped = content[:_THOUGHT_HISTORY_CAP]
                if len(content) > _THOUGHT_HISTORY_CAP:
                    capped += "...(truncated)"
                history.append({"role": "assistant", "content":
                    json.dumps({"type": "thought", "content": capped}, ensure_ascii=False)
                })

                Output.thinking(content)

                # --- Loop detection ---
                is_loop = (
                    len(thoughts) >= 2
                    and self._thought_similarity(thoughts[-1], thoughts[-2]) > _SIMILARITY_THRESHOLD
                )

                if is_loop:
                    Output.warn(f"检测到重复思考，强制要求执行动作")
                    history.append({"role": "user", "content":
                        "STOP. You are repeating the same thought. "
                        "Do NOT think again. You MUST output an action JSON now. "
                        "Pick one: web_fetch, python_exec, shell, or ask_user. "
                        "If you have enough info, output an answer JSON."
                    })
                elif consecutive_thoughts >= _THOUGHT_HARD_LIMIT:
                    Output.warn(f"连续思考 {consecutive_thoughts} 轮，强制要求动作")
                    history.append({"role": "user", "content":
                        "You have been thinking too long without acting. "
                        "You MUST take an action NOW or give your final answer. "
                        "Output a JSON with type='action' or type='answer'. "
                        "Do NOT output another thought."
                    })
                elif consecutive_thoughts >= _THOUGHT_SOFT_LIMIT:
                    history.append({"role": "user", "content":
                        "You've thought enough. Now take action. "
                        "What specific action (web_fetch/python_exec/shell) will you execute?"
                    })
                else:
                    history.append({"role": "user", "content":
                        "Good. Now take action based on your analysis. What will you do?"
                    })

                continue

            # Reset consecutive thought counter on any non-thought response
            consecutive_thoughts = 0

            # ── Handle: ACTION ───────────────────────────────
            if parsed["type"] == "action":
                capability = parsed.get("capability", "")
                params = parsed.get("params", {})

                # Guard: prevent ask_user loop
                if capability == "ask_user":
                    consecutive_ask_user += 1
                    if consecutive_ask_user > _ASK_USER_LIMIT:
                        Output.warn(f"连续 ask_user {consecutive_ask_user} 次，强制跳过并继续执行")
                        history.append({"role": "assistant", "content": raw_response})
                        history.append({"role": "user", "content":
                            "User did not respond. Do NOT ask again. "
                            "Proceed with reasonable defaults or use the information you already have. "
                            "If images are needed, skip them or generate a text-only version."
                        })
                        continue
                else:
                    consecutive_ask_user = 0

                actions.append({"capability": capability, "params": params})

                # --- Action loop detection ---
                action_sig = f"{capability}:{json.dumps(params, sort_keys=True, ensure_ascii=False)}"
                _recent_action_sigs.append(action_sig)
                if len(_recent_action_sigs) >= 3 and len(set(_recent_action_sigs[-3:])) == 1:
                    stuck_action = params.get("action", "") or params.get("command", "")
                    is_app_launch_loop = (
                        "open -a" in stuck_action or "activate" in stuck_action.lower()
                        or capability == "shell" and "open -a" in params.get("command", "")
                    )

                    if is_app_launch_loop and execute_fn:
                        Output.warn(f"检测到重复动作 ({capability})，自动执行 screenshot 推进流程")
                        history.append({"role": "assistant", "content": raw_response})
                        auto_result = execute_fn("desktop_control", action="screenshot")
                        Output.action("desktop_control", "[自动] 截屏以推进流程")
                        Output.observation(auto_result[:500] if len(auto_result) > 500 else auto_result)
                        hint = self._action_hint("desktop_control", {"action": "screenshot"}, auto_result)
                        if hint:
                            auto_result += "\n" + hint
                        history.append({"role": "user", "content":
                            f"[SYSTEM] You were stuck repeating '{stuck_action}'. The app IS already open. "
                            f"I auto-executed screenshot for you. Here are the current screen elements:\n\n"
                            f"Observation from desktop_control:\n{auto_result}\n\n"
                            f"Now use click <text> to click a UI element, or type <text> to enter text. "
                            f"Do NOT run open/activate again."
                        })
                        _recent_action_sigs.clear()
                    else:
                        Output.warn(f"检测到重复动作 ({capability})，强制切换策略")
                        history.append({"role": "assistant", "content": raw_response})
                        history.append({"role": "user", "content":
                            f"[SYSTEM] STOP. You executed '{capability}' with the same parameters "
                            f"3 times in a row. This is not working. "
                            f"You MUST try a COMPLETELY DIFFERENT approach now."
                        })
                    continue

                # --- Click-target loop detection (across non-consecutive turns) ---
                if capability == "desktop_control":
                    action_str = params.get("action", "")
                    if action_str.startswith("click "):
                        click_target = action_str[6:].strip()
                        _click_target_counts[click_target] = _click_target_counts.get(click_target, 0) + 1
                        if _click_target_counts[click_target] >= 3:
                            Output.warn(f'检测到重复点击 "{click_target}" {_click_target_counts[click_target]} 次，强制换策略')
                            history.append({"role": "assistant", "content": raw_response})
                            history.append({"role": "user", "content":
                                f'[SYSTEM] STOP. You have clicked "{click_target}" {_click_target_counts[click_target]} times '
                                f'but the UI has not changed. This means you are clicking the WRONG element '
                                f'(likely the search input text, not a search result). '
                                f'Try one of these:\n'
                                f'1. Click a more specific element with context (e.g. click the full search result text, not the short keyword)\n'
                                f'2. Use click_xy with coordinates of the actual search result below the input\n'
                                f'3. Press Enter/Return to confirm the search, then screenshot to see results\n'
                                f'4. Use hotkey to navigate (e.g. hotkey down, then hotkey enter)'
                            })
                            continue

                # --- Intercept redundant 'open -a' when app already active ---
                import re as _re_loop
                if capability == "shell" and _active_app and execute_fn:
                    shell_cmd = params.get("command", "")
                    m_open = _re_loop.search(r'open\s+-a\s+["\']?(\w+)', shell_cmd)
                    if m_open:
                        from monad.tools.desktop_control import _is_same_app
                        requested_app = m_open.group(1)
                        if _is_same_app(requested_app, _active_app):
                            Output.warn(f'"{_active_app}" 已在前台，跳过重复 open，自动截屏')
                            history.append({"role": "assistant", "content": raw_response})
                            auto_result = execute_fn("desktop_control", action="screenshot")
                            Output.action("desktop_control", "[自动] 截屏替代重复 open")
                            Output.observation(auto_result[:500] if len(auto_result) > 500 else auto_result)
                            hint = self._action_hint("desktop_control", {"action": "screenshot"}, auto_result)
                            if hint:
                                auto_result += "\n" + hint
                            history.append({"role": "user", "content":
                                f'[SYSTEM] "{_active_app}" is ALREADY open and in the foreground. '
                                f'Do NOT run "open -a" or "activate" again. '
                                f'I auto-executed screenshot for you:\n\n'
                                f'Observation from desktop_control:\n{auto_result}\n\n'
                                f'Now interact with the UI: use click <text>, type <text>, '
                                f'hotkey cmd k (to search contacts), etc.'
                            })
                            _recent_action_sigs.clear()
                            continue

                history.append({"role": "assistant", "content": raw_response})

                # Show what action is being taken
                if capability == "python_exec":
                    code = params.get("code", "")
                    Output.action("python_exec", "执行 Python 代码")
                    Output.code(code)
                elif capability == "shell":
                    cmd = params.get("command", "")
                    Output.action("shell", f"执行命令: {cmd}")
                elif capability == "web_fetch":
                    url = params.get("url", "")
                    fetch_mode = params.get("mode", "auto")
                    sel = params.get("selector", "")
                    desc = f"感知网页: {url} (模式: {fetch_mode})"
                    if sel:
                        desc += f" [选择器: {sel}]"
                    Output.action("web_fetch", desc)
                elif capability == "ask_user":
                    question = params.get("question", "")
                    Output.action("ask_user", f"需要询问用户: {question}")
                else:
                    Output.action(capability, str(params)[:200])

                # Execute
                if execute_fn:
                    result = execute_fn(capability, **params)
                else:
                    result = f"Error: No executor available for '{capability}'"

                # Show observation
                Output.observation(result[:500] if len(result) > 500 else result)

                # Track active app from successful activate or open -a
                if capability == "desktop_control":
                    act_str = params.get("action", "")
                    if act_str.startswith("activate") and ("verified" in result or "foreground" in result):
                        app_name = act_str.split(None, 1)[1].strip() if " " in act_str else ""
                        if app_name:
                            _active_app = app_name
                elif capability == "shell" and not _active_app:
                    shell_cmd = params.get("command", "")
                    import re as _re_track
                    m_track = _re_track.search(r'open\s+-a\s+["\']?(\w+)', shell_cmd)
                    if m_track and "error" not in result.lower() and "unable" not in result.lower():
                        _active_app = m_track.group(1)

                # Post-action verification for skill/file creation
                verification = self._verify_action(capability, params, result)
                if verification:
                    result = result + "\n" + verification
                    Output.observation(f"[验证] {verification}")

                # Smart hint: guide LLM to next step after opening an app
                hint = self._action_hint(capability, params, result)
                if hint:
                    result = result + "\n" + hint

                # Feed back to LLM
                observation = f"Observation from {capability}:\n{result}"
                history.append({"role": "user", "content": observation})

            # ── Handle: ANSWER ───────────────────────────────
            elif parsed["type"] == "answer":
                # Guard: reject hollow answers that claim creation
                # without actual write actions
                if self._is_hollow_answer(user_input, actions):
                    Output.warn("检测到空洞回答：声称完成操作但未实际执行，强制要求执行")
                    history.append({"role": "assistant", "content": raw_response})
                    # Build a targeted rejection message based on what's missing
                    dc_actions_done = [
                        a.get("params", {}).get("action", "").strip()
                        for a in actions
                        if a.get("capability") == "desktop_control"
                    ]
                    has_type = any(a.lower().startswith("type ") for a in dc_actions_done)
                    has_send = any(
                        a.lower() in ("hotkey return", "hotkey enter", "hotkey cmd return")
                        for a in dc_actions_done
                    )
                    has_click = any(
                        a.lower().startswith(("click", "click_xy"))
                        for a in dc_actions_done
                    )
                    # Only count 'type' as "message typed" if the typed content
                    # matches the message to send (not just a contact search term).
                    import re as _re2
                    msg_match = _re2.search(r'[""「\'"]([^"""\'」]{1,50})[""」\'"]', user_input)
                    expected_msg = msg_match.group(1) if msg_match else None
                    has_msg_typed = any(
                        a.lower().startswith("type ")
                        and (expected_msg is None or expected_msg.lower() in a.lower())
                        for a in dc_actions_done
                    )
                    if has_click and not has_msg_typed:
                        msg_to_type = expected_msg or "<message content>"
                        reject_msg = (
                            "[SYSTEM] You clicked a contact but you have NOT typed the message yet. "
                            "The chat window should now be open. Your ONLY next steps are:\n"
                            f"1. desktop_control screenshot — confirm the chat is open\n"
                            f"2. desktop_control type {msg_to_type} — type the message in the chat input\n"
                            "3. desktop_control hotkey return — press Enter to SEND\n"
                            "4. desktop_control screenshot — confirm message was sent\n"
                            "DO NOT answer. Execute these steps NOW."
                        )
                    elif has_msg_typed and not has_send:
                        reject_msg = (
                            "[SYSTEM] You typed the message but did NOT press Enter to send it. "
                            "Execute NOW: desktop_control hotkey return — then screenshot to confirm."
                        )
                    else:
                        reject_msg = (
                            "[SYSTEM] Your answer claims you completed the task, but action history "
                            "shows you did NOT actually perform the required operations. "
                            "For desktop messaging: you MUST (1) screenshot to see the current UI, "
                            "(2) type <message> in the chat input, (3) hotkey return to send. "
                            "DO NOT answer again — take action NOW."
                        )
                    history.append({"role": "user", "content": reject_msg})
                    continue

                Output.phase("任务完成")
                return {
                    "answer": parsed["content"],
                    "thoughts": thoughts,
                    "actions": actions,
                    "success": True,
                }

            # ── Handle: PARSE ERROR ──────────────────────────
            elif parsed["type"] == "error":
                Output.warn(f"LLM 返回格式异常，正在重试... (原始: {raw_response[:150]})")
                # Store only a short snippet to avoid polluting history with garbage
                history.append({"role": "assistant", "content": raw_response[:300]})
                history.append({
                    "role": "user",
                    "content": (
                        "Your response was not valid JSON. "
                        "You MUST respond with ONLY a JSON object. "
                        "No markdown, no extra text, no code fences, no XML tags. "
                        "Example: {\"type\": \"action\", \"capability\": \"web_fetch\", "
                        "\"params\": {\"url\": \"https://example.com\"}}"
                    ),
                })

        # Exhausted turns
        Output.error(f"推理轮次已用尽 ({MAX_TURNS} 轮)")
        return {
            "answer": "推理轮次已用尽，无法完成任务。请尝试更简单的描述。",
            "thoughts": thoughts,
            "actions": actions,
            "success": False,
        }

    def _build_context(self, user_input: str) -> str:
        """Build context from MONAD's knowledge base."""
        sections = []

        knowledge = self.vault.load_all_context(query=user_input)

        # Axioms
        if knowledge.get("axioms"):
            sections.append(f"## Your Principles\n{knowledge['axioms']}")
            Output.system(f"已加载系统公理 ({len(knowledge['axioms'])} 字符)")

        # Skills
        if knowledge.get("skills"):
            sections.append(f"## Your Learned Skills (USE THESE FIRST)\n{knowledge['skills']}")
            Output.skill_check(f"已学会的技能: {knowledge['skills'][:200]}")
        else:
            Output.skill_check("尚无已学技能，将在工作中学习")

        # Environment
        if knowledge.get("environment"):
            sections.append(f"## Environment Knowledge\n{knowledge['environment']}")
            Output.system(f"已加载环境知识 ({len(knowledge['environment'])} 字符)")

        # User Context (Facts, Mood, Goals)
        if knowledge.get("user_context"):
            sections.append(f"## Known User Context (Facts, Mood, Goals)\n{knowledge['user_context']}")
            Output.system(f"已加载用户记忆 ({len(knowledge['user_context'])} 字符)")

        # Protocols
        if knowledge.get("protocols"):
            sections.append(f"## Behavioral Protocols\n{knowledge['protocols']}")

        # Experiences
        if knowledge.get("experiences"):
            sections.append(f"## Past Experiences\n{knowledge['experiences']}")
            Output.system(f"已加载过往经验总结 ({len(knowledge['experiences'])} 字符)")

        sections.append(f"## User Request\n{user_input}")

        return "\n\n".join(sections)

    @staticmethod
    def _action_hint(capability: str, params: dict, result: str) -> str:
        """Generate contextual hints to guide the LLM to the next logical step."""
        import re as _re
        if capability == "shell":
            cmd = params.get("command", "")
            m = _re.search(r'open\s+-a\s+["\']?(\w+)', cmd)
            if m and "error" not in result.lower() and "unable" not in result.lower():
                app_name = m.group(1)
                return (
                    f"[Hint: '{app_name}' has been opened. Your next steps should be: "
                    f'1) desktop_control activate {app_name} — to bring it to foreground, '
                    f'2) desktop_control wait 2 — let UI load, '
                    f'3) desktop_control screenshot — to see the UI elements. '
                    f'Do NOT run open -a again.]'
                )
        if capability == "desktop_control":
            action = params.get("action", "")
            if action.startswith("activate") and "foreground" in result.lower():
                if "Auto-screenshot" in result:
                    hint = (
                        "[Hint: App is in foreground and UI elements are shown above. "
                        "Use click/type/hotkey to interact NOW. Do NOT run open/activate/screenshot again."
                    )
                    if "Feishu" in result or "Lark" in result:
                        hint += " To search for a contact in Feishu/Lark: hotkey cmd k"
                    elif "WeChat" in result or "微信" in result:
                        hint += " To search for a contact in WeChat: hotkey cmd f (NOT cmd+k)"
                    hint += "]"
                    return hint
                return (
                    "[Hint: App is now in foreground. Next: desktop_control screenshot "
                    "to see UI elements, then click/type to interact.]"
                )
            if action == "screenshot" and "UI elements" in result:
                # Detect "发送给 XXX" pattern — this is a Feishu/WeChat search result card.
                # The correct action is to click it to open the chat, then type the message.
                send_to_match = _re.search(r'["\']发送给\s*(\S+?)["\']', result)
                if send_to_match:
                    contact = send_to_match.group(1)
                    return (
                        f'[Hint: Search result shows "发送给{contact}" button. '
                        f'Click it to open the chat: click 发送给{contact} '
                        f'— then immediately type your message and press hotkey return to send.]'
                    )
                hint = (
                    "[Hint: You can now see the screen. Use click <text> to click a button, "
                    "type <text> to enter text, or hotkey to press keys. "
                    "Do NOT take another screenshot until you've performed an action."
                )
                if "搜索" not in result and ("Feishu" in result or "Lark" in result):
                    hint += (
                        " To search for a contact in Feishu/Lark: use 'hotkey cmd k'."
                    )
                elif "搜索" not in result and ("WeChat" in result or "微信" in result):
                    hint += (
                        " To search for a contact in WeChat: use 'hotkey cmd f' "
                        "(NOT cmd+k — WeChat uses cmd+f for search)."
                    )
                hint += "]"
                return hint
            if action.startswith("type") and "Typed:" in result:
                # After typing into a search box, LLM must wait briefly then screenshot to see results
                typed_text = action[4:].strip() if len(action) > 4 else ""
                return (
                    f'[Hint: Typed "{typed_text}". Wait for search results, then screenshot: '
                    f'1) desktop_control wait 1  '
                    f'2) desktop_control screenshot — find the contact in the RESULT LIST (larger y value). '
                    f'IMPORTANT: Do NOT use "click {typed_text}" — that may hit the search INPUT box. '
                    f'Instead use click_xy <x> <y> with the exact coordinates of the contact in the result list.]'
                )
            if action.startswith("click") and "Also matched:" in result:
                return (
                    "[Hint: Multiple elements matched your click target. If the clicked element "
                    "was a search input (not a result), the UI won't change. Check the 'Also matched' "
                    "alternatives and try clicking one with more context text (e.g. a search result item).]"
                )
            if action.startswith("click") and "发送给" in result:
                send_to_match = _re.search(r'["\']发送给\s*(\S+?)["\']', result)
                if send_to_match:
                    contact = send_to_match.group(1)
                    return (
                        f'[Hint: Click succeeded and "发送给{contact}" is visible. '
                        f'This is the search result card. Click it: click 发送给{contact} '
                        f'— then type your message and hotkey return to send.]'
                    )
            if action.startswith("click") and "WARNING: Only one" in result and "SEARCH INPUT" in result:
                # Clicked what is likely the search input text, not the result below.
                # Instruct LLM to wait and screenshot to find the result list.
                return (
                    "[Hint: The click may have landed on the SEARCH INPUT field (where you typed), "
                    "not the contact in the RESULT LIST below. "
                    "Do: desktop_control wait 1 → desktop_control screenshot. "
                    "In the screenshot, look for the contact name at a LOWER position (larger y). "
                    "If you see it, use click_xy <x> <y> with those exact coordinates to click it.]"
                )
            if action.startswith("click") and "Clicked" in result:
                # After clicking a contact/search result, the UI needs time to load the chat.
                # Always wait and then screenshot to confirm the state changed.
                return (
                    "[Hint: Click executed. Now wait for the UI to respond: "
                    "desktop_control wait 1 — then desktop_control screenshot "
                    "to confirm whether the chat/page opened. "
                    "Do NOT click again without first seeing the updated screen.]"
                )
        return ""

    @staticmethod
    def _verify_action(capability: str, params: dict, result: str) -> str:
        """Verify file-creation actions actually produced the expected artifacts."""
        if capability not in ("python_exec", "shell"):
            return ""

        code = params.get("code", "") + params.get("command", "")

        skills_dir = os.path.expanduser("~/.monad/knowledge/skills/")
        if skills_dir not in code and "/skills/" not in code:
            return ""

        match = re.search(r'skills/([a-zA-Z0-9_-]+)', code)
        if not match:
            return ""
        skill_name = match.group(1)
        skill_path = os.path.join(skills_dir, skill_name)
        yaml_ok = os.path.isfile(os.path.join(skill_path, "skill.yaml"))
        py_ok = os.path.isfile(os.path.join(skill_path, "executor.py"))
        parts = []
        if yaml_ok and py_ok:
            parts.append(f"✅ Verified: skill '{skill_name}' — skill.yaml and executor.py exist")
        else:
            if not yaml_ok:
                parts.append(f"⚠️ skill.yaml NOT found at {skill_path}/skill.yaml")
            if not py_ok:
                parts.append(f"⚠️ executor.py NOT found at {skill_path}/executor.py")
        return " | ".join(parts)

    @staticmethod
    def _is_hollow_answer(user_input: str, actions: list) -> bool:
        """Detect answers that claim creation/action without actual execution.

        Returns True when the user's request implies creating/saving something
        but the action history contains no python_exec or shell write commands,
        OR when the task implies desktop GUI interaction but no click/type/hotkey
        actions were actually performed.
        """
        task_lower = user_input.lower()

        # --- Check 1: Creation tasks need write actions ---
        creation_keywords = ["创建", "生成", "保存", "安装", "学习", "制作",
                             "写入", "install", "create", "save", "build"]
        if any(kw in task_lower for kw in creation_keywords):
            write_indicators = ["open(", "write(", "makedirs", "mkdir",
                                "pip install", "save_", "> ", ">>",
                                "with open", "write_text"]
            for action in actions:
                cap = action.get("capability", "")
                if cap not in ("python_exec", "shell"):
                    continue
                code = action.get("params", {}).get("code", "")
                cmd = action.get("params", {}).get("command", "")
                payload = code + cmd
                if any(w in payload for w in write_indicators):
                    break
            else:
                return True

        # --- Check 2: Desktop interaction tasks need click/type/hotkey ---
        desktop_keywords = ["打开", "点击", "发消息", "发送", "输入", "操作",
                            "给.*发", "click", "type", "send", "open.*app"]
        import re
        if any(re.search(kw, task_lower) for kw in desktop_keywords):
            interaction_actions = {"click", "double_click", "click_xy", "type", "hotkey"}
            for action in actions:
                if action.get("capability") != "desktop_control":
                    continue
                act_str = action.get("params", {}).get("action", "")
                cmd = act_str.strip().split(None, 1)[0].lower() if act_str.strip() else ""
                if cmd in interaction_actions:
                    break
            else:
                return True

        # --- Check 3: Messaging tasks require type + hotkey return (or click send button) ---
        # A lone 'type' could be search input — only count it if followed by
        # 'hotkey return' / 'hotkey enter' / click on a send button.
        messaging_keywords = ["发消息", "发信息", "发个消息", "发送消息",
                              "给.*发.*消息", "给.*说", "告诉.*", "问.*",
                              "send.*message", "send.*msg"]
        if any(re.search(kw, task_lower) for kw in messaging_keywords):
            dc_actions = [
                a.get("params", {}).get("action", "").strip()
                for a in actions
                if a.get("capability") == "desktop_control"
            ]
            # Check that we see: type <something> AND (hotkey return/enter OR click send)
            has_type = any(a.lower().startswith("type ") for a in dc_actions)
            has_send = any(
                a.lower() in ("hotkey return", "hotkey enter", "hotkey cmd return")
                or (a.lower().startswith("click") and any(
                    kw in a for kw in ("发送", "Send", "send", "发 ")
                ))
                for a in dc_actions
            )
            if not (has_type and has_send):
                return True

        return False

    @staticmethod
    def _thought_similarity(a: str, b: str) -> float:
        """Jaccard similarity between two thought strings (word-level)."""
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / len(words_a | words_b)

    def _build_prompt(self, context: str, history: list) -> str:
        """Build the full prompt for the LLM.

        Trims old history to stay within a reasonable context budget.
        """
        parts = [context]

        trimmed = history[-_HISTORY_CAP:] if len(history) > _HISTORY_CAP else history

        if trimmed:
            if len(trimmed) < len(history):
                parts.append(f"\n## Reasoning History (latest {len(trimmed)} of {len(history)} entries)")
            else:
                parts.append("\n## Reasoning History")
            for msg in trimmed:
                role = "You" if msg["role"] == "assistant" else "System"
                parts.append(f"\n[{role}]: {msg['content']}")

        return "\n".join(parts)

    def _normalize_parsed(self, parsed: dict) -> dict | None:
        """Normalize alternative JSON formats into the standard format."""
        if "type" in parsed:
            ptype = parsed["type"]
            # LLM sometimes returns {"type": "ask_user", "content": "..."}
            # instead of the correct action format — fix it here
            if ptype == "ask_user":
                question = parsed.get("content", "") or parsed.get("question", "")
                return {
                    "type": "action",
                    "capability": "ask_user",
                    "params": {"question": question},
                }
            return parsed
        # Handle {"action": "ask_user", "params": {...}} format
        if "action" in parsed:
            return {
                "type": "action",
                "capability": parsed["action"],
                "params": parsed.get("params", {}),
            }
        # Handle {"capability": "shell", "params": {...}} format
        if "capability" in parsed:
            return {
                "type": "action",
                "capability": parsed["capability"],
                "params": parsed.get("params", {}),
            }
        # Handle {"answer": "..."} format
        if "answer" in parsed:
            return {"type": "answer", "content": parsed["answer"]}
        # Handle {"thought": "..."} format
        if "thought" in parsed:
            return {"type": "thought", "content": parsed["thought"]}
        return None

    def _parse_response(self, raw: str) -> dict:
        """Parse LLM response into structured format.

        Handles various edge cases:
        - Pure JSON
        - JSON wrapped in markdown code blocks
        - JSON mixed with text labels (e.g. '思考: {...}')
        - Multiple JSON objects (takes the first valid one)
        - Truncated JSON (attempts to fix)
        - <think>...</think> XML blocks (stripped)
        - Alternative format: {"action": ..., "params": ...}
        """
        cleaned = raw.strip()

        # Strip <think>...</think> blocks (Minimax model leakage)
        cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL).strip()
        # Also strip unclosed <think> blocks (truncated responses)
        cleaned = re.sub(r'<think>.*$', '', cleaned, flags=re.DOTALL).strip()
        # Strip any remaining XML-like tags from Minimax
        cleaned = re.sub(r'</?(?:minimax:tool_call|invoke|parameter)[^>]*>', '', cleaned).strip()

        # Remove markdown code blocks
        if "```" in cleaned:
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        # Strategy 1: Direct parse
        try:
            parsed = json.loads(cleaned)
            normalized = self._normalize_parsed(parsed)
            if normalized:
                return normalized
        except json.JSONDecodeError:
            pass

        # Strategy 2: Find JSON object in mixed text
        # This handles cases like '思考: {"type": "thought", ...}'
        brace_depth = 0
        json_start = -1
        for i, ch in enumerate(cleaned):
            if ch == '{':
                if brace_depth == 0:
                    json_start = i
                brace_depth += 1
            elif ch == '}':
                brace_depth -= 1
                if brace_depth == 0 and json_start >= 0:
                    candidate = cleaned[json_start:i + 1]
                    try:
                        parsed = json.loads(candidate)
                        normalized = self._normalize_parsed(parsed)
                        if normalized:
                            return normalized
                    except json.JSONDecodeError:
                        pass
                    json_start = -1

        # Strategy 3: Find partial/truncated JSON and try to fix
        start = cleaned.find("{")
        if start >= 0:
            fragment = cleaned[start:]
            # Try to detect the type from the fragment
            if '"type"' in fragment:
                # Try adding missing closing braces
                for fix in ['}", "}"}', '"}', '}', '"]}', '"}}']:
                    try:
                        parsed = json.loads(fragment + fix)
                        if "type" in parsed:
                            Output.warn(f"JSON 被截断，已自动修复")
                            return parsed
                    except json.JSONDecodeError:
                        continue

        # Strategy 4: Handle [TOOL_CALL] format (Minimax model leakage)
        # e.g. [TOOL_CALL] {tool => "ask_user", args => { --question "..." }}
        tool_call_match = re.search(r'\[TOOL_CALL\].*?tool\s*=>\s*"(\w+)"', cleaned)
        if tool_call_match:
            tool_name = tool_call_match.group(1)
            # Extract question/content from args if present
            arg_match = re.search(r'--question\s+"([^"]*)', cleaned)
            arg_val = arg_match.group(1) if arg_match else ""
            if tool_name == "ask_user":
                return {"type": "action", "capability": "ask_user",
                        "params": {"question": arg_val}}
            return {"type": "action", "capability": tool_name, "params": {}}

        # Strategy 5: Extract thought from plain text response
        # If the model outputs plain text, treat it as a thought
        if len(cleaned) > 10 and '{' not in cleaned:
            return {"type": "thought", "content": cleaned[:500]}

        return {"type": "error", "content": f"JSON 解析失败: {raw[:200]}"}
