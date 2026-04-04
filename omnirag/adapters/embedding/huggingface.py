"""Hugging Face sentence-transformers embedding adapter.

Requires: pip install omnirag[huggingface]
"""

from __future__ import annotations

from typing import Any

from omnirag.adapters.base import BaseAdapter
from omnirag.core.maturity import maturity_level
from omnirag.core.models import OmniChunk


@maturity_level("core")
class HuggingFaceEmbeddingAdapter(BaseAdapter):
    """Generate embeddings using Hugging Face sentence-transformers."""

    def __init__(self) -> None:
        self._model: Any = None
        self._model_name: str = ""

    @property
    def name(self) -> str:
        return "huggingface"

    @property
    def category(self) -> str:
        return "embedding"

    def _load_model(self, model_name: str) -> Any:
        """Lazy-load the sentence-transformers model."""
        if self._model is None or self._model_name != model_name:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise ImportError(
                    "sentence-transformers is required. "
                    "Install with: pip install omnirag[huggingface]"
                ) from e
            self._model = SentenceTransformer(model_name)
            self._model_name = model_name
        return self._model

    def embed(self, chunks: list[OmniChunk], **kwargs: Any) -> list[OmniChunk]:
        """Generate embeddings for chunks.

        Params:
            model: Model name (default: 'all-MiniLM-L6-v2').
            batch_size: Batch size for encoding (default: 32).
            device: Device to use ('cpu', 'cuda', default: None = auto).
        """
        model_name: str = kwargs.get("model", "all-MiniLM-L6-v2")
        batch_size: int = kwargs.get("batch_size", 32)
        device: str | None = kwargs.get("device")

        model = self._load_model(model_name)
        if device:
            model = model.to(device)

        texts = [c.content for c in chunks]
        embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=False)

        for chunk, emb in zip(chunks, embeddings, strict=False):
            chunk.embedding = emb.tolist()

        return chunks
