# Changelog

All notable changes to this project will be documented in this file.

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
