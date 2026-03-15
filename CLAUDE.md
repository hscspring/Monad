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
- **Experience Staging & Hygiene**: New experiences land in `pending.jsonl` first. Only when the same tag pattern recurs ≥3 times is the best example promoted to `accumulated_experiences.md`. Failed experiences are tagged `[FAILED]` and never promoted.
- **Tag-Based Experience Retrieval**: Experiences scored by `relevance × 2 + recency` (keyword overlap + timestamp). Top entries selected plus 3 most recent as fallback. No vector DB.
- **Anti-Hallucination Verification**: Post-action verification checks filesystem after skill creation actions. Hollow answer guard rejects answers claiming creation without actual write actions.
- **Skill Deduplication (Reuse First)**: System prompt instructs LLM to check existing skills before creating new ones. SkillBuilder supports `skip`/`update`/`create` actions, preferring `update`.

### Basic Capabilities (5 "Instincts")

MONAD ships with 5 built-in capabilities:
1. **python_exec** - Execute arbitrary Python code
2. **shell** - Execute shell commands
3. **web_fetch** - Fetch web pages (3 modes: fast HTTP, stealth anti-bot, browser JS render)
4. **ask_user** - Request clarification from user
5. **desktop_control** - Control any desktop app via screenshot + OCR + keyboard/mouse (optional: `pip install monad-core[desktop]`)

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
│   └── reasoner.py     # Multi-turn ReAct loop (max 30 turns)
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
├── tools/              # 5 basic capabilities
│   ├── python_exec.py
│   ├── shell.py
│   ├── web_fetch.py
│   ├── ask_user.py
│   └── desktop_control.py
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
├── skills/             # Reusable skills (built-in + auto-generated)
│   └── <skill_name>/
│       ├── skill.yaml  # Metadata: name, goal, inputs, steps, triggers
│       └── executor.py # Python implementation with run(**kwargs)
├── experiences/        # Two-tier experience memory
│   ├── pending.jsonl            # Short-term staging area
│   └── accumulated_experiences.md  # Long-term promoted experiences
├── protocols/          # Error handling protocols
├── tools/              # Documentation for 5 basic capabilities
├── records/            # Full execution logs per task
└── cache/              # Temporary task results
```

## Key Technical Details

### Reasoner (cognition/reasoner.py)

- Multi-turn ReAct reasoning with max 30 turns
- LLM responds with JSON in 3 types:
  - `{"type": "thought", "content": "reasoning"}` - Internal reasoning
  - `{"type": "action", "capability": "python_exec", "params": {...}}` - Execute capability
  - `{"type": "answer", "content": "final answer"}` - Task completion
- Handles malformed JSON, truncated responses, XML tag leakage from certain models
- System prompt enforces "Search First" principle, "Reuse First" for skills, and rationality rules
- System prompt dynamically injects current OS/platform info so LLM generates platform-correct commands
- Post-action verification: checks skill files exist after creation actions
- Hollow answer guard: rejects answers claiming creation without write actions

### Executor (execution/executor.py)

- Executes 5 basic capabilities
- Loads skills exclusively from `~/.monad/knowledge/skills/` (via `CONFIG.skills_path`)
- Injects MONAD's tool functions (`web_fetch`, `shell`, `python_exec`, `ask_user`) into skill modules at load time
- `python_exec` pre-injects `os`, `sys`, `web_fetch`, `shell`, `MONAD_OUTPUT_DIR` into execution namespace

### Learning Pipeline

1. **Reflection** (`learning/reflection.py`): Summarizes task execution with tags into concise experience
2. **SkillBuilder** (`learning/skill_builder.py`): Evaluates existing skills first; supports `skip`/`update`/`create` actions
3. **Vault** (`knowledge/vault.py`): Two-tier experience storage (pending → promote); tag-based retrieval with relevance+recency scoring

### Stateless Message Management

- Each task starts with clean context (no chat history accumulation)
- Context built from: axioms + skills + environment + user context + protocols + experiences
- Prevents hallucination buildup from long conversations
- Forces LLM to reason in pure, noise-free environment

## Development Guidelines

### Adding New Capabilities

Don't. MONAD learns by generating code, not by adding hardcoded tools. If you need to add a fundamental capability (like the 5 instincts), add it to `monad/tools/` and register in `executor.py`.

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
- `vault.save_experience(query, reflection, success, tags)` - Save task reflection (stages to pending.jsonl, auto-promotes)

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
- Examine turn limit (MAX_TURNS = 30)

### Adding Knowledge
Edit files in `~/.monad/knowledge/` (primary) or bundled `monad/knowledge/` (synced incrementally on startup — new files only, never overwrites user changes):
- `axioms/` - Core behavioral principles
- `environment/` - World facts (URLs, APIs)
- `protocols/` - Error handling strategies
- `skills/` - Reusable skills (built-in: web_to_markdown, parse_document, fetch_topic_news, publish_to_xhs, doc_to_knowledge_map, record_screen)

### Desktop Control
Requires optional dependency: `pip install monad-core[desktop]`

### Screen Recording
`record_screen` skill uses `ffmpeg` (macOS: AVFoundation). Requires:
1. `brew install ffmpeg`
2. Grant Screen Recording permission to Terminal/Python in System Settings → Privacy & Security → Screen Recording

Usage: `record_screen(action="start")` / `record_screen(action="stop")` — non-blocking background process.

### Feishu Integration
Requires optional dependency: `pip install monad-core[feishu]`

### Install Everything
`pip install monad-core[all]`

## Important Notes

- **Python 3.10+** required
- **Chrome browser** required for web_fetch browser mode (uses system Chrome, no separate install needed)
- **OpenAI-compatible API** required (configured via `~/.monad/.env`)
- User workspace at `~/.monad/` is separate from package code at `monad/`
- First run triggers interactive setup if API key missing
- All output uses Chinese + English (bilingual system messages)
