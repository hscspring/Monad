"""
MONAD Configuration
Global settings for the Personal AGI Core.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LLMConfig:
    """LLM API configuration."""
    base_url: str = "https://api.qnaigc.com/v1"
    api_key: str = "sk-ef253f991b06149c04e15882cbb42da6f204a378534a36d51af726da5028f750"
    model: str = "minimax/minimax-m2.5"
    temperature: float = 0.3
    max_tokens: int = 4096


@dataclass
class MonadConfig:
    """Top-level MONAD configuration."""
    # Root directory of the MONAD project
    root_dir: Path = field(default_factory=lambda: Path(__file__).parent)

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
