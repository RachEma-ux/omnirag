"""Tests for the file loader ingestion adapter."""

import tempfile
from pathlib import Path

from omnirag.adapters.ingestion import FileLoaderAdapter


def test_ingest_single_file():
    adapter = FileLoaderAdapter()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Hello, OmniRAG!")
        f.flush()
        docs = adapter.ingest(f.name)
    assert len(docs) == 1
    assert docs[0].chunks[0].content == "Hello, OmniRAG!"


def test_ingest_directory():
    adapter = FileLoaderAdapter()
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "a.txt").write_text("File A")
        (Path(tmpdir) / "b.md").write_text("File B")
        (Path(tmpdir) / "c.bin").write_bytes(b"\x00\x01")  # non-text, should be skipped
        docs = adapter.ingest(tmpdir)
    assert len(docs) == 2
    contents = {d.chunks[0].content for d in docs}
    assert "File A" in contents
    assert "File B" in contents


def test_ingest_empty_file():
    adapter = FileLoaderAdapter()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("")
        f.flush()
        docs = adapter.ingest(f.name)
    assert len(docs) == 0


def test_ingest_csv_gets_table_modality():
    adapter = FileLoaderAdapter()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("name,age\nAlice,30\n")
        f.flush()
        docs = adapter.ingest(f.name)
    assert len(docs) == 1
    assert docs[0].chunks[0].modality == "table"
