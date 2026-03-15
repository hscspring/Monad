<div align="center">
  <h1>🌌 MONAD</h1>
  <p><strong>Personal AGI Operating Core</strong></p>

  <p>
    <a href="README_zh.md">🇨🇳 简体中文 (Chinese)</a> •
    <a href="#-how-it-works">How It Works</a> •
    <a href="#-installation">Installation</a> •
    <a href="#-architecture">Architecture</a>
  </p>
  
  <p>
    <img src="https://img.shields.io/badge/-Python_3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/-OpenAI_API-412991?style=for-the-badge&logo=openai&logoColor=white" alt="OpenAI API">
    <img src="https://img.shields.io/badge/-ReAct_Agent-FF6F00?style=for-the-badge" alt="ReAct Agent">
  </p>
</div>

<br/>

> **MONAD is not a chatbot or a simple tool-matcher.** It is a self-learning, objective-driven autonomous rational agent core.

Unlike traditional agents that rely on a predefined, hardcoded set of tools, MONAD acts like a rational entity with basic "instincts". It has no memory and no pre-loaded knowledge of how to perform specific tasks (like checking the weather or searching the web).

Instead, it **autonomously learns** how to complete your tasks by writing and executing Python code on the fly, and then saving those successful experiences as reusable skills.

---

## 🧠 Core Philosophy

*   **File System as Database:** The system itself has no memory of past sessions. It persists all learned information (axioms, environment knowledge, learned skills, user context, and experiences) directly to local Markdown files. No vector databases, no RAG, zero external dependencies.
*   **Absolute Rationality:** MONAD follows a strict reasoning loop (`Analyze → Self-check → Learn → Execute → Reflect`) to accomplish goals logically.
*   **Self-Learning & Self-Evolving:** Instead of shipping with 100 tools, MONAD ships with only 5 basic instincts (hands 🤲, voice 🗣️, eyes 👁️, dialogue 💬, screen 🖥️) plus a growing library of built-in skills. It learns everything else by generating code.
*   **LLM as a Command Executor:** The LLM's own training data is disregarded. All factual information must be retrieved from the real world via code execution or web perception.
*   **Stateless Message Management:** Every user request starts with a fresh, clean message context. MONAD doesn't rely on LLM Chat History; instead, it persists vital information via reflection loops. This ensures reasoning purity and prevents hallucination buildup from long conversations.
*   **Search First, Ask Later:** When stuck during execution (errors, missing packages, unfamiliar tools), MONAD's first instinct is to search the web via `web_fetch`, never to guess. But if the user's intent is unclear, MONAD asks the user first. In short: **unclear query → ask user; execution problem → search first**.
*   **URL-First Principle:** When the user provides a specific URL or domain (e.g., *"Analyze kexue.fm"*), MONAD must directly access that URL first, not detour through a search engine. Search engines are a fallback, not the default when a target is already known.
*   **Experience Staging & Hygiene:** Experiences don't go directly into long-term memory. New experiences first land in a staging area (`pending.jsonl`). Only when the same tag pattern recurs **≥3 times** is the best example promoted to the permanent experience file — a frequency-based deduplication inspired by how humans consolidate short-term memory into long-term memory. Failed experiences are tagged `[FAILED]` and never promoted, preventing "experience pollution."
*   **Tag-Based Experience Retrieval:** Experiences are tagged during reflection. At reasoning time, MONAD scores each experience by `relevance × 2 + recency` (not semantic embeddings, just keyword overlap + timestamp), picks the top entries, and always includes the 3 most recent as fallback. Simple, fast, zero infrastructure.
*   **Anti-Hallucination Verification:** LLMs sometimes claim "I created the skill" without actually writing any files. MONAD defends against this at two levels: (1) **Post-Action Verification** — after actions that should create files, the system checks the filesystem and appends verification results to the LLM's observation; (2) **Hollow Answer Guard** — if the LLM tries to deliver a final answer claiming creation/saving but never executed a write action, the answer is rejected and the LLM is forced to actually do the work.
*   **Skill Deduplication (Reuse First):** Before creating a new skill, the system prompts the LLM to check existing skills and prefer modifying them. The SkillBuilder module independently evaluates all existing skills and supports three actions: `skip`, `update` (preferred), or `create` — preventing the skill library from growing duplicate entries.

---

## ⚡ Basic Capabilities ("Instincts")

MONAD comes with five built-in capabilities:

| Capability | Metaphor | Description |
| :--- | :--- | :--- |
| 🐍 `python_exec` | Hands 🤲 | Evaluate arbitrary Python code. Process data, call APIs, read/write files, install libraries—learn to do anything. |
| 💻 `shell` | Voice 🗣️ | Execute shell commands on the host operating system. |
| 👁️ `web_fetch` | Eyes 👁️ | Perceive the internet directly. Fetch web pages with 3 modes: fast (HTTP), stealth (anti-bot), browser (JS render). Powered by Scrapling. |
| 🙋 `ask_user` | Dialogue 💬 | Ask the user for clarification when it truly cannot proceed independently. |
| 🖥️ `desktop_control` | Screen 🖥️ | Control any desktop application via screenshot + OCR + keyboard/mouse. Cross-platform (macOS/Windows/Linux). |

> **Note:** `desktop_control` requires optional dependencies: `pip install monad-core[desktop]`

---

## 📂 Knowledge Architecture

MONAD uses **Categorized Memory** instead of semantic retrieval (RAG).

```text
knowledge/
├── axioms/          # System axioms & core behavioral principles
├── environment/     # World knowledge (e.g., search engine URLs, API endpoints)
├── user/            # Categorized user context (No RAG used here)
│   ├── facts.md     #   Objective facts & preferences (e.g., prefers Python)
│   ├── mood.md      #   Current state & mood
│   └── goals.md     #   Long-term goals & ongoing projects
├── skills/          # Reusable Python skills (built-in + auto-generated)
│   └── <skill>/
│       ├── skill.yaml   # Metadata: name, goal, inputs, steps, triggers
│       └── executor.py  # Python implementation with run(**kwargs)
├── experiences/     # Two-tier experience memory
│   ├── pending.jsonl            # Short-term: all recent experiences (staging area)
│   └── accumulated_experiences.md  # Long-term: promoted high-frequency patterns
├── protocols/       # Error handling protocols
└── tools/           # Documentation for the 5 basic capabilities + built-in skills
```

---

## 🛠️ Built-in Skills

Beyond the 5 core instincts, MONAD ships with a set of ready-to-use skills:

| Skill | Description |
| :--- | :--- |
| `record_screen` | Background screen recording to mp4 via ffmpeg. `start`/`stop`/`status` actions, non-blocking — runs alongside other tasks. |
| `publish_to_xhs` | Publish posts/articles to Xiaohongshu (RED). Supports text + image. |
| `fetch_topic_news` | Fetch and summarize latest news on any topic from the web. |
| `parse_document` | Parse and extract structured content from documents (PDF, Word, etc.). |
| `web_to_markdown` | Convert any web page to clean Markdown. |
| `doc_to_knowledge_map` | Transform a document into a structured knowledge graph in Markdown. |

> Skills are Python modules (`executor.py` + `skill.yaml`). MONAD can also auto-generate new skills from any successful task.

---

## ⚙️ How It Works

When you give MONAD an objective (e.g., *"What is the weather in Hangzhou today?"*):

1.  **Analyze & Self-Check:** Understand intent and check the local knowledge base for existing skills.
2.  **Learn & Research (The "Search First" Principle):** If the task is unknown or an error occurs, MONAD uses `web_fetch` to research documentation, API usage, or solutions. This is the "Learning" phase where it acquires the "how-to" knowledge before acting.
3.  **Execute & Observe:** MONAD writes and executes Python code or shell commands via `python_exec`. It treats the output as "Observations" to verify success or identify new obstacles.
4.  **Reflect & Persist:** After a successful execution, the `Reflection` module summarizes the experience with tags. The `SkillBuilder` evaluates if the logic should be abstracted into a permanent skill — checking existing skills first to avoid duplication.
5.  **Verify & Answer:** Before delivering the final answer, the system verifies that claimed actions actually happened (files exist, skills were written). The answer is based on real-world data verified through execution.

### 💡 Deep Dive: Why Stateless?

MONAD intentionally discards traditional "Chat History" in favor of a **Stateless Design**, where every task starts with a clean context and persists only vital information via the file system.

*   **Mitigating Hallucination:** Long-running chat histories eventually lead to context pollution and attention decay. By resetting the context per task, we force the LLM to reason in a pure, noise-free environment.
*   **Physical Memory:** Unlike black-box model caches, MONAD's memory consists of human-readable Markdown files. This is a deliberate step towards **Personal Data Sovereignty**.
*   **Task Atomicity:** Every objective becomes an independent, reproducible unit of execution.
*   **The Future of Agents:** We believe the evolution of Agents will shift from "simulating conversation" to "simulating rational execution." Maintaining a living **"State Whiteboard"** via reflection loops is far more aligned with the essence of AGI than endlessly stacking chat logs.

---

## 🚀 Installation

**1. Install via pip (Recommended)**
```bash
pip install monad-core
```

*Optional extras:*
```bash
pip install monad-core[desktop]   # Desktop control (screenshot + OCR + keyboard/mouse)
pip install monad-core[feishu]    # Feishu (Lark) bot integration
pip install monad-core[all]       # Everything
```

*Or install from source:*
```bash
git clone https://github.com/hscspring/Monad.git
cd Monad
pip install -e .            # core only
pip install -e ".[all]"     # with all extras
```

**2. Configure your LLM**
On your first run, MONAD will initialize its workspace in `~/.monad/`. Update `~/.monad/.env` with your LLM Base URL, API Key, and Model name. 
> **Note**: If you don't configure this manually, MONAD will guide you through an interactive setup with connectivity validation on your first launch.

---

## 💻 Usage

Once installed, you can start the MONAD agent from **any directory** in your terminal.

### Start Web UI (Default)
Launch the modern browser-based interface:
```bash
monad
```

### Interactive Terminal Mode (Classic)
Start the continuous ReAct agent loop in the CLI:
```bash
monad --cli
```

### Feishu (Lark) Bot Mode
1. Follow the first two steps in the [Feishu Bot Guide](https://open.feishu.cn/document/develop-an-echo-bot/introduction) to create a bot and obtain your `APP_ID` and `APP_SECRET`.
2. Connect MONAD to your Feishu bot via WebSocket:
```bash
APP_ID=xxx APP_SECRET=yyy monad --feishu
```
> **Note**: Requires `pip install monad-core[feishu]` for the `lark-oapi` dependency.

### Self-Test
Verify all modules load correctly and the LLM connection is functioning:
```bash
monad --test
```

### Unit Tests
Run the test suite for all tools:
```bash
python -m pytest tests/ -v
```

---

<div align="center">
  <p>Built with pure rational reasoning 💡</p>
</div>
