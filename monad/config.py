"""
MONAD Configuration
Global settings for the Personal AGI Core.
"""

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

PACKAGE_DIR = Path(__file__).parent
WORKSPACE_DIR = Path.home() / ".monad"

# Initialize workspace on first run
if not WORKSPACE_DIR.exists():
    WORKSPACE_DIR.mkdir(parents=True)

# Sync bundled knowledge → user workspace
# System-managed dirs: always overwrite (ensures bug fixes reach users)
# User-managed dirs: only copy new files (preserves customizations)
_SYSTEM_MANAGED_DIRS = {"skills", "protocols", "tools"}

knowledge_dir = WORKSPACE_DIR / "knowledge"
bundled_knowledge = PACKAGE_DIR / "knowledge"
if bundled_knowledge.exists():
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

# Create default .env if missing
env_file = WORKSPACE_DIR / ".env"
if not env_file.exists():
    env_content = (
        "# MONAD Configuration\n"
        "MONAD_BASE_URL=https://api.qnaigc.com/v1\n"
        "MONAD_API_KEY=\n"
        "MODEL_ID=minimax/minimax-m2.5\n"
    )
    env_file.write_text(env_content, encoding="utf-8")

load_dotenv(WORKSPACE_DIR / ".env")


@dataclass
class LLMConfig:
    """LLM API configuration."""
    base_url: str = os.getenv("MONAD_BASE_URL", "https://api.qnaigc.com/v1")
    api_key: str = os.getenv("MONAD_API_KEY", "")
    model: str = os.getenv("MODEL_ID", "minimax/minimax-m2.5")
    temperature: float = 0.3
    max_tokens: int = 4096


@dataclass
class MonadConfig:
    """Top-level MONAD configuration."""
    # Root directory of the MONAD workspace
    root_dir: Path = field(default_factory=lambda: WORKSPACE_DIR)

    # LLM settings
    llm: LLMConfig = field(default_factory=LLMConfig)

    # Knowledge paths (relative to root_dir)
    knowledge_dir: str = "knowledge"

    # Logging
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
    def browser_path(self) -> Path:
        return self.root_dir / "browser"


# Global config instance
CONFIG = MonadConfig()

# Ensure browser state directory exists
CONFIG.browser_path.mkdir(parents=True, exist_ok=True)
