"""Tests for adapter registry."""

import warnings

import pytest

from omnirag.adapters.base import BaseAdapter
from omnirag.adapters.memory import MemoryVectorAdapter
from omnirag.adapters.registry import AdapterRegistry
from omnirag.core.exceptions import AdapterMaturityWarning, AdapterNotFoundError
from omnirag.core.maturity import MaturityLevel, get_maturity, maturity_level


def test_register_and_get():
    registry = AdapterRegistry()
    registry.register("memory", MemoryVectorAdapter)
    adapter = registry.get("memory")
    assert isinstance(adapter, MemoryVectorAdapter)


def test_get_not_found():
    registry = AdapterRegistry()
    with pytest.raises(AdapterNotFoundError, match="not_real"):
        registry.get("not_real")


def test_has():
    registry = AdapterRegistry()
    registry.register("memory", MemoryVectorAdapter)
    assert registry.has("memory")
    assert not registry.has("nonexistent")


def test_list_adapters():
    registry = AdapterRegistry()
    registry.register("memory", MemoryVectorAdapter)
    adapters = registry.list_adapters()
    assert len(adapters) == 1
    assert adapters[0]["name"] == "memory"
    assert adapters[0]["maturity"] == "core"


def test_maturity_level_decorator():
    @maturity_level("experimental")
    class TestAdapter(BaseAdapter):
        @property
        def name(self) -> str:
            return "test"

        @property
        def category(self) -> str:
            return "test"

    assert get_maturity(TestAdapter) == MaturityLevel.EXPERIMENTAL
    assert get_maturity(TestAdapter()) == MaturityLevel.EXPERIMENTAL


def test_compiled_mode_warning_for_non_core():
    @maturity_level("experimental")
    class ExpAdapter(BaseAdapter):
        @property
        def name(self) -> str:
            return "exp"

        @property
        def category(self) -> str:
            return "test"

    registry = AdapterRegistry()
    registry.register("exp", ExpAdapter)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        registry.get("exp", compiled_mode=True)
        assert len(w) == 1
        assert issubclass(w[0].category, AdapterMaturityWarning)
