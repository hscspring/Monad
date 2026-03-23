"""
MONAD Configuration
Global settings and dataclasses for the Personal AGI Core.

Importing this module does not touch the filesystem. Call init_workspace() from
entry points before using paths, logs, or env-populated LLM settings.
"""

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# ── Package / Workspace Paths ───────────────────────────────────
PACKAGE_DIR = Path(__file__).parent
WORKSPACE_DIR = Path.home() / ".monad"

# ── Version (single source of truth) ────────────────────────────
VERSION = "1.0.0"

# ── Default API Settings ────────────────────────────────────────
DEFAULT_BASE_URL = "https://api.qnaigc.com/v1"
DEFAULT_MODEL = "minimax/minimax-m2.5"

# ── Timeouts (seconds) ──────────────────────────────────────────
TIMEOUT_LLM_CONNECT = 15.0
TIMEOUT_LLM_READ = 120.0
TIMEOUT_LLM_WRITE = 15.0
TIMEOUT_LLM_POOL = 15.0

# ── LLM retry (transient failures: 5xx, timeout, connection) ────
LLM_MAX_RETRIES = 3
LLM_RETRY_BASE_DELAY = 2.0
LLM_RETRY_MAX_DELAY = 30.0
TIMEOUT_SHELL = 120
TIMEOUT_PIP_INSTALL = 120
TIMEOUT_SUBPROCESS = 5

# ── Truncation lengths (characters) ─────────────────────────────
TRUNCATE_SHORT = 100
TRUNCATE_MEDIUM = 200
TRUNCATE_LONG = 500
TRUNCATE_THOUGHT = 400
TRUNCATE_CONTENT = 5000

# ── Reasoner limits ─────────────────────────────────────────────
MAX_TURNS = 30
HISTORY_CAP = 30
THOUGHT_SOFT_LIMIT = 2
THOUGHT_HARD_LIMIT = 4
ASK_USER_LIMIT = 2
MAX_ANSWER_REJECTIONS = 3
SIMILARITY_THRESHOLD = 0.6

# ── Experience settings ─────────────────────────────────────────
PROMOTE_THRESHOLD = 3
MAX_EXPERIENCES = 10
RECENT_FALLBACK = 3

# ── Proactive scheduler ─────────────────────────────────────────
IDLE_THRESHOLD_MINUTES = 30
PROACTIVE_CHECK_INTERVAL = 60  # seconds
DAILY_LEARNING_BUDGET = 5

# ── Desktop control ─────────────────────────────────────────────
MAX_OCR_ELEMENTS = 50
MIN_OCR_TEXT_LEN = 2
OCR_CONFIDENCE_THRESHOLD = 0.5
WINDOW_FILTER_MARGIN = 60

# ── Web fetch ────────────────────────────────────────────────────
MIN_CONTENT_LEN = 200
CHALLENGE_CONTENT_THRESHOLD = 500
CHALLENGE_MARKERS = (
    "please solve the challenge",
    "checking your browser",
    "just a moment",
    "enable javascript",
    "you need to enable javascript",
)
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# ── UI ───────────────────────────────────────────────────────────
DIVIDER_WIDTH = 50
CODE_DIVIDER_WIDTH = 40
QUIT_COMMANDS = frozenset({"quit", "exit", "bye", "q"})

# ── Launch mode (set by main.py at startup) ───────────────────
LAUNCH_MODE: str = "cli"

# ── Web server (env overrides) ─────────────────────────────────
DEFAULT_WEB_HOST = "127.0.0.1"
DEFAULT_WEB_PORT = 8000
DEFAULT_WEB_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB

# ── WebSocket protocol markers ──────────────────────────────────
WS_RESULT_START = "[__WS_RESULT_START__]"
WS_RESULT_END = "[__WS_RESULT_END__]"
WS_ASK_USER_START = "[__WS_ASK_USER__]"
WS_ASK_USER_END = "[__WS_ASK_USER_END__]"
WS_FILE_START = "[__WS_FILE__]"
WS_FILE_END = "[__WS_FILE_END__]"


# ── Knowledge sync policy ─────────────────────────────────────────
_SYSTEM_MANAGED_DIRS = frozenset({"skills", "protocols", "tools"})


# ── Utility ──────────────────────────────────────────────────────

def truncate(text: str, max_len: int = TRUNCATE_LONG) -> str:
    """Truncate text to max_len characters with ellipsis."""
    if not text or len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _refresh_llm_from_env() -> None:
    """Update global CONFIG.llm from environment (after load_dotenv)."""
    CONFIG.llm.base_url = os.getenv("MONAD_BASE_URL", DEFAULT_BASE_URL)
    CONFIG.llm.api_key = os.getenv("MONAD_API_KEY", "")
    CONFIG.llm.model = os.getenv("MODEL_ID", DEFAULT_MODEL)


def _sync_bundled_knowledge(workspace_root: Path) -> None:
    """Sync bundled package knowledge into the user workspace."""
    knowledge_dir = workspace_root / "knowledge"
    bundled_knowledge = PACKAGE_DIR / "knowledge"
    if not bundled_knowledge.exists():
        return
    if not knowledge_dir.exists():
        shutil.copytree(bundled_knowledge, knowledge_dir)
    else:
        for src_file in bundled_knowledge.rglob("*"):
            if not src_file.is_file():
                continue
            rel = src_file.relative_to(bundled_knowledge)
            dest = knowledge_dir / rel
            top_dir = rel.parts[0] if rel.parts else ""
            if dest.exists() and top_dir not in _SYSTEM_MANAGED_DIRS:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dest)

    _sync_bundled_schedules(workspace_root)


def _sync_bundled_schedules(workspace_root: Path) -> None:
    """Copy bundled schedule YAML files to ~/.monad/schedules/ (new files only)."""
    bundled = PACKAGE_DIR / "knowledge" / "schedules"
    target = workspace_root / "schedules"
    if not bundled.exists():
        return
    target.mkdir(parents=True, exist_ok=True)
    for src in bundled.glob("*.yaml"):
        dest = target / src.name
        if not dest.exists():
            shutil.copy2(src, dest)


def _ensure_default_env(workspace_root: Path) -> None:
    env_file = workspace_root / ".env"
    if not env_file.exists():
        env_content = (
            "# MONAD Configuration\n"
            f"MONAD_BASE_URL={DEFAULT_BASE_URL}\n"
            "MONAD_API_KEY=\n"
            f"MODEL_ID={DEFAULT_MODEL}\n"
        )
        env_file.write_text(env_content, encoding="utf-8")


def _configure_loguru(workspace_root: Path, log_level: str) -> None:
    from loguru import logger

    _log_dir = workspace_root / "logs"
    _log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(
        _log_dir / "monad.log",
        rotation="10 MB",
        retention="7 days",
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        encoding="utf-8",
    )


def init_workspace(*, configure_logging: bool = True) -> None:
    """Create workspace layout, sync knowledge, load .env, refresh LLM config.

    Call this once from process entry points (CLI, web, Feishu, self-test).
    Safe to call multiple times (idempotent for dirs and sync).
    """
    ws = CONFIG.root_dir
    if not ws.exists():
        ws.mkdir(parents=True)

    _sync_bundled_knowledge(ws)
    _ensure_default_env(ws)
    load_dotenv(ws / ".env")
    _refresh_llm_from_env()

    for _dir in (CONFIG.browser_path, CONFIG.output_path, CONFIG.input_path,
                  CONFIG.schedules_path):
        _dir.mkdir(parents=True, exist_ok=True)

    if configure_logging:
        _configure_loguru(ws, CONFIG.log_level)


# ── Dataclass Configs ────────────────────────────────────────────

@dataclass
class LLMConfig:
    """LLM API configuration (defaults from env at instance creation)."""
    base_url: str = field(
        default_factory=lambda: os.getenv("MONAD_BASE_URL", DEFAULT_BASE_URL)
    )
    api_key: str = field(default_factory=lambda: os.getenv("MONAD_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("MODEL_ID", DEFAULT_MODEL))
    temperature: float = 0.3
    max_tokens: int = 4096


@dataclass
class MonadConfig:
    """Top-level MONAD configuration."""
    root_dir: Path = field(default_factory=lambda: WORKSPACE_DIR)
    llm: LLMConfig = field(default_factory=LLMConfig)
    knowledge_dir: str = "knowledge"
    log_level: str = "INFO"

    @property
    def knowledge_path(self) -> Path:
        return self.root_dir / self.knowledge_dir

    @property
    def axioms_path(self) -> Path:
        return self.knowledge_path / "axioms"

    @property
    def environment_path(self) -> Path:
        return self.knowledge_path / "environment"

    @property
    def tools_docs_path(self) -> Path:
        return self.knowledge_path / "tools"

    @property
    def skills_path(self) -> Path:
        return self.knowledge_path / "skills"

    @property
    def protocols_path(self) -> Path:
        return self.knowledge_path / "protocols"

    @property
    def user_path(self) -> Path:
        return self.knowledge_path / "user"

    @property
    def experiences_path(self) -> Path:
        return self.knowledge_path / "experiences"

    @property
    def records_path(self) -> Path:
        return self.knowledge_path / "records"

    @property
    def cache_path(self) -> Path:
        return self.knowledge_path / "cache"

    @property
    def schedules_path(self) -> Path:
        return self.root_dir / "schedules"

    @property
    def browser_path(self) -> Path:
        return self.root_dir / "browser"

    @property
    def output_path(self) -> Path:
        return self.root_dir / "output"

    @property
    def input_path(self) -> Path:
        return self.root_dir / "input"

    def skill_dir(self, name: str) -> Path:
        """Directory for a named skill under the skills tree."""
        return self.skills_path / name

    @property
    def web_host(self) -> str:
        return os.getenv("WEB_HOST", DEFAULT_WEB_HOST)

    @property
    def web_port(self) -> int:
        raw = os.getenv("WEB_PORT")
        if raw is None or raw == "":
            return DEFAULT_WEB_PORT
        try:
            return int(raw)
        except ValueError:
            return DEFAULT_WEB_PORT

    @property
    def web_max_upload_bytes(self) -> int:
        raw = os.getenv("WEB_MAX_UPLOAD_BYTES")
        if raw is None or raw == "":
            return DEFAULT_WEB_MAX_UPLOAD_BYTES
        try:
            return int(raw)
        except ValueError:
            return DEFAULT_WEB_MAX_UPLOAD_BYTES


# ── Global Config Instance ──────────────────────────────────────
CONFIG = MonadConfig()
