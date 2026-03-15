# MONAD — Personal AGI Operating Core

> 不是聊天机器人，不是工具匹配器，而是一个**目标驱动的自主学习理性执行内核**。

## Core Philosophy

*   **文件系统即数据库：** 所有知识（公理、环境知识、技能、经验、用户记忆）全部以 Markdown 文件持久化在本地文件系统中。没有向量数据库，没有 RAG，没有任何外部依赖。
*   **绝对理性：** MONAD 遵循严格的推理循环（分析 → 自检 → 学习 → 执行 → 反思）来达成目标。
*   **自主学习：** 不预装 100 个工具，只有 5 个"本能"（手🤲、口令🗣️、眼👁️、对话💬、屏幕🖥️），外加一组内置 skill 库。其他一切能力都是 MONAD 通过写代码、执行代码来**自己学会**的。
*   **LLM = 高级指令执行器：** LLM 没有记忆，没有知识。所有事实性信息必须通过执行代码或感知互联网获取，绝不能依赖 LLM 自身的训练数据。
*   **无状态消息管理（Stateless）：** 每次用户请求都是一个全新的、干净的消息上下文。MONAD 不依赖 LLM 的 Chat History，而是通过反思循环将关键信息持久化。这确保了推理的纯净性，防止了长对话带来的幻觉堆积。
*   **万事不决先搜索：** 执行过程中遇到任何困难（报错、缺库、不知道怎么做），第一反应是用 `web_fetch` 搜索解决方案。但如果是用户意图不清晰，则必须先问用户。一句话：**query 不清楚 → 问用户；执行遇困难 → 先搜索**。
*   **URL 优先原则：** 当用户给出了具体的 URL 或域名（如"帮我分析 kexue.fm"），MONAD 必须先直接访问该 URL，而不是绕道搜索引擎。搜索引擎是 fallback，不是已知目标的默认入口。
*   **经验分级管道 & 卫生机制：** 经验不会直接进入长期记忆。新经验先落入暂存区（`pending.jsonl`），只有当**相同标签模式出现 ≥3 次**时，才会将最佳样本晋升到永久经验文件——这是一种基于频率的去重机制，灵感来自人类将短期记忆固化为长期记忆的过程。失败经验标记为 `[FAILED]` 且永不晋升，防止"经验污染"。
*   **基于标签的经验检索：** 经验在反思阶段被打上标签。推理时，MONAD 按 `相关性 × 2 + 时效性` 对经验评分（不是语义嵌入，只是关键词重叠 + 时间戳），选取得分最高的条目，并始终包含最近 3 条作为兜底。简单、快速、零基础设施。
*   **反幻觉验证：** LLM 有时会声称"我已创建好技能"但实际上并未写入任何文件。MONAD 在两个层面防御：（1）**行动后验证** —— 在应该创建文件的 action 执行后，系统检查文件系统并将验证结果追加到 LLM 的观察中；（2）**空洞回答拦截** —— 如果 LLM 试图给出声称已完成创建/保存的最终答案，但从未执行过写入操作，该回答将被拒绝，LLM 被强制要求实际执行。
*   **技能去重（复用优先）：** 创建新技能前，系统提示 LLM 先检查已有技能，优先修改而非新建。SkillBuilder 模块独立评估所有已有技能，支持三种操作：`skip`（跳过）、`update`（优先，修改已有）、`create`（新建）——防止技能库产生重复条目。


## Basic Capabilities（5 个"本能"）

| 能力 | 隐喻 | 说明 |
|------|------|------|
| `python_exec` | 手 🤲 | 执行 Python 代码。万能后手，通过它可以处理数据、调 API、读写文件、安装库——学会任何事 |
| `shell` | 口令 🗣️ | 执行 Shell 命令 |
| `web_fetch` | 眼 👁️ | 感知互联网。直接看到网页内容，支持 fast/stealth/browser 三种模式（基于 Scrapling） |
| `ask_user` | 对话 💬 | 确实无法独立完成时，向用户求助 |
| `desktop_control` | 屏幕 🖥️ | 操控任意桌面应用程序。通过截屏 + OCR 识别界面元素，模拟键鼠操作，跨平台（macOS/Windows/Linux） |

> **提示：** `desktop_control` 需要额外安装依赖：`pip install monad-core[desktop]`

## Knowledge Architecture

```text
knowledge/
├── axioms/          # 系统公理（MONAD 行为准则）
├── environment/     # 世界知识（搜索引擎用法、API 列表等）
├── user/            # 分类化用户记忆（见下文）
│   ├── facts.md     #   客观事实与偏好
│   ├── mood.md      #   当前状态与心情
│   └── goals.md     #   长期目标与项目
├── skills/          # 可复用技能（内置 + 自动生成）
│   └── <skill>/
│       ├── skill.yaml   # 元数据：name, goal, inputs, steps, triggers
│       └── executor.py  # Python 实现，入口 run(**kwargs)
├── experiences/     # 两级经验记忆
│   ├── pending.jsonl            # 短期：所有近期经验（暂存区）
│   └── accumulated_experiences.md  # 长期：高频模式晋升后的精华
├── protocols/       # 异常处理协议
└── tools/           # 5 个基础能力 + 内置 skill 的文档
```

### 分类化用户记忆（Categorized Memory）

MONAD 不使用 RAG，不做语义检索。用户记忆采用**标签化分类存储**：

| 文件 | 内容 | 示例 |
|------|------|------|
| `user/facts.md` | 客观事实与偏好 | "偏好 Python"、"常用路径 /Users/Yam" |
| `user/mood.md` | 心情与临时状态 | "今天很累，回答简短些" |
| `user/goals.md` | 长期目标与项目 | "正在开发 MONAD 自学习 Agent" |

**演化路径：** 数据量小时用单文件；膨胀后分细类子目录（如 `facts/coding.md`、`facts/apis.md`）；再膨胀时让 MONAD 自己用代码做摘要压缩——永远不引入额外复杂性。

## 🛠️ 内置 Skill 库

除 5 个本能外，MONAD 预装了一套开箱即用的 skill：

| Skill | 说明 |
|-------|------|
| `record_screen` | 后台录制屏幕为 mp4（基于 ffmpeg）。支持 `start`/`stop`/`status`，非阻塞，可与其他任务并行运行。 |
| `publish_to_xhs` | 发布帖子/文章到小红书，支持图文。 |
| `fetch_topic_news` | 抓取并摘要任意话题的最新新闻。 |
| `parse_document` | 解析 PDF、Word 等文档并提取结构化内容。 |
| `web_to_markdown` | 将任意网页转换为干净的 Markdown。 |
| `doc_to_knowledge_map` | 将文档转化为结构化知识图谱 Markdown。 |

> Skill 由 `executor.py`（Python 实现）+ `skill.yaml`（元数据）组成。MONAD 也能从任意成功任务中自动生成新 skill。

---

## How It Works

当你给 MONAD 一个目标（如"杭州今天天气咋样"）：

1.  **分析 & 自检：** 理解用户意图，并检查本地知识库中是否已有相关技能。
2.  **学习 & 搜索（"万事不决先搜索"）：** 如果任务涉及未知领域或执行报错，MONAD 会通过 `web_fetch` 搜索文档、API 用法或解决方案。这是“学习”阶段，确保行动前掌握必要的“Know-how”。
3.  **执行 & 观察：** 编写并运行 Python 代码或 Shell 命令。MONAD 会将输出作为“观察结果”，用于验证成功或发现新的障碍。
4.  **反思 & 固化：** 任务成功后，`Reflection` 模块带标签总结经验。`SkillBuilder` 评估是否应抽象为永久技能——优先检查已有技能以避免重复。
5.  **验证 & 回答：** 给出最终答案前，系统验证所声称的操作是否确实发生（文件存在、技能已写入）。答案基于经过执行验证的真实数据。

### 💡 深度解析：为什么是无状态（Stateless）？

MONAD 放弃了传统的“长对话记忆（Chat History）”，转而采用每一轮任务完全重置、仅通过文件系统持久化核心信息的“无状态”设计。

*   **抑制幻觉堆积：** 长对话会导致 LLM 注意力分散和上下文污染（Context Pollution）。通过每轮重启消息上下文，我们强制模型在纯净的环境中进行最高效的理性思考。
*   **物理层记忆：** 不同于黑盒化的模型缓存，MONAD 的记忆是可见、可编辑、可审计的 Markdown 文件。这是实现**“个人主权数据”**（Personal Data Sovereignty）的关键一步。
*   **任务原子化：** 每一个目标都是独立且可复现的执行单元。
*   **面向未来：** 我们认为 Agent 的未来是从“模拟聊天”转向“模拟理性执行”。通过“反思循环（Reflection）”实时维护一个**状态白板**，比无休止地堆叠聊天记录更接近通用人工智能的本质。

## Project Structure

```text
MONAD/
├── core/            # 核心循环 + LLM 客户端
├── cognition/       # Reasoner（多轮 ReAct 推理引擎）
├── execution/       # Executor（执行基础能力与已学技能）
├── knowledge/       # 文件系统数据库（见上文）
├── learning/        # 反思引擎 + 技能生成器
├── interface/       # 用户输入/输出
├── tools/           # 基础能力实现
├── design.md        # 原始设计文档
└── main.py          # 入口
```

## Setup

**1. 通过 pip 安装（推荐）**
```bash
pip install monad-core
```

*可选扩展：*
```bash
pip install monad-core[desktop]   # 桌面控制（截屏 + OCR + 键鼠模拟）
pip install monad-core[feishu]    # 飞书机器人集成
pip install monad-core[all]       # 全部安装
```

*或者从源码安装：*
```bash
git clone https://github.com/hscspring/Monad.git
cd Monad
pip install -e .            # 仅核心
pip install -e ".[all]"     # 含全部扩展
```

**2. 配置模型**
首次运行时，MONAD 会自动在 `~/.monad/` 生成工作区。请修改 `~/.monad/.env` 中的 LLM Base URL、API Key 和模型名称。
> **提示**：如果你未手动配置，首次启动时 MONAD 会自动进入交互式配置引导，并在线验证 API 连通性。

## Usage

安装完成后，可以在**终端的任意路径**下直接唤起 MONAD。

### 启动 Web 交互界面 (默认)
```bash
monad
```

### 启动纯命令行交互模式 (经典模式)
```bash
monad --cli
```

### 飞书机器人模式
1. 按照 [飞书机器人配置指南](https://open.feishu.cn/document/develop-an-echo-bot/introduction) 配置好前两步，拿到 `APP_ID` 和 `APP_SECRET`。
2. 启动飞书机器人模式：
```bash
APP_ID=xxx APP_SECRET=yyy monad --feishu
```
> **提示**: 飞书模式需要额外安装依赖：`pip install monad-core[feishu]`

### 系统自检
```bash
monad --test
```

### 运行单元测试
```bash
python -m pytest tests/ -v
```
