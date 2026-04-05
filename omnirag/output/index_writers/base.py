"""Base index writer interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from omnirag.intake.models import Chunk
from omnirag.output.embedding import EmbeddingResult


class BaseIndexWriter(ABC):
    """Writes chunks + embeddings to an index store."""

    name: str = "base"

    @abstractmethod
    async def write(self, chunks: list[Chunk], embeddings: list[EmbeddingResult]) -> int:
        """Write chunks to the index. Returns count of successfully written."""
        ...

    @abstractmethod
    async def delete(self, chunk_ids: list[str]) -> int:
        """Delete chunks by ID. Returns count deleted."""
        ...

    @abstractmethod
    async def health(self) -> dict:
        """Return health status of this writer."""
        ...

    @abstractmethod
    async def search(self, query_vector: list[float] | None, query_text: str | None,
                     acl_principals: list[str], top_k: int = 10, filters: dict | None = None) -> list[dict]:
        """Search the index. Returns scored results."""
        ...


class IndexWriterRegistry:
    def __init__(self) -> None:
        self._writers: dict[str, BaseIndexWriter] = {}

    def register(self, writer: BaseIndexWriter) -> None:
        self._writers[writer.name] = writer

    def get(self, name: str) -> BaseIndexWriter | None:
        return self._writers.get(name)

    def all(self) -> list[BaseIndexWriter]:
        return list(self._writers.values())

    def names(self) -> list[str]:
        return list(self._writers.keys())


_registry = IndexWriterRegistry()


def get_writer_registry() -> IndexWriterRegistry:
    return _registry
