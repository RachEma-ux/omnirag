"""Adapter registry — central catalog of adapters with maturity tracking."""

from __future__ import annotations

import warnings
from typing import Any

from omnirag.adapters.base import BaseAdapter
from omnirag.core.exceptions import AdapterMaturityWarning, AdapterNotFoundError
from omnirag.core.maturity import MaturityLevel, get_maturity


class AdapterRegistry:
    """Central registry for all OmniRAG adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, dict[str, Any]] = {}

    def register(self, name: str, adapter_class: type[BaseAdapter]) -> None:
        """Register an adapter class."""
        maturity = get_maturity(adapter_class)
        self._adapters[name] = {
            "class": adapter_class,
            "maturity": maturity,
        }

    def get(self, name: str, compiled_mode: bool = False) -> BaseAdapter:
        """Get an adapter instance by name.

        If compiled_mode is True and the adapter is not core maturity,
        a warning is issued.
        """
        entry = self._adapters.get(name)
        if entry is None:
            raise AdapterNotFoundError(
                f"Adapter '{name}' not found. "
                f"Available: {list(self._adapters.keys())}"
            )
        if compiled_mode and entry["maturity"] != MaturityLevel.CORE:
            warnings.warn(
                f"Adapter '{name}' has maturity '{entry['maturity'].value}' — "
                f"compiled mode optimizations may be limited.",
                AdapterMaturityWarning,
                stacklevel=2,
            )
        return entry["class"]()

    def list_adapters(self) -> list[dict[str, str]]:
        """List all registered adapters with their maturity levels."""
        return [
            {"name": name, "maturity": info["maturity"].value}
            for name, info in self._adapters.items()
        ]

    def has(self, name: str) -> bool:
        """Check if an adapter is registered."""
        return name in self._adapters


# Global singleton registry
adapter_registry = AdapterRegistry()
