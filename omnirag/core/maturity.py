"""Adapter maturity level system.

Maturity levels control what optimizations the compiler can apply:
- core: Full optimization (inlining, fusion)
- extended: Limited optimization (no deep fusion)
- experimental: No compilation (runtime only)
"""

from __future__ import annotations

from enum import Enum
from functools import wraps
from typing import Any


class MaturityLevel(str, Enum):
    CORE = "core"
    EXTENDED = "extended"
    EXPERIMENTAL = "experimental"


def maturity_level(level: str | MaturityLevel) -> Any:
    """Decorator to annotate an adapter class with its maturity level."""
    if isinstance(level, str):
        level = MaturityLevel(level)

    def decorator(cls: type) -> type:
        cls._maturity_level = level  # type: ignore[attr-defined]
        return cls

    return decorator


def get_maturity(adapter: Any) -> MaturityLevel:
    """Get the maturity level of an adapter instance or class."""
    cls = adapter if isinstance(adapter, type) else type(adapter)
    return getattr(cls, "_maturity_level", MaturityLevel.EXPERIMENTAL)
