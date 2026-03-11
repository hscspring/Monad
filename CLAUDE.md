# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MONAD** is a Personal AGI Operating Core - a self-learning, stateless, rational agent system. Unlike traditional agents with hardcoded tools, MONAD autonomously learns by writing and executing Python code, then saves successful experiences as reusable skills.

### Core Philosophy

- **Stateless Design**: No chat history; every task starts with fresh context. Vital information persists via reflection loops to markdown files.
- **File System as Database**: All knowledge (axioms, skills, experiences, user context) stored as markdown files. No vector DB, no RAG.
- **Absolute Rationality**: Follows strict reasoning loop: Analyze → Self-check → Learn → Execute → Reflect
- **Search First Principle**: When stuck (errors, missing packages), MONAD uses `web_fetch` to search for solutions, never guesses. Only asks user when the query itself is unclear.
- **URL-First Principle**: When the user provides a specific URL, MONAD must access it directly first, not search for it. Search engines are a fallback.
- **LLM as Command Executor**: LLM training data is disregarded. All factual information must be retrieved from real world via code execution or web perception.
- **Experience Hygiene**: Failed experiences are tagged `[FAILED]` and excluded from reasoning context to prevent experience pollution.

### Basic Capabilities (4 "Instincts")

MONAD ships with only 4 built-in capabilities:
1. **python_exec** - Execute arbitrary Python code
2. **shell** - Execute shell commands
3. **web_fetch** - Fetch web pages (3 modes: fast HTTP, stealth anti-bot, browser JS render)
4. **ask_user** - Request clarification from user

Everything else is learned by generating and executing code.

## Commands

### Development & Testing

```bash
# Install from source
pip install -e .

# browser mode uses system Chrome — no 'playwright install' needed

# Run self-test
monad --test

# Run unit tests
pytest tests/ -v
python -m pytest tests/ -v
```

### Running MONAD

```bash
# Web UI (default)
monad

# Interactive CLI mode
monad --cli

# Feishu (Lark) bot mode
APP_ID=xxx APP_SECRET=yyy monad --feishu
```

### Configuration

- Workspace: `~/.monad/`
- Config: `~/.monad/.env` (created on first run with interactive setup)
- LLM settings: `MONAD_BASE_URL`, `MONAD_API_KEY`, `MODEL_ID`

## Architecture

### Directory Structure

```
monad/
├── cognition/          # Reasoning engine
│   └── reasoner.py     # Multi-turn ReAct loop (max 15 turns)
├── core/
│   ├── loop.py         # Main orchestration: Input → Reason → Reflect
│   └── llm.py          # LLM API wrapper
├── execution/
│   └── executor.py     # Executes capabilities & learned skills
├── knowledge/
│   └── vault.py        # File system knowledge I/O
├── learning/
│   ├── reflection.py   # Post-task experience summarization
│   └── skill_builder.py # Auto-generates reusable skills
├── tools/              # 4 basic capabilities
│   ├── python_exec.py
│   ├── shell.py
│   ├── web_fetch.py
│   └── ask_user.py
└── interface/
    ├── web.py          # FastAPI web UI
    ├── feishu.py       # Feishu bot integration
    └── output.py       # Terminal output formatting
```

### Knowledge Directory (`~/.monad/knowledge/`)

```
knowledge/
├── axioms/             # System behavioral principles (rationality.md)
├── environment/        # World knowledge (internet.md)
├── user/               # User context (facts.md, mood.md, goals.md)
├── skills/             # Auto-generated reusable skills
│   └── <skill_name>/
│       ├── skill.yaml  # Metadata: name, goal, inputs, steps
│       └── executor.py # Python implementation
├── experiences/        # Post-task reflections
├── protocols/          # Error handling protocols
├── tools/              # Documentation for 4 basic capabilities
├── records/            # Full execution logs per task
└── cache/              # Temporary task results
```

## Key Technical Details

### Reasoner (cognition/reasoner.py)

- Multi-turn ReAct reasoning with max 15 turns
- LLM responds with JSON in 3 types:
  - `{"type": "thought", "content": "reasoning"}` - Internal reasoning
  - `{"type": "action", "capability": "python_exec", "params": {...}}` - Execute capability
  - `{"type": "answer", "content": "final answer"}` - Task completion
- Handles malformed JSON, truncated responses, XML tag leakage from certain models
- System prompt enforces "Search First" principle and rationality rules

### Executor (execution/executor.py)

- Executes 4 basic capabilities
- Dynamically loads learned skills from `knowledge/skills/` by importing `executor.py`
- Skills registered via YAML metadata + Python implementation

### Learning Pipeline

1. **Reflection** (`learning/reflection.py`): Summarizes task execution into concise experience
2. **SkillBuilder** (`learning/skill_builder.py`): Evaluates if task should become reusable skill
3. **Vault** (`knowledge/vault.py`): Persists experiences and skills to markdown/YAML

### Stateless Message Management

- Each task starts with clean context (no chat history accumulation)
- Context built from: axioms + skills + environment + user context + protocols + experiences
- Prevents hallucination buildup from long conversations
- Forces LLM to reason in pure, noise-free environment

## Development Guidelines

### Adding New Capabilities

Don't. MONAD learns by generating code, not by adding hardcoded tools. If you need to add a fundamental capability (like the 4 instincts), add it to `monad/tools/` and register in `executor.py`.

### Testing web_fetch

The `web_fetch` tool has 3 modes:
- `fast`: HTTP requests (fastest)
- `stealth`: Anti-bot browser
- `browser`: Full Chromium with JS rendering
- `auto` (default): Smart fallback fast→stealth→browser

Test all modes: `pytest tests/test_web_fetch.py -v`

### Working with Knowledge Files

All knowledge files are markdown. Use `KnowledgeVault` methods:
- `vault.load_axioms()` - Load system principles
- `vault.load_skills()` - Load available skills
- `vault.load_all_context()` - Load everything for reasoning
- `vault.save_skill(name, goal, inputs, steps, code)` - Save new skill
- `vault.save_experience(query, reflection)` - Save task reflection

### LLM Communication

The Reasoner expects pure JSON responses (no markdown fences, no extra text). The parser handles various edge cases:
- Markdown code blocks (stripped)
- Mixed text + JSON (extracts JSON)
- Truncated JSON (attempts repair)
- XML tags from model leakage (stripped)
- Alternative formats (normalized to standard)

## Common Workflows

### Running a Single Test
```bash
pytest tests/test_web_fetch.py::TestWebFetchAutoMode::test_auto_simple_page -v
```

### Debugging Reasoner Issues
- Check `monad/cognition/reasoner.py` system prompt
- Review JSON parsing in `_parse_response()`
- Examine turn limit (MAX_TURNS = 15)

### Adding Knowledge
Edit files in `~/.monad/knowledge/` or bundled `monad/knowledge/`:
- `axioms/` - Core behavioral principles
- `environment/` - World facts (URLs, APIs)
- `protocols/` - Error handling strategies

### Feishu Integration
Requires optional dependency: `pip install monad-core[feishu]`

## Important Notes

- **Python 3.10+** required
- **Chrome browser** required for web_fetch browser mode (uses system Chrome, no separate install needed)
- **OpenAI-compatible API** required (configured via `~/.monad/.env`)
- User workspace at `~/.monad/` is separate from package code at `monad/`
- First run triggers interactive setup if API key missing
- All output uses Chinese + English (bilingual system messages)
