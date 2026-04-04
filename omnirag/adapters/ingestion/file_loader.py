"""File loader ingestion adapter.

Loads text files from a directory into OmniDocuments.
Supports: .txt, .md, .py, .json, .csv, .html, .yaml, .yml
No external dependencies required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from omnirag.adapters.base import BaseAdapter
from omnirag.core.maturity import maturity_level
from omnirag.core.models import Modality, OmniChunk, OmniDocument


_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".csv",
    ".html", ".htm", ".xml", ".yaml", ".yml", ".toml",
    ".rst", ".cfg", ".ini", ".sh", ".bash", ".sql",
}


@maturity_level("core")
class FileLoaderAdapter(BaseAdapter):
    """Load text files from a directory into OmniDocuments."""

    @property
    def name(self) -> str:
        return "file_loader"

    @property
    def category(self) -> str:
        return "ingestion"

    def ingest(self, source: Any, **kwargs: Any) -> list[OmniDocument]:
        """Ingest files from a directory.

        Params:
            source: Directory path or file path.
            glob_pattern: Glob pattern for file matching (default: '*').
            recursive: Whether to search recursively (default: True).
            encoding: File encoding (default: 'utf-8').
        """
        glob_pattern: str = kwargs.get("glob", kwargs.get("glob_pattern", "*"))
        recursive: bool = kwargs.get("recursive", True)
        encoding: str = kwargs.get("encoding", "utf-8")

        source_path = Path(str(source))
        documents: list[OmniDocument] = []

        if source_path.is_file():
            doc = self._load_file(source_path, encoding)
            if doc:
                documents.append(doc)
        elif source_path.is_dir():
            pattern = f"**/{glob_pattern}" if recursive else glob_pattern
            for filepath in sorted(source_path.glob(pattern)):
                if filepath.is_file() and filepath.suffix.lower() in _TEXT_EXTENSIONS:
                    doc = self._load_file(filepath, encoding)
                    if doc:
                        documents.append(doc)

        return documents

    def _load_file(self, filepath: Path, encoding: str) -> OmniDocument | None:
        """Load a single file into an OmniDocument."""
        try:
            content = filepath.read_text(encoding=encoding)
        except (UnicodeDecodeError, PermissionError):
            return None

        if not content.strip():
            return None

        modality = Modality.TABLE if filepath.suffix == ".csv" else Modality.TEXT

        chunk = OmniChunk(
            content=content,
            modality=modality,
            metadata={
                "source_file": str(filepath),
                "file_name": filepath.name,
                "file_size": filepath.stat().st_size,
                "extension": filepath.suffix,
            },
        )

        return OmniDocument(
            source=str(filepath),
            chunks=[chunk],
        )
