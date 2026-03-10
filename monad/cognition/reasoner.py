"""
MONAD Cognition: Reasoner
Multi-turn ReAct reasoning engine.

MONAD thinks like a rational person:
  Analyze problem → Check own capabilities → Learn if needed → Execute → Reflect

This is the brain of MONAD. Every step is printed so the user can see the process.
"""

import json
from monad.core.llm import llm_call
from monad.knowledge.vault import KnowledgeVault
from monad.interface.output import Output


REASONER_SYSTEM = """You are MONAD, a rational autonomous agent.

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

## 你的基础能力（4个"本能"）

1. **python_exec**: 执行 Python 代码。你的"手"🤲——通过它你可以：
   - 处理数据、计算、分析
   - 读写文件
   - 安装缺失的库（subprocess: pip install）
   - 做任何 Python 能做的事
   - 对 web_fetch 返回的数据做进一步处理

2. **shell**: 执行 Shell 命令。你的"口令"🗣️。

3. **web_fetch**: 感知互联网。你的"眼睛"👁️——直接看到网页内容：
   - mode="auto"（默认）：智能自动降级 fast→stealth→browser，自动选择最佳方式
   - mode="fast"：快速 HTTP 请求，适合大多数网页
   - mode="stealth"：隐身浏览器，可绕过 Cloudflare 等反爬
   - mode="browser"：完整 Chromium 浏览器，JS 渲染，适合 SPA/动态页面
   - selector：CSS 选择器，精确提取页面元素（可选）
   - 这是获取互联网信息的首选方式！自动处理各种网页，无需手动选模式

4. **ask_user**: 确实无法独立完成时，向用户求助。你的"对话"💬。

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

## 常见任务的正确处理方式

- **搜索信息/新闻** → web_fetch url="https://www.bing.com/search?q=关键词"
- **查看任何网页** → web_fetch url="网页地址"（auto 模式自动选择最佳方式）
- **精确提取网页元素** → web_fetch selector="CSS选择器"
- **查天气** → web_fetch 抓取天气网站，或 python_exec 调用天气 API
- **复杂数据处理** → 先 web_fetch 获取原始数据，再 python_exec 处理
- **记忆与分类用户状态** → python_exec 写入 `knowledge/user/` 目录
- **文件/系统操作** → python_exec 或 shell

## ⭐ 万事不决先搜索（核心机制）

以下场景，你的第一反应必须是 web_fetch 搜索，而不是猜测或问用户：

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
9. 先 thought 思考，再 action 行动。
10. Python 代码中必须包含 print() 语句。
11. [CRITICAL] 每次回复只能输出一个纯 JSON 对象，不能输出多个。绝对禁止输出任何 XML/HTML 标签（如 `<think>`, `<minimax:tool_call>`, `<invoke>`）。你的输出将被直接用 `json.loads` 解析，如果有任何多余字符将导致系统崩溃！"""

MAX_TURNS = 15


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
                thoughts.append(content)
                history.append({"role": "assistant", "content": raw_response})
                history.append({"role": "user", "content": "Continue. What will you do next?"})

                Output.thinking(content)

            # ── Handle: ACTION ───────────────────────────────
            elif parsed["type"] == "action":
                capability = parsed.get("capability", "")
                params = parsed.get("params", {})
                actions.append({"capability": capability, "params": params})
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
                    fetch_mode = params.get("mode", "fast")
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

                # Feed back to LLM
                observation = f"Observation from {capability}:\n{result}"
                history.append({"role": "user", "content": observation})

            # ── Handle: ANSWER ───────────────────────────────
            elif parsed["type"] == "answer":
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
                history.append({"role": "assistant", "content": raw_response})
                history.append({
                    "role": "user",
                    "content": (
                        "Your response was not valid JSON. "
                        "Please respond with ONLY a JSON object. "
                        "No markdown, no extra text, no code fences. Just pure JSON."
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

        knowledge = self.vault.load_all_context()

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

    def _build_prompt(self, context: str, history: list) -> str:
        """Build the full prompt for the LLM."""
        parts = [context]

        if history:
            parts.append("\n## Reasoning History")
            for msg in history:
                role = "You" if msg["role"] == "assistant" else "System"
                parts.append(f"\n[{role}]: {msg['content']}")

        return "\n".join(parts)

    def _normalize_parsed(self, parsed: dict) -> dict | None:
        """Normalize alternative JSON formats into the standard format."""
        if "type" in parsed:
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
        import re
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

        # Strategy 4: Extract thought from plain text response
        # If the model outputs plain text, treat it as a thought
        if len(cleaned) > 10 and '{' not in cleaned:
            return {"type": "thought", "content": cleaned[:500]}

        return {"type": "error", "content": f"JSON 解析失败: {raw[:200]}"}
