# MONAD — Personal AGI Operating Core

> 不是聊天机器人，不是工具匹配器，而是一个**目标驱动的自主学习理性执行内核**。

## Core Philosophy

*   **文件系统即数据库：** 所有知识（公理、环境知识、技能、经验、用户记忆）全部以 Markdown 文件持久化在本地文件系统中。没有向量数据库，没有 RAG，没有任何外部依赖。
*   **绝对理性：** MONAD 遵循严格的推理循环（分析 → 自检 → 学习 → 执行 → 反思）来达成目标。
*   **自主学习：** 不预装 100 个工具，只有 4 个"本能"（手🤲、口令🗣️、眼👁️、对话💬）。其他一切能力都是 MONAD 通过写代码、执行代码来**自己学会**的。
*   **LLM = 高级指令执行器：** LLM 没有记忆，没有知识。所有事实性信息必须通过执行代码或感知互联网获取，绝不能依赖 LLM 自身的训练数据。
*   **万事不决先搜索：** 执行过程中遇到任何困难（报错、缺库、不知道怎么做），第一反应是用 `web_fetch` 搜索解决方案。但如果是用户意图不清晰，则必须先问用户。一句话：**query 不清楚 → 问用户；执行遇困难 → 先搜索**。

## Basic Capabilities（4 个"本能"）

| 能力 | 隐喻 | 说明 |
|------|------|------|
| `python_exec` | 手 🤲 | 执行 Python 代码。万能后手，通过它可以处理数据、调 API、读写文件、安装库——学会任何事 |
| `shell` | 口令 🗣️ | 执行 Shell 命令 |
| `web_fetch` | 眼 👁️ | 感知互联网。直接看到网页内容，支持 fast/stealth/browser 三种模式（基于 Scrapling） |
| `ask_user` | 对话 💬 | 确实无法独立完成时，向用户求助 |

## Knowledge Architecture

```text
knowledge/
├── axioms/          # 系统公理（MONAD 行为准则）
├── environment/     # 世界知识（搜索引擎用法、API 列表等）
├── user/            # 分类化用户记忆（见下文）
│   ├── facts.md     #   客观事实与偏好
│   ├── mood.md      #   当前状态与心情
│   └── goals.md     #   长期目标与项目
├── skills/          # 自动生成的可复用技能
├── experiences/     # 每次任务的执行日志与反思
├── protocols/       # 异常处理协议
└── tools/           # 3 个基础能力的文档
```

### 分类化用户记忆（Categorized Memory）

MONAD 不使用 RAG，不做语义检索。用户记忆采用**标签化分类存储**：

| 文件 | 内容 | 示例 |
|------|------|------|
| `user/facts.md` | 客观事实与偏好 | "偏好 Python"、"常用路径 /Users/Yam" |
| `user/mood.md` | 心情与临时状态 | "今天很累，回答简短些" |
| `user/goals.md` | 长期目标与项目 | "正在开发 MONAD 自学习 Agent" |

**演化路径：** 数据量小时用单文件；膨胀后分细类子目录（如 `facts/coding.md`、`facts/apis.md`）；再膨胀时让 MONAD 自己用代码做摘要压缩——永远不引入额外复杂性。

## How It Works

当你给 MONAD 一个目标（如"杭州今天天气咋样"）：

1.  **分析 & 自检：** Reasoner 加载知识库，检查是否已有 `get_weather` 技能。
2.  **规划 & 执行：** 没有技能？写 Python 代码调用天气 API。
3.  **观察 & 重试：** 执行代码，观察 stdout。失败则换方法再试。
4.  **回答：** 基于真实数据整理结果返回给用户。
5.  **反思 & 学习：** Reflection 模块分析执行过程；SkillBuilder 判断是否应抽象为可复用技能。

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

*或者从源码自建：*
```bash
git clone https://github.com/hscspring/Monad.git
cd Monad
pip install -e .
```

**2. 安装浏览器内核（必须）**
MONAD 的 `web_fetch` 能力依赖 Chromium 来抓取动态网页：
```bash
playwright install chromium
```

**3. 配置模型**
首次运行时，MONAD 会自动在 `~/.monad/` 生成工作区。请修改 `~/.monad/.env` 中的 LLM Base URL、API Key 和模型名称。

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

### 系统自检
```bash
monad --test
```

> **提示**: 飞书模式需要额外安装依赖：`pip install monad-core[feishu]`

### 运行单元测试
```bash
python -m pytest tests/ -v
```
