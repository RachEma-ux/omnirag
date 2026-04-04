"""Canonical data model for OmniRAG.

All runtimes and adapters normalize their outputs to these Pydantic models.
This ensures interoperability across frameworks.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class Modality(StrEnum):
    """Content modality types."""

    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    CHART = "chart"
    FORMULA = "formula"


class Relation(BaseModel):
    """Relationship between two chunks."""

    source_id: str
    target_id: str
    relation_type: str  # "contains", "references", "caption_of", "part_of"


class OmniChunk(BaseModel):
    """A single chunk of content with optional embedding."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str
    modality: Modality = Modality.TEXT
    embedding: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    relationships: list[Relation] = Field(default_factory=list)


class OmniDocument(BaseModel):
    """A document composed of chunks."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    source: str  # file path, URL, S3 URI
    chunks: list[OmniChunk] = Field(default_factory=list)

    @field_validator("chunks")
    @classmethod
    def validate_unique_chunk_ids(cls, v: list[OmniChunk]) -> list[OmniChunk]:
        ids = [c.id for c in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Chunk IDs must be unique within a document")
        return v


class RetrievalResult(BaseModel):
    """Result of a retrieval operation."""

    query: str
    chunks: list[OmniChunk] = Field(default_factory=list)
    scores: list[float] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_scores_alignment(self) -> RetrievalResult:
        if self.scores and len(self.scores) != len(self.chunks):
            raise ValueError(
                f"scores length ({len(self.scores)}) must match "
                f"chunks length ({len(self.chunks)})"
            )
        return self


class GenerationResult(BaseModel):
    """Result of a generation (LLM) operation."""

    answer: str
    citations: list[str] = Field(default_factory=list)  # chunk IDs
    confidence: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
