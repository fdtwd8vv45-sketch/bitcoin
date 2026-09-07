"""Use Strands @tool when installed; otherwise keep a no-op decorator.

The local CLI and unit tests should run with the Python standard library.
The deployed AgentCore runtime still uses strands-agents.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

try:
    from strands import tool as tool
except ImportError:

    def tool(func: F | None = None, **_kwargs: Any) -> F | Callable[[F], F]:
        if func is None:
            return lambda inner: inner
        return func
