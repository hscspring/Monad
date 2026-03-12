# Changelog

All notable changes to this project will be documented in this file.

## [0.3.1] - 2026-03-12

### Added
- **Experience Staging (Pending → Promote)**: New experiences no longer go directly into the long-term experience file. They first land in `pending.jsonl` as short-term memory. Only when the same tag pattern recurs ≥3 times is the experience promoted to `accumulated_experiences.md`. This prevents one-off incidents and ephemeral errors from polluting the reasoning context — inspired by OpenClaw's "≥3 times promote" rule.
- **Post-Action Verification**: After `python_exec` or `shell` actions that involve skill creation (detected by path patterns), the Reasoner automatically verifies that the expected `skill.yaml` and `executor.py` files actually exist, appending verification results to the LLM observation. No more "I created the skill" hallucinations.
- **Hollow Answer Guard**: When the user's task involves creation/saving keywords but the LLM attempts to output a final answer without having executed any write actions, the answer is rejected and the LLM is forced to actually perform the work. Addresses the pattern where LLMs describe completion in an `answer` without executing any `action`.
- **Skill Deduplication**: Two-layer defense against duplicate skill creation:
  - *Prompt layer*: System prompt now includes "Step 0 — Reuse First" in the skill creation guide, instructing the LLM to check existing skills and modify them instead of creating new ones when overlap exists.
  - *SkillBuilder layer*: The auto-evaluation prompt now includes all existing skills and supports three actions: `skip` (no skill needed), `update` (modify existing skill), `create` (new skill). The LLM is instructed to prefer `update` over `create` when any existing skill has overlapping functionality.
- **Built-in Skill: web_to_markdown**: Generic web page to Markdown converter using `web_fetch` + BeautifulSoup. Replaces the previous duplicate skills (convert_web_article_to_markdown, convert_wechat_article_to_markdown).
- **Comprehensive Test Suite**: 92 new unit tests across 6 test files covering vault (experience staging, tag filtering, skill I/O), reasoner (JSON parsing, hollow answer guard, action verification), executor (capability routing, skill loading with tool injection), python_exec (injected globals), shell, and reflection (tag extraction, LLM output cleaning).

### Changed
- **Experience Save Flow**: `save_experience()` in `KnowledgeVault` now writes to `pending.jsonl` first, with automatic promotion and cluster cleanup logic.
- **Skill Execution Path**: `Executor._try_skill()` now uses `CONFIG.skills_path` (always `~/.monad/knowledge/skills/`) instead of the package directory. MONAD's 4 tool functions (web_fetch, shell, python_exec, ask_user) are injected into skill modules at load time so skill code can call them directly.
- **Knowledge Sync**: Bundled knowledge is now incrementally synced to user workspace — new files from package updates are copied without overwriting user modifications.
- **python_exec Globals**: `os`, `sys`, `web_fetch`, and `shell` are pre-injected into the execution namespace so LLM-generated code doesn't need to import them.
- **MONAD_OUTPUT_DIR Prompt**: System prompt now explicitly shows the resolved path (`~/.monad/output/`) and a code example, preventing the LLM from treating the variable name as a literal path string.

## [0.3.0] - 2026-03-11

### Added
- **File Upload**: Users can attach files via the web UI (📎 button). Files are saved to `~/.monad/input/` and the path is injected into the user's message as `[attached: /path/to/file]`. The LLM can then read/parse the file using `python_exec` or learned skills.
- **Skill Triggers**: Skills now support a `triggers` field in `skill.yaml` — natural language descriptions of when the skill should be used. Displayed in the skills context to help the LLM match tasks to skills more accurately.
- **Skill Creation Guide in System Prompt**: The LLM now knows the exact file structure (`skill.yaml` + `executor.py`), directory path, and format needed to create new skills. Users can teach MONAD new skills through chat (e.g., "learn a document parsing skill using docling").
- **File Attachment Protocol**: System prompt includes instructions for handling `[attached: ...]` file markers, guiding the LLM to use appropriate parsing methods.

### Changed
- **MAX_TURNS increased to 30**: Up from 15, giving MONAD more room for complex multi-step tasks like learning new skills (install deps → read docs → test → save skill).
- **Dependency**: Added `python-multipart` for FastAPI file upload support.

## [0.2.5] - 2026-03-11

### Added
- **Experience Hygiene Mechanism**: Failed experiences are now tagged `[FAILED]` and excluded from future reasoning context. Prevents "experience pollution" where wrong conclusions from past failures (e.g., "web_fetch can't handle JS pages") mislead the LLM in subsequent tasks. Successful experiences are tagged `[SUCCESS]`; untagged legacy experiences are loaded normally for backward compatibility.

### Changed
- **Design Philosophy Documentation**: Added "URL-First Principle" and "Experience Hygiene" as formal design principles in README.md, README_zh.md, and CLAUDE.md — elevated from system prompt tweaks to documented architectural decisions.

## [0.2.4] - 2026-03-11

### Added
- **File Output System**: When MONAD generates files (reports, data exports, etc.), they are saved to `~/.monad/output/` and a download link is shown in the web UI's files panel. The web server mounts this directory at `/output/` for browser downloads.
- **MONAD_OUTPUT_DIR**: `python_exec` now injects this variable into the execution namespace. After execution, new files in the output directory are automatically detected and download links are emitted.
- **Simple Markdown Rendering**: MONAD's chat answers now render basic markdown (headers, bold, lists, dividers) instead of raw text.

### Changed
- **Clean Answer Display**: Removed the `═` decorator borders from `Output.result()`. Answers now appear as clean text in the chat panel.
- **System Prompt**: Instructs the LLM to only save files when the user explicitly asks for a report/export, and to use `MONAD_OUTPUT_DIR` for the path.

## [0.2.3] - 2026-03-11

### Fixed
- **URL-First Principle**: Added explicit rule in system prompt — when the user provides a specific URL/domain, MONAD must `web_fetch` that URL directly first, not search for it on Bing. Previously the "search first" principle was over-applied, causing MONAD to detour through Bing even when the target URL was right in the user's request.
- **Reflection Think-Tag Leakage**: LLM `<think>` blocks are now stripped from reflection summaries before saving to the experience file. Previously raw think tokens polluted the knowledge base, wasting context and adding noise.
- **Stale Experience Cleanup**: Removed outdated kexue.fm failure experiences that were misleading the LLM into avoiding direct page access (based on pre-fix web_fetch behavior).

## [0.2.2] - 2026-03-11

### Fixed
- **CSS Selector Fallback**: When a CSS selector matches nothing across all fetch modes, `_auto_fetch` now automatically retries without the selector instead of failing outright. Previously a bad selector (e.g. `main, .content, article` on a site that uses different element names) would cause all three modes to return ~36 chars and give up.

## [0.2.1] - 2026-03-11

### Fixed
- **Reasoner Thought Loop**: Added loop detection (Jaccard similarity) and consecutive-thought counter with escalating prompts to break out of repetitive thinking cycles that previously exhausted all 15 turns.
- **History Context Bloat**: Thoughts stored in history are now capped (400 chars) and total history is trimmed (last 30 entries) to prevent context overflow causing LLM output truncation.
- **System Prompt Tightening**: Thoughts must be concise (1-3 sentences); consecutive thoughts without action are now explicitly forbidden; stronger follow-up prompts guide the LLM toward action.

### Changed
- **Browser Mode Uses System Chrome**: `web_fetch` browser mode now uses `real_chrome=True`, leveraging the user's installed Chrome browser instead of requiring a separate `playwright install chromium` step. This eliminates the most error-prone part of installation.
- **Simplified Installation**: Removed the `playwright install chromium` step from README and all documentation. Users only need `pip install` and a Chrome browser.
- **web_fetch Prompt**: System prompt no longer lists individual modes; tells the LLM to never manually specify `mode`, letting the auto fallback chain handle everything.

## [0.2.0] - 2026-03-10

### Added
- **Web UI**: A modern, two-column browser-based interface (`FastAPI` + `WebSockets`) replaces the default CLI loop. Left column: chat + output files. Right column: real-time log stream.
- **Interactive First-Run Setup**: On first boot, MONAD guides users to configure `Base URL`, `API Key`, and `Model ID` with real-time API connectivity validation before saving to `~/.monad/.env`.
- **Feishu Bot Integration**: `monad --feishu` connects MONAD to a Feishu (Lark) bot via WebSocket long-connection. Usage: `APP_ID=xxx APP_SECRET=yyy monad --feishu`. Requires `pip install monad-core[feishu]`.

### Fixed
- **LLM Parser Hardening**: Added regex-based `<think>` block stripping and `_normalize_parsed()` to handle alternative JSON formats from Minimax models (e.g. `{"action": ...}` instead of `{"type": "action", ...}`).
- **ask_user Chat Display**: Questions from `ask_user` now appear in the frontend chat panel via `[__WS_ASK_USER__]` markers.
- **WebSocket Result Parsing**: Fixed boundary parsing for LLM answers not displaying in the chat dialog.
- **Static Files Packaging**: Ensured `index.html` and `knowledge/*` files are bundled into the PyPI wheel.
- **Dependency Fix**: Pinned `curl_cffi < 0.14.0` to avoid a broken wheel build on macOS arm64.

## [0.1.1] - 2026-03-09

### Added
- Feishu integration (`main_feishu.py`) supporting asynchronous background loop iteration.
- Thread-local buffered output queues allowing step-by-step batched sending mechanics.
- A concise 'records and accumulated_experiences' mechanism rather than full-length text context bloat.

## [0.1.0] - 2026-03-09

### Added
- **4 Core Capabilities (Instincts)**:
    - `python_exec` (HANDS 🤲): Execute Python code for data processing, file I/O, and tool creation.
    - `shell` (VOICE 🗣️): Execute shell commands for system operations.
    - `web_fetch` (EYES 👁️): Perception of the internet with smart mode selection.
    - `ask_user` (DIALOGUE 💬): Interaction with the user for clarification or final results.
- **Smart Web Perception**:
    - `web_fetch` now supports `auto` mode (default), which implements an intelligent fallback chain: `fast` (HTTP/curl_cffi) → `stealth` (Playwright Stealth) → `browser` (Playwright Dynamic).
    - Automatic detection of JavaScript-rendered "empty shells" or anti-bot challenges to trigger escalation to higher modes.
- **Rationality Framework**:
    - **No-Knowledge Axiom**: MONAD relies on execution and perception, not internal training data for factual information.
    - **Search-First Principle**: When encountering technical obstacles (errors, missing libraries, unknown APIs), MONAD automatically searches for solutions before giving up.
    - **Ask-First Nuance**: If the user's initial query is ambiguous, MONAD prioritizes clarification over blind execution.
- **Autonomous Learning**:
    - **Skill Builder**: MONAD can extract successful logic into permanent skill files (`knowledge/skills/`).
    - **Experience Recorder**: Every task execution is reflected upon and recorded in `knowledge/experiences/`.
- **Protocol System**: Standardized handling for unknown tasks, missing parameters, and missing dependencies.
- **Quality Assurance**: Initial unit test suite for core tool reliability.

### Changed
- Refined system prompts for the ReAct reasoner to enforce absolute rationality and search-first behaviors.
- Improved error handling for missing Python libraries with automatic pip/brew installation strategies.

### Technical Details
- **Architecture**: Pure reasoning-based ReAct loop.
- **Persistence**: File-system based knowledge vault (Markdown/YAML). No vector DB, no RAG.
- **Technology**: Python 3.12, Scrapling, Playwright, curl-cffi.
