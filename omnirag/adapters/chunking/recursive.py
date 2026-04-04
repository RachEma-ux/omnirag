"""Recursive character text splitter adapter.

Splits text into chunks by recursively trying separators,
keeping chunks under the specified size with optional overlap.
"""

from __future__ import annotations

from typing import Any

from omnirag.adapters.base import BaseAdapter
from omnirag.core.maturity import maturity_level
from omnirag.core.models import OmniChunk, OmniDocument


_DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


@maturity_level("core")
class RecursiveChunkerAdapter(BaseAdapter):
    """Recursive character text splitter — generic chunking for any text."""

    @property
    def name(self) -> str:
        return "recursive_splitter"

    @property
    def category(self) -> str:
        return "chunking"

    def chunk(self, documents: list[OmniDocument], **kwargs: Any) -> list[OmniChunk]:
        """Split documents into chunks.

        Params:
            chunk_size: Max characters per chunk (default 512).
            overlap: Number of overlapping characters (default 50).
            separators: List of separator strings to try (default: paragraph, line, sentence, word).
        """
        chunk_size: int = kwargs.get("chunk_size", 512)
        overlap: int = kwargs.get("overlap", 50)
        separators: list[str] = kwargs.get("separators", _DEFAULT_SEPARATORS)

        all_chunks: list[OmniChunk] = []

        for doc in documents:
            for source_chunk in doc.chunks:
                splits = self._recursive_split(
                    source_chunk.content, chunk_size, overlap, separators
                )
                for i, text in enumerate(splits):
                    all_chunks.append(
                        OmniChunk(
                            content=text,
                            modality=source_chunk.modality,
                            metadata={
                                **source_chunk.metadata,
                                "source_chunk_id": source_chunk.id,
                                "chunk_index": i,
                                "doc_source": doc.source,
                            },
                        )
                    )

        return all_chunks

    def _recursive_split(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
        separators: list[str],
    ) -> list[str]:
        """Recursively split text using the first separator that produces sub-chunks."""
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

        for sep in separators:
            if sep == "":
                # Last resort: split by character
                return self._split_by_size(text, chunk_size, overlap)
            if sep in text:
                parts = text.split(sep)
                return self._merge_parts(parts, sep, chunk_size, overlap, separators)

        return self._split_by_size(text, chunk_size, overlap)

    def _merge_parts(
        self,
        parts: list[str],
        separator: str,
        chunk_size: int,
        overlap: int,
        separators: list[str],
    ) -> list[str]:
        """Merge small parts into chunks up to chunk_size."""
        chunks: list[str] = []
        current = ""

        for part in parts:
            candidate = current + separator + part if current else part

            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current.strip())
                # If this single part exceeds chunk_size, recurse with next separator
                if len(part) > chunk_size:
                    idx = separators.index(separator) + 1 if separator in separators else 0
                    sub_sep = separators[idx:] if idx < len(separators) else [""]
                    chunks.extend(self._recursive_split(part, chunk_size, overlap, sub_sep))
                    current = ""
                else:
                    # Start overlap from the end of the previous chunk
                    if overlap > 0 and chunks:
                        tail = chunks[-1][-overlap:]
                        current = tail + separator + part
                    else:
                        current = part

        if current and current.strip():
            chunks.append(current.strip())

        return chunks

    def _split_by_size(self, text: str, chunk_size: int, overlap: int) -> list[str]:
        """Fallback: split by raw character count with overlap."""
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(chunk_text)
            start += chunk_size - overlap
        return chunks
