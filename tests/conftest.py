"""Shared pytest fixtures and configuration."""

import pytest

from monad.config import init_workspace


@pytest.fixture(scope="session", autouse=True)
def _init_monad_workspace() -> None:
    """Ensure workspace layout and .env exist before any test imports mutate CONFIG."""
    init_workspace()
