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
*   **Self-Learning & Self-Evolving:** Instead of shipping with 100 tools, MONAD ships with only 3 basic instincts. It learns everything else by generating code.
*   **LLM as a Command Executor:** The LLM's own training data is disregarded. All factual information must be retrieved from the real world via code execution (e.g., scraping websites, calling APIs).

---

## ⚡ Basic Capabilities ("Instincts")

MONAD comes with only three built-in capabilities:

| Capability | Description |
| :--- | :--- |
| 🐍 `python_exec` | Evaluate arbitrary Python code. The ultimate fallback: call APIs, crawl the web, process data, install missing libraries—learn to do anything a human programmer can do. |
| 💻 `shell` | Execute shell commands on the host operating system. |
| 🙋 `ask_user` | Ask the user for clarification when it truly cannot proceed independently. |

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
└── tools/           # Documentation for the 3 basic capabilities
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

**1. Clone the repository**
```bash
git clone https://github.com/hscspring/Monad.git
cd Monad
```

**2. Install dependencies**
```bash
## Using a virtual environment is highly recommended
pip install -r requirements.txt
```

**3. Configure your LLM**
Update `config.py` with your LLM Base URL, API Key, and Model name (Defaults to an OpenAI-compatible API).

---

## 💻 Usage

### Interactive Terminal Mode
Start the continuous ReAct agent loop:
```bash
python main.py
```

### Self-Test
Verify all modules load correctly and the LLM connection is functioning:
```bash
python main.py --test
```

---

<div align="center">
  <p>Built with pure rational reasoning 💡</p>
</div>
