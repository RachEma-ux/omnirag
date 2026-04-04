"""Base adapter interface.

All OmniRAG adapters must inherit from BaseAdapter and implement
the relevant methods for their category (ingestion, embedding,
retrieval, generation, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from omnirag.core.models import GenerationResult, OmniChunk, OmniDocument, RetrievalResult


class BaseAdapter(ABC):
    """Abstract base class for all OmniRAG adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique adapter name."""

    @property
    @abstractmethod
    def category(self) -> str:
        """Adapter category: ingestion, chunking, embedding, retrieval, reranking, generation."""

    def ingest(self, source: Any, **kwargs: Any) -> list[OmniDocument]:
        """Ingest content from a source into OmniDocuments."""
        raise NotImplementedError(f"{self.name} does not support ingestion")

    def chunk(self, documents: list[OmniDocument], **kwargs: Any) -> list[OmniChunk]:
        """Split documents into chunks."""
        raise NotImplementedError(f"{self.name} does not support chunking")

    def embed(self, chunks: list[OmniChunk], **kwargs: Any) -> list[OmniChunk]:
        """Generate embeddings for chunks (modifies chunks in place, returns them)."""
        raise NotImplementedError(f"{self.name} does not support embedding")

    def store(self, chunks: list[OmniChunk], **kwargs: Any) -> None:
        """Store chunks in a vector database."""
        raise NotImplementedError(f"{self.name} does not support storage")

    def retrieve(self, query: str, **kwargs: Any) -> RetrievalResult:
        """Retrieve relevant chunks for a query."""
        raise NotImplementedError(f"{self.name} does not support retrieval")

    def rerank(self, result: RetrievalResult, **kwargs: Any) -> RetrievalResult:
        """Rerank a retrieval result."""
        raise NotImplementedError(f"{self.name} does not support reranking")

    def generate(self, query: str, context: list[OmniChunk], **kwargs: Any) -> GenerationResult:
        """Generate an answer given query and context chunks."""
        raise NotImplementedError(f"{self.name} does not support generation")
