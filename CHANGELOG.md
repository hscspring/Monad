# Changelog

All notable changes to this project will be documented in this file.

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
