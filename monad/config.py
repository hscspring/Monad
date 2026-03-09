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
    # Copy bundled knowledge
    bundled_knowledge = PACKAGE_DIR / "knowledge"
    if bundled_knowledge.exists():
        shutil.copytree(bundled_knowledge, WORKSPACE_DIR / "knowledge", dirs_exist_ok=True)
    
    # Create default .env
    env_file = WORKSPACE_DIR / ".env"
    env_content = (
        "# MONAD Configuration\n"
        "MONAD_BASE_URL=https://api.qnaigc.com/v1\n"
        "MONAD_API_KEY=\n"
    )
    env_file.write_text(env_content, encoding="utf-8")

load_dotenv(WORKSPACE_DIR / ".env")


@dataclass
class LLMConfig:
    """LLM API configuration."""
    base_url: str = os.getenv("MONAD_BASE_URL", "https://api.qnaigc.com/v1")
    api_key: str = os.getenv("MONAD_API_KEY", "")
    model: str = "minimax/minimax-m2.5"
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
    def cache_path(self) -> Path:
        return self.knowledge_path / "cache"


# Global config instance
CONFIG = MonadConfig()
