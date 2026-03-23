# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MONAD** is a Personal AGI Operating Core - a self-learning, stateless, rational agent system. Unlike traditional agents with hardcoded tools, MONAD autonomously learns by writing and executing Python code, then saves successful experiences as reusable skills.

### Core Philosophy

- **Minimal Dependencies**: MONAD keeps external dependencies as few and lightweight as possible. Never introduce heavy/complex libraries when a simpler alternative exists. Prefer pure-Python solutions over those requiring system-level C libraries. When choosing between tools, always pick the one with the smallest dependency footprint. This is a top priority.
- **Stateless Design**: No chat history; every task starts with fresh context. Vital information persists via reflection loops to markdown files.
- **File System as Database**: All knowledge (axioms, skills, experiences, user context) stored as markdown files. No vector DB, no RAG.
- **Absolute Rationality**: Follows strict reasoning loop: Analyze → Self-check → Learn → Execute → Reflect
- **Search First Principle**: When stuck (errors, missing packages), MONAD uses `web_fetch` to search for solutions, never guesses. Only asks user when the query itself is unclear.
- **URL-First Principle**: When the user provides a specific URL, MONAD must access it directly first, not search for it. Search engines are a fallback.
- **LLM as Command Executor**: LLM training data is disregarded. All factual information must be retrieved from real world via code execution or web perception.
- **Capability Evolution, Not Identity Evolution**: Unlike OpenClaw (which rewrites its personality files), MONAD only evolves skills and protocols. Axioms are immutable. Learning produces executable code, not text memories.
- **Self-Improvement Loop**: During idle time, `SelfEvaluator` analyzes past failures by tag, `CuriosityEngine` researches fixes via web_fetch, and applies updates to skills/protocols. Every session must produce a concrete change.
- **Experience Staging & Hygiene**: New experiences land in `pending.jsonl` first. Only when the same tag pattern recurs ≥3 times is the best example promoted to `accumulated_experiences.md`. Failed experiences are tagged `[FAILED]` and never promoted.
- **Tag-Based Experience Retrieval**: Experiences scored by `relevance × 2 + recency` (jieba-segmented keyword overlap + timestamp). Top entries selected plus 3 most recent as fallback. No vector DB.
- **Anti-Hallucination Verification**: Post-action verification checks filesystem after skill creation actions. LLM-based completion check validates all subtasks are done before accepting an answer.
- **Skill Deduplication (Reuse First)**: System prompt instructs LLM to check existing skills before creating new ones. SkillBuilder supports `skip`/`update`/`create` actions, preferring `update`.
- **Skill Teardown**: Skills can declare a `teardown` field in `skill.yaml` naming another skill to run on task failure (e.g. `start_recording` → `stop_recording`). The core loop auto-runs teardowns when a task fails, preventing resource leaks like orphaned ffmpeg processes.
- **LLM Retry on Transient Failures**: `llm_call()` retries up to 3 times with exponential backoff (2s→4s→8s) on 5xx, timeout, and connection errors. The reasoner loop also tolerates up to 3 consecutive LLM failures before aborting, consuming a turn instead of killing the task.

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
- Startup: `init_workspace()` in `monad.config` is called from CLI/web/Feishu entry points (creates dirs, syncs bundled knowledge + schedules, loads `.env`, configures loguru). Importing `config` alone does **not** run I/O.
- Web UI: `WEB_HOST`, `WEB_PORT`, `WEB_MAX_UPLOAD_BYTES` (optional; defaults `127.0.0.1`, `8000`, 10 MiB)
- Scheduler: `IDLE_THRESHOLD_MINUTES` (30), `PROACTIVE_CHECK_INTERVAL` (60s), `DAILY_LEARNING_BUDGET` (5)
- Launch mode: `LAUNCH_MODE` module variable (`"cli"`, `"web"`, `"feishu"`), set by `main.py`

## Architecture

### Directory Structure

```
monad/
├── cognition/          # Reasoning engine
│   ├── reasoner.py     # Multi-turn ReAct loop (max 30 turns)
│   ├── prompts.py      # System prompts for reasoner, planner, completion checker
│   ├── parser.py       # JSON response parsing with error recovery
│   ├── hints.py        # Smart hints injected after actions
│   └── planning.py     # Plan parsing, JSON array extraction, semantic capability matching
├── core/
│   ├── loop.py         # Main orchestration: Input → Reason → Reflect → Self-improve
│   └── llm.py          # LLM API wrapper with retry logic
├── execution/
│   ├── executor.py     # Executes capabilities & learned skills
│   └── context.py      # TaskState — shared state dict for a single task
├── types.py            # Shared typing (ToolFn protocol)
├── knowledge/
│   ├── vault.py        # File system knowledge I/O
│   └── schedule.py     # macOS Calendar/Reminders reader
├── learning/
│   ├── reflection.py       # Post-task experience summarization
│   ├── skill_builder.py    # Auto-generates reusable skills
│   ├── personalization.py  # Post-task user knowledge extraction
│   ├── self_eval.py        # Self-evaluation: failure pattern analysis
│   └── curiosity.py        # Curiosity engine: targeted skill/protocol improvement
├── proactive/          # Proactive behavior engine
│   ├── scheduler.py    # APScheduler-based background job checker
│   ├── jobs.py         # Job model, YAML persistence, schedule format parser
│   ├── notify.py       # Multi-channel notification routing
│   └── _feishu_bridge.py  # Feishu client reference for proactive notifications
├── tools/              # 5 basic capabilities + helpers
│   ├── python_exec.py
│   ├── shell.py
│   ├── web_fetch.py
│   ├── ask_user.py
│   ├── desktop_control.py
│   └── _schedule_helpers.py  # schedule_task(), monitor_condition(), etc.
└── interface/
    ├── web.py          # FastAPI web UI
    ├── feishu.py       # Feishu bot integration
    └── output.py       # Terminal output formatting
```

### Knowledge Directory (`~/.monad/knowledge/`) and Workspace

```
~/.monad/
├── knowledge/
│   ├── axioms/             # System behavioral principles (rationality.md) — IMMUTABLE
│   ├── environment/        # World knowledge (internet.md)
│   ├── user/               # User context (facts.md, mood.md, goals.md)
│   ├── skills/             # Reusable skills (built-in + auto-generated)
│   │   └── <skill_name>/
│   │       ├── skill.yaml  # Metadata: name, goal, inputs, outputs, steps, triggers, dependencies, teardown, composition
│   │       └── executor.py # Python implementation with run(**kwargs)
│   ├── experiences/        # Two-tier experience memory
│   │   ├── pending.jsonl            # Short-term staging area
│   │   └── accumulated_experiences.md  # Long-term promoted experiences
│   ├── protocols/          # Error handling protocols
│   ├── tools/              # Documentation for 5 basic capabilities + schedule helpers
│   ├── records/            # Full execution logs per task + self-eval reports
│   └── cache/              # Temporary task results + curiosity_state.json
├── schedules/              # Proactive job definitions (YAML, one per job)
│   └── self_improvement.yaml  # Default idle-triggered self-improvement job
└── .env                    # LLM API configuration
```

## Key Technical Details

### Cognition Module (cognition/)

The cognition layer is split into focused modules:
- **`reasoner.py`** — ReAct loop orchestration, plan tracking, answer validation
- **`prompts.py`** — System prompts (`build_reasoner_system`, `PLAN_SYSTEM`, `COMPLETION_CHECK_SYSTEM`, `PERSONALIZATION_SYSTEM`) with runtime platform injection
- **`parser.py`** — JSON response parsing (`parse_response`, `clean_llm_output`, `parse_tags`), truncated JSON repair, `[TOOL_CALL]` format handling
- **`hints.py`** — Post-action contextual hints for shell and desktop_control
- **`planning.py`** — Plan decomposition parsing (`parse_plan_steps`, `extract_json_array`), semantic capability matching (`action_satisfies_planned_capability`), `BASIC_CAPABILITIES` constant

Key behaviors:
- **Task Decomposition**: Before the ReAct loop, multi-step tasks are decomposed into an explicit ordered plan via LLM. Plan is tracked throughout execution (`✅`/`⬜`), injected into each turn's context, and used for deterministic completion checking.
- **Semantic Plan Matching**: `_update_plan` uses `action_satisfies_planned_capability` to handle cases where the LLM uses an equivalent but different capability (e.g. `python_exec` + `requests` for a `web_fetch` step). `_reconcile_plan_from_actions` replays all actions before answer validation.
- Multi-turn ReAct reasoning with max 30 turns
- LLM responds with JSON in 3 types:
  - `{"type": "thought", "content": "reasoning"}` - Internal reasoning
  - `{"type": "action", "capability": "python_exec", "params": {...}}` - Execute capability
  - `{"type": "answer", "content": "final answer"}` - Task completion
- Handles malformed JSON, truncated responses, XML tag leakage from certain models
- System prompt enforces "Search First" principle, "Reuse First" for skills, and rationality rules
- System prompt dynamically injects current OS/platform info so LLM generates platform-correct commands
- Post-action verification: checks skill files exist after creation actions
- LLM-based task completion check: calls LLM to semantically validate all subtasks are done before accepting an answer (fail-open with max 3 rejections to prevent loops)

### TaskState (execution/context.py)

- Shared `dict` subclass that lives for one `solve()` invocation
- Every action's **full, untruncated** result is auto-stored via `state.task_state.store(capability, result)` in `_handle_action`
- Keys follow the pattern `step_{n}_{capability}` (e.g. `step_1_web_fetch`, `step_2_python_exec`)
- `summary()` produces a compact index for LLM context (keys + char counts only)
- Injected into `python_exec` as `task_state` variable in exec_globals, and into skill modules as `module.task_state`
- LLM generates code like `content = task_state["step_1_web_fetch"]` to access full prior results
- This transforms data flow from prompt-driven (truncated text) to state-driven (direct memory reference)

### Executor (execution/executor.py)

- Executes 5 basic capabilities and learned skills
- Loads skills exclusively from `~/.monad/knowledge/skills/` (via `CONFIG.skill_dir(name)`)
- Supports **composite skills** in two flavors:
  - `composition.sequence` — simple list of sub-skill names, all receive the same kwargs
  - `composition.steps` — ordered sub-skills with **parameter mapping**: `{{kwargs.X}}` references caller input, `{{skill_name}}` references a previous step's return value. Resolved by `_resolve_templates`.
- Injects MONAD's tool functions (`web_fetch`, `shell`, `python_exec`, `ask_user`) into skill modules at load time
- `python_exec` pre-injects `os`, `sys`, `web_fetch`, `shell`, `MONAD_OUTPUT_DIR`, `task_state`, `schedule_task`, `monitor_condition`, `list_schedules`, `cancel_schedule` into execution namespace
- Passes `task_state` through `execute()` → `_try_skill()` → `_load_and_run_skill()` for full propagation

### Learning Pipeline

Three parallel learners run after every successful task:

1. **Reflection** (`learning/reflection.py`): Summarizes task execution with tags into concise experience. Uses centralized `clean_llm_output` from `parser.py`.
2. **SkillBuilder** (`learning/skill_builder.py`): Evaluates existing skills first; supports `skip`/`update`/`create`/composite actions. Receives rich execution traces (`actions_full` / `step_results_full`). Generated code goes through LLM review (`_review_code`) then isolated smoke test (`_smoke_run_skill_code`) before saving.
3. **Personalizer** (`learning/personalization.py`): Extracts user facts, preferences, and goals from the interaction and writes them to `user/` knowledge files. Same principle as Reflection and SkillBuilder — execute, extract, persist.
4. **Vault** (`knowledge/vault.py`): Two-tier experience storage (pending → promote); tag-based retrieval with relevance+recency scoring. `save_skill` supports optional `composition` dict for composite skills. User context write API: `update_user_facts`, `update_user_goals`, `update_user_mood`.

### Self-Learning Pipeline (Idle-time)

Two additional learners run during idle time (triggered by scheduler):

5. **SelfEvaluator** (`learning/self_eval.py`): Reads all `pending.jsonl` entries, groups by tags, calculates per-category success/failure rates. LLM identifies weak areas and generates improvement objectives. Saves reports to `records/self_eval_<date>.md`.
6. **CuriosityEngine** (`learning/curiosity.py`): Takes improvement objectives from SelfEvaluator, researches via `web_fetch`, generates concrete skill/protocol updates via LLM, writes changes to filesystem. Budget: 5 sessions/day, 2 objectives/session. State persisted in `cache/curiosity_state.json`.

### Proactive Scheduler

- **APScheduler** `BackgroundScheduler` runs in daemon thread, checks jobs every 60 seconds
- Jobs stored as YAML in `~/.monad/schedules/`, loaded by `proactive/jobs.py`
- Three job types: `cron` (time-based), `monitor` (condition check), `idle` (idle-triggered)
- Simple schedule format: `daily HH:MM`, `hourly`, `every Nm`/`Nh`, `weekly MON HH:MM`
- Proactive tasks go into `MonadLoop.proactive_queue`, processed when user is idle
- Notification follows launch mode: web→WebSocket, feishu→Feishu msg, cli→terminal
- `python_exec` injects `schedule_task()`, `monitor_condition()`, `list_schedules()`, `cancel_schedule()`
- Config constants: `IDLE_THRESHOLD_MINUTES=30`, `PROACTIVE_CHECK_INTERVAL=60`, `DAILY_LEARNING_BUDGET=5`
- `LAUNCH_MODE` module-level variable in `config.py`, set by `main.py` at startup

### Stateless Message Management

- Each task starts with clean context (no chat history accumulation)
- Context built from: axioms + skills + environment + user context + schedule + protocols + experiences
- User context grows via Personalizer, but each task independently loads the current state
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
- `vault.save_skill(name, goal, inputs, steps, code, dependencies={"python": [...], "system": [...]}, composition={"sequence": [...]}, outputs={"key": "desc"})` - Save new skill (dependencies auto-installed on execution; composition for YAML-only composite skills; outputs declares return values)
- `vault.save_experience(query, reflection, success, tags)` - Save task reflection (stages to pending.jsonl, auto-promotes)
- `vault.update_user_facts(["new fact"])` - Append to user/facts.md (deduplicates)
- `vault.update_user_goals(["goal"])` - Rewrite user/goals.md
- `vault.update_user_mood("mood text")` - Overwrite user/mood.md with timestamp

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
- Check system prompts in `monad/cognition/prompts.py`
- Review JSON parsing in `monad/cognition/parser.py` (`parse_response`)
- Check plan parsing in `monad/cognition/planning.py` (`parse_plan_steps`, `action_satisfies_planned_capability`)
- Examine turn limit (`MAX_TURNS` in `monad/config.py`)

### Adding Knowledge
Edit files in `~/.monad/knowledge/` (primary) or bundled `monad/knowledge/` (synced incrementally on startup — new files only, never overwrites user changes):
- `axioms/` - Core behavioral principles
- `environment/` - World facts (URLs, APIs)
- `protocols/` - Error handling strategies
- `skills/` - Reusable skills (built-in: web_to_markdown, parse_document, fetch_topic_news, publish_to_xhs, markdown_to_knowledge_map, markdown_to_pdf, start_recording, stop_recording)

### Desktop Control
Requires optional dependency: `pip install monad-core[desktop]`

### Screen Recording
`start_recording` / `stop_recording` skills use `ffmpeg` (macOS: AVFoundation). Requires:
1. `brew install ffmpeg`
2. Grant Screen Recording permission to Terminal/Python in System Settings → Privacy & Security → Screen Recording

`start_recording` outputs `.mkv` (safe to SIGKILL); `stop_recording` transcodes to `.mp4` via a fresh ffmpeg process, guaranteeing a valid moov atom.

### Feishu Integration
Requires optional dependency: `pip install monad-core[feishu]`

### Install Everything
`pip install monad-core[all]`

## Design Documents

- **[DESIGN.md](DESIGN.md)** — Complete architecture philosophy, design decisions, trade-offs, and the TaskState design
- **[FUTURE.md](FUTURE.md)** — Roadmap, architecture evolution history, and deferred design directions

## Important Notes

- **Python 3.10+** required
- **Chrome browser** required for web_fetch browser mode (uses system Chrome, no separate install needed)
- **OpenAI-compatible API** required (configured via `~/.monad/.env`)
- User workspace at `~/.monad/` is separate from package code at `monad/`
- **Knowledge sync**: On startup, `skills/`, `protocols/`, `tools/` are always overwritten from the bundled package (system-managed). `user/`, `experiences/`, `axioms/`, `environment/` only get new files (user-managed, never overwritten). Bundled `schedules/` are also synced (new files only, never overwrite user schedules).
- First run triggers interactive setup if API key missing
- All output uses Chinese + English (bilingual system messages)
