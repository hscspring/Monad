<div align="center">
  <h1>🌌 MONAD (v0.1)</h1>
  <p><strong>Personal AGI Operating Core</strong></p>

  <p>
    <a href="README_zh.md">🇨🇳 简体中文 (Chinese)</a> •
    <a href="#-how-it-works">How It Works</a> •
    <a href="#-installation">Installation</a> •
    <a href="#-architecture">Architecture</a>
  </p>
  
  <p>
    <img src="https://img.shields.io/badge/-Python_3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
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
*   **Self-Learning & Self-Evolving:** Instead of shipping with 100 tools, MONAD ships with only 4 basic instincts (hands 🤲, voice 🗣️, eyes 👁️, dialogue 💬). It learns everything else by generating code.
*   **LLM as a Command Executor:** The LLM's own training data is disregarded. All factual information must be retrieved from the real world via code execution or web perception.
*   **Search First, Ask Later:** When stuck during execution (errors, missing packages, unfamiliar tools), MONAD's first instinct is to search the web via `web_fetch`, never to guess. But if the user's intent is unclear, MONAD asks the user first. In short: **unclear query → ask user; execution problem → search first**.

---

## ⚡ Basic Capabilities ("Instincts")

MONAD comes with only four built-in capabilities:

| Capability | Metaphor | Description |
| :--- | :--- | :--- |
| 🐍 `python_exec` | Hands 🤲 | Evaluate arbitrary Python code. Process data, call APIs, read/write files, install libraries—learn to do anything. |
| 💻 `shell` | Voice 🗣️ | Execute shell commands on the host operating system. |
| 👁️ `web_fetch` | Eyes 👁️ | Perceive the internet directly. Fetch web pages with 3 modes: fast (HTTP), stealth (anti-bot), browser (JS render). Powered by Scrapling. |
| 🙋 `ask_user` | Dialogue 💬 | Ask the user for clarification when it truly cannot proceed independently. |

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
├── skills/          # Auto-generated reusable Python skills
├── experiences/     # Execution logs and post-task reflections
├── protocols/       # Error handling protocols
└── tools/           # Documentation for the 4 basic capabilities
```

---

## ⚙️ How It Works

When you give MONAD an objective (e.g., *"What is the weather in Hangzhou today?"*):

1.  **Analyze & Self-Check:** The Reasoner loads the knowledge base and checks if a `get_weather` skill already exists.
2.  **Plan & Act:** If no skill exists, it writes a Python script using `python_exec` to call a free weather API (e.g., Open-Meteo).
3.  **Observe & Adjust:** It runs the code, observes the standard output. If it crashes, it analyzes the error, patches the code, and retries.
4.  **Answer:** It formats the final retrieved real-world data for the user.
5.  **Reflect & Learn:** After the task, the `Reflection` module analyzes what happened. The `SkillBuilder` then evaluates if the logic should be extracted into a new permanent skill file.

---

## 🚀 Installation

**1. Install via pip (Recommended)**
```bash
pip install monad-core
```

*Alternatively, install from source:*
```bash
git clone https://github.com/hscspring/Monad.git
cd Monad
pip install -e .
```

**2. Install Browser Engine (Required)**
MONAD's `web_fetch` capability requires the Chromium browser engine to parse dynamic web pages:
```bash
playwright install chromium
```

**3. Configure your LLM**
On your first run, MONAD will initialize its workspace in `~/.monad/`. Update `~/.monad/.env` with your LLM Base URL, API Key, and Model name.

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
Connect MONAD to a Feishu bot via WebSocket:
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
