"""Shared typing helpers for MONAD."""

from typing import Protocol


class ToolFn(Protocol):
    """Callable signature for built-in tool run functions."""

    def __call__(self, **kwargs) -> str: ...
