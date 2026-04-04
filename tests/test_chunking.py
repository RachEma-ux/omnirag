"""Tests for the recursive chunking adapter."""

from omnirag.adapters.chunking import RecursiveChunkerAdapter
from omnirag.core.models import OmniChunk, OmniDocument


def test_chunk_small_document():
    """Document smaller than chunk_size should return as-is."""
    adapter = RecursiveChunkerAdapter()
    doc = OmniDocument(source="test.txt", chunks=[OmniChunk(content="Short text.")])
    result = adapter.chunk([doc], chunk_size=512)
    assert len(result) == 1
    assert result[0].content == "Short text."


def test_chunk_large_document():
    """Document larger than chunk_size should be split."""
    adapter = RecursiveChunkerAdapter()
    content = "Hello world. " * 100  # ~1300 chars
    doc = OmniDocument(source="test.txt", chunks=[OmniChunk(content=content)])
    result = adapter.chunk([doc], chunk_size=200, overlap=20)
    assert len(result) > 1
    for chunk in result:
        assert len(chunk.content) <= 250  # allow some margin for split boundaries


def test_chunk_preserves_metadata():
    """Chunks should carry source metadata."""
    adapter = RecursiveChunkerAdapter()
    doc = OmniDocument(source="data/file.md", chunks=[
        OmniChunk(content="A" * 600, metadata={"page": 1})
    ])
    result = adapter.chunk([doc], chunk_size=200)
    assert len(result) > 1
    for chunk in result:
        assert chunk.metadata["page"] == 1
        assert chunk.metadata["doc_source"] == "data/file.md"


def test_chunk_empty_document():
    """Empty document should produce no chunks."""
    adapter = RecursiveChunkerAdapter()
    doc = OmniDocument(source="empty.txt", chunks=[OmniChunk(content="")])
    result = adapter.chunk([doc], chunk_size=512)
    assert len(result) == 0
