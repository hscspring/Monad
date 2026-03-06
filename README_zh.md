# MONAD (v0.1) — Personal AGI Operating Core

> 不是聊天机器人，不是工具匹配器，而是一个**目标驱动的自主学习理性执行内核**。

## Core Philosophy

*   **文件系统即数据库：** 所有知识（公理、环境知识、技能、经验、用户记忆）全部以 Markdown 文件持久化在本地文件系统中。没有向量数据库，没有 RAG，没有任何外部依赖。
*   **绝对理性：** MONAD 遵循严格的推理循环（分析 → 自检 → 学习 → 执行 → 反思）来达成目标。
*   **自主学习：** 不预装 100 个工具，只有 3 个"本能"。其他一切能力都是 MONAD 通过写代码、执行代码来**自己学会**的。
*   **LLM = 高级指令执行器：** LLM 没有记忆，没有知识。所有事实性信息必须通过执行代码从真实数据源获取，绝不能依赖 LLM 自身的训练数据。

## Basic Capabilities（3 个"本能"）

| 能力 | 说明 |
|------|------|
| `python_exec` | 执行 Python 代码。万能后手，通过它可以调 API、爬网页、读写文件、安装库——学会任何事 |
| `shell` | 执行 Shell 命令 |
| `ask_user` | 确实无法独立完成时，向用户求助 |

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

```bash
pip install -r requirements.txt
```

在 `config.py` 中配置 LLM 的 Base URL、API Key 和模型名称。

## Usage

```bash
# 交互模式
python main.py

# 自检
python main.py --test
```
