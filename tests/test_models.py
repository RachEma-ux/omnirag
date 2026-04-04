"""Tests for canonical data models."""

import pytest
from pydantic import ValidationError

from omnirag.core.models import (
    GenerationResult,
    Modality,
    OmniChunk,
    OmniDocument,
    Relation,
    RetrievalResult,
)


def test_omni_chunk_defaults():
    chunk = OmniChunk(content="hello world")
    assert chunk.modality == Modality.TEXT
    assert chunk.embedding is None
    assert chunk.metadata == {}
    assert chunk.relationships == []
    assert chunk.id  # auto-generated UUID


def test_omni_chunk_with_embedding():
    chunk = OmniChunk(content="test", embedding=[0.1, 0.2, 0.3])
    assert chunk.embedding == [0.1, 0.2, 0.3]


def test_omni_document_unique_chunk_ids():
    c1 = OmniChunk(id="a", content="first")
    c2 = OmniChunk(id="b", content="second")
    doc = OmniDocument(source="test.pdf", chunks=[c1, c2])
    assert len(doc.chunks) == 2


def test_omni_document_duplicate_chunk_ids_raises():
    c1 = OmniChunk(id="same", content="first")
    c2 = OmniChunk(id="same", content="second")
    with pytest.raises(ValidationError, match="unique"):
        OmniDocument(source="test.pdf", chunks=[c1, c2])


def test_retrieval_result_scores_alignment():
    chunks = [OmniChunk(content="a"), OmniChunk(content="b")]
    result = RetrievalResult(query="test", chunks=chunks, scores=[0.9, 0.8])
    assert len(result.scores) == len(result.chunks)


def test_retrieval_result_misaligned_scores_raises():
    chunks = [OmniChunk(content="a"), OmniChunk(content="b")]
    with pytest.raises(ValidationError, match="scores length"):
        RetrievalResult(query="test", chunks=chunks, scores=[0.9])


def test_generation_result_confidence_bounds():
    result = GenerationResult(answer="test", confidence=0.95)
    assert result.confidence == 0.95

    with pytest.raises(ValidationError):
        GenerationResult(answer="test", confidence=1.5)

    with pytest.raises(ValidationError):
        GenerationResult(answer="test", confidence=-0.1)


def test_relation():
    rel = Relation(source_id="a", target_id="b", relation_type="contains")
    assert rel.relation_type == "contains"


def test_modality_values():
    assert Modality.TEXT == "text"
    assert Modality.TABLE == "table"
    assert Modality.IMAGE == "image"
    assert Modality.CHART == "chart"
    assert Modality.FORMULA == "formula"
