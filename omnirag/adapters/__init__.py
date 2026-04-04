"""Adapter ecosystem — pluggable components for RAG pipelines."""

from omnirag.adapters.base import BaseAdapter
from omnirag.adapters.registry import AdapterRegistry, adapter_registry

__all__ = ["BaseAdapter", "AdapterRegistry", "adapter_registry"]
