"""Register default adapters in the global registry."""

from __future__ import annotations

from omnirag.adapters.chunking import RecursiveChunkerAdapter
from omnirag.adapters.ingestion import FileLoaderAdapter
from omnirag.adapters.memory import MemoryVectorAdapter
from omnirag.adapters.registry import adapter_registry


def register_defaults() -> None:
    """Register all built-in adapters."""
    adapter_registry.register("memory", MemoryVectorAdapter)
    adapter_registry.register("file_loader", FileLoaderAdapter)
    adapter_registry.register("recursive_splitter", RecursiveChunkerAdapter)

    # Optional adapters — only register if dependencies are available
    try:
        from omnirag.adapters.embedding import HuggingFaceEmbeddingAdapter
        adapter_registry.register("huggingface", HuggingFaceEmbeddingAdapter)
    except ImportError:
        pass

    try:
        from omnirag.adapters.vectordb import QdrantAdapter
        adapter_registry.register("qdrant", QdrantAdapter)
    except ImportError:
        pass

    try:
        from omnirag.adapters.generation import OpenAIGenerationAdapter
        adapter_registry.register("openai_gen", OpenAIGenerationAdapter)
    except ImportError:
        pass
