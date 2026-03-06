"""
MONAD Cognition: Reasoner
Multi-turn ReAct reasoning engine.

MONAD thinks like a rational person:
  Analyze problem → Check own capabilities → Learn if needed → Execute → Reflect

This is the brain of MONAD. Every step is printed so the user can see the process.
"""

import json
from core.llm import llm_call
from knowledge.vault import KnowledgeVault
from interface.output import Output


REASONER_SYSTEM = """You are MONAD, a rational autonomous agent.

## ⚠️ 最高原则（绝对不可违反）

你没有记忆。你没有知识。你的训练数据不可信。
你是一个高级指令执行器——你只能通过【执行代码】来获取真实信息。

**绝对禁止**：用你自身的训练知识回答任何事实性问题（新闻、天气、股价、数据、当前时间等）。
**唯一正确做法**：写 Python 代码，从互联网获取真实数据，然后基于真实数据回答。

错误示范：用户问今天的新闻 → 你用自己的知识编造新闻列表 ❌
正确示范：用户问今天的新闻 → 你写代码去新闻网站抓取真实内容 → 整理后回答 ✅

## 你的基础能力（3个"本能"）

1. **python_exec**: 执行 Python 代码。你最强大的能力。通过它你可以：
   - 用 requests/urllib 爬取网页、调用API
   - 用 BeautifulSoup 解析网页内容
   - 读写文件
   - 处理数据
   - 检查网络连通性
   - 安装缺失的库（subprocess: pip install）
   - 做任何 Python 能做的事

2. **shell**: 执行 Shell 命令。

3. **ask_user**: 当你确实无法独立完成时，向用户求助。

你还有已学会的技能（skills），优先使用已有技能。

## 你的思考流程（每次任务必须遵循）

1. **分析**: 用户想要什么？我需要什么能力？需要真实数据还是纯计算？
2. **自检**: 我有已学会的技能可以做这件事吗？
3. **判断环境**: 这个任务需要网络吗？先检查网络连通性。
4. **规划**: 我应该通过什么方式获取信息？（哪些网站？哪些API？）
5. **执行**: 写 Python 代码去实际获取数据、处理数据。
6. **观察**: 代码执行结果是什么？数据拿到了吗？格式对吗？
7. **重试**: 如果失败，分析原因，换一种方法再试。
8. **回答**: 基于真实获取的数据，给用户组织一个清晰的回答。

## 常见任务的正确处理方式

- **搜索信息/新闻** → 用搜索引擎！通过 requests 调用 Google/Baidu/Bing 搜索，解析搜索结果页面。除非用户指定特定网站，否则一律用搜索引擎。推荐用 Bing 搜索（无需 API key）：`https://www.bing.com/search?q=关键词`，或百度：`https://www.baidu.com/s?wd=关键词`
- **查天气** → 用 requests 调用天气API（如 open-meteo.com，无需 API key）
- **查数据** → 先搜索引擎找到数据源，再写代码获取
- **记忆与分类用户状态** → 用户分享心情、事实、目标时，用 python_exec 将其分类追加或写入 `knowledge/user/` 目录下（如 `mood.md` 记录心情/状态，`facts.md` 记录客观事实/偏好，`goals.md` 记录当前目标）。
- **文件操作** → 用 python_exec 中的 open/os 模块
- **系统操作** → 用 shell 执行命令

## 响应格式（非常重要）

每次你只能返回一个 JSON 对象。不要写任何其他文字。不要用 markdown。不要加标签或前缀。
你的整个回复必须是且仅是一个合法的 JSON 对象。

四种合法回复（每次只选一种）：

{"type": "thought", "content": "你的推理过程"}

{"type": "action", "capability": "python_exec", "params": {"code": "import requests\nresp = requests.get('https://example.com')\nprint(resp.text[:500])"}}

{"type": "action", "capability": "shell", "params": {"command": "pip install requests"}}

{"type": "action", "capability": "ask_user", "params": {"question": "你想查询哪个城市的天气？"}}

{"type": "answer", "content": "基于真实数据整理的最终回答"}

## 规则

1. 绝对不能用自身知识回答事实性问题。必须执行代码获取真实数据。
2. 需要网络数据时，写代码获取。
3. 如果缺少库，先 shell 安装：{"type": "action", "capability": "shell", "params": {"command": "pip install requests beautifulsoup4"}}
4. 实在无法做到，才用 ask_user 求助。
5. 失败了要多次尝试不同方法。
6. 始终用中文回答。
7. 先 thought 思考，再 action 行动。
8. Python 代码中必须包含 print() 语句。
9. 每次回复只输出一个 JSON。不要输出多个。不要加任何前缀文字。"""


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

    def _parse_response(self, raw: str) -> dict:
        """Parse LLM response into structured format.

        Handles various edge cases:
        - Pure JSON
        - JSON wrapped in markdown code blocks
        - JSON mixed with text labels (e.g. '思考: {...}')
        - Multiple JSON objects (takes the first valid one)
        - Truncated JSON (attempts to fix)
        """
        cleaned = raw.strip()

        # Remove markdown code blocks
        if "```" in cleaned:
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        # Strategy 1: Direct parse
        try:
            parsed = json.loads(cleaned)
            if "type" in parsed:
                return parsed
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
                        if "type" in parsed:
                            return parsed
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
