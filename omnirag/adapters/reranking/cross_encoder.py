"""Cross-encoder reranking adapter.

Uses sentence-transformers CrossEncoder models to rerank retrieval results.
Requires: pip install omnirag[huggingface]
"""

from __future__ import annotations

from typing import Any

from omnirag.adapters.base import BaseAdapter
from omnirag.core.maturity import maturity_level
from omnirag.core.models import RetrievalResult


@maturity_level("core")
class CrossEncoderRerankAdapter(BaseAdapter):
    """Rerank retrieval results using a cross-encoder model."""

    def __init__(self) -> None:
        self._model: Any = None
        self._model_name: str = ""

    @property
    def name(self) -> str:
        return "cross_encoder"

    @property
    def category(self) -> str:
        return "reranking"

    def _load_model(self, model_name: str) -> Any:
        if self._model is None or self._model_name != model_name:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as e:
                raise ImportError(
                    "sentence-transformers is required. "
                    "Install with: pip install omnirag[huggingface]"
                ) from e
            self._model = CrossEncoder(model_name)
            self._model_name = model_name
        return self._model

    def rerank(
        self, result: RetrievalResult, **kwargs: Any
    ) -> RetrievalResult:
        """Rerank chunks using cross-encoder scores.

        Params:
            model: Cross-encoder model name
                   (default: 'cross-encoder/ms-marco-MiniLM-L-6-v2').
            top_k: Return top K after reranking (default: all).
        """
        model_name = kwargs.get(
            "model", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        top_k: int = kwargs.get("top_k", len(result.chunks))

        if not result.chunks:
            return result

        model = self._load_model(model_name)

        pairs = [[result.query, c.content] for c in result.chunks]
        scores = model.predict(pairs).tolist()

        ranked = sorted(
            zip(result.chunks, scores, strict=False),
            key=lambda x: x[1],
            reverse=True,
        )[:top_k]

        return RetrievalResult(
            query=result.query,
            chunks=[c for c, _ in ranked],
            scores=[s for _, s in ranked],
            provenance={
                **result.provenance,
                "reranker": self.name,
                "reranker_model": model_name,
            },
        )
