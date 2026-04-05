"""Chunkers per semantic type — the most important RAG rule: chunk by meaning."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from omnirag.intake.models import CanonicalDocument, Chunk, SemanticType


class BaseChunker(ABC):
    """Splits a CanonicalDocument into ordered Chunks."""
    name: str = "base"

    @abstractmethod
    def chunk(self, doc: CanonicalDocument) -> list[Chunk]:
        ...

    def _make_chunk(self, doc: CanonicalDocument, text: str, order: int,
                    section_path: list[str] | None = None, chunk_type: str | None = None) -> Chunk:
        return Chunk(
            document_id=doc.id,
            text=text,
            order=order,
            section_path=section_path or [],
            metadata={"semantic_type": doc.semantic_type.value},
            acl_filter_ref=None,
            chunk_type=chunk_type,
        )


class DocumentChunker(BaseChunker):
    """Recursive text splitter on headings (markdown H1-H6). Target: 512 tokens, 10% overlap."""
    name = "document"

    def __init__(self, chunk_size: int = 512, overlap_pct: float = 0.1) -> None:
        self.chunk_size = chunk_size
        self.overlap = int(chunk_size * overlap_pct)

    def chunk(self, doc: CanonicalDocument) -> list[Chunk]:
        # Split by headings first
        sections = re.split(r'(?m)^(#{1,6}\s+.+)$', doc.body)
        chunks: list[Chunk] = []
        current_path: list[str] = []
        order = 0

        buffer = ""
        for part in sections:
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', part.strip())
            if heading_match:
                # Flush buffer
                if buffer.strip():
                    for c in self._split_text(buffer.strip(), order, current_path, doc):
                        chunks.append(c)
                        order += 1
                    buffer = ""
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                current_path = current_path[:level - 1] + [title]
                buffer += part + "\n"
            else:
                buffer += part

        if buffer.strip():
            for c in self._split_text(buffer.strip(), order, current_path, doc):
                chunks.append(c)
                order += 1

        return chunks if chunks else [self._make_chunk(doc, doc.body, 0, chunk_type="full_document")]

    def _split_text(self, text: str, start_order: int, path: list[str], doc: CanonicalDocument) -> list[Chunk]:
        words = text.split()
        if len(words) <= self.chunk_size:
            return [self._make_chunk(doc, text, start_order, path, "heading_section")]

        result = []
        i = 0
        order = start_order
        while i < len(words):
            end = min(i + self.chunk_size, len(words))
            chunk_text = " ".join(words[i:end])
            result.append(self._make_chunk(doc, chunk_text, order, path, "heading_section"))
            order += 1
            i = end - self.overlap if end < len(words) else end
        return result


class TableChunker(BaseChunker):
    """Row-group splitter: group rows into chunks (50 rows per chunk)."""
    name = "table"

    def __init__(self, rows_per_chunk: int = 50) -> None:
        self.rows_per_chunk = rows_per_chunk

    def chunk(self, doc: CanonicalDocument) -> list[Chunk]:
        lines = doc.body.split("\n")
        if len(lines) <= self.rows_per_chunk:
            return [self._make_chunk(doc, doc.body, 0, chunk_type="table_full")]

        chunks = []
        for i in range(0, len(lines), self.rows_per_chunk):
            batch = "\n".join(lines[i:i + self.rows_per_chunk])
            if batch.strip():
                chunks.append(self._make_chunk(doc, batch, len(chunks), chunk_type="table_row_group"))
        return chunks


class CodeChunker(BaseChunker):
    """Symbol-aware: split at function/class boundaries. Target: 1024 tokens."""
    name = "code"

    def __init__(self, chunk_size: int = 1024) -> None:
        self.chunk_size = chunk_size

    def chunk(self, doc: CanonicalDocument) -> list[Chunk]:
        # Split by class/function definitions
        pattern = r'(?m)^(?:class |def |function |export |public |private |async )'
        parts = re.split(pattern, doc.body)

        if len(parts) <= 1:
            return [self._make_chunk(doc, doc.body, 0, chunk_type="code_file")]

        chunks = []
        for i, part in enumerate(parts):
            if part.strip():
                chunks.append(self._make_chunk(doc, part.strip(), i, chunk_type="code_symbol"))
        return chunks


class ConversationChunker(BaseChunker):
    """Turn-based: group by 5 turns. Target: 256 tokens, 20% overlap."""
    name = "conversation"

    def __init__(self, turns_per_chunk: int = 5) -> None:
        self.turns_per_chunk = turns_per_chunk

    def chunk(self, doc: CanonicalDocument) -> list[Chunk]:
        lines = doc.body.split("\n")
        # Detect turns by pattern: "user @ timestamp: message" or "> message"
        turns: list[str] = []
        current = ""
        for line in lines:
            if re.match(r'^[\w@\s]+\s*@\s*[\d.]+:', line) or re.match(r'^>\s', line):
                if current.strip():
                    turns.append(current.strip())
                current = line + "\n"
            else:
                current += line + "\n"
        if current.strip():
            turns.append(current.strip())

        if not turns:
            return [self._make_chunk(doc, doc.body, 0, chunk_type="conversation_full")]

        chunks = []
        overlap = max(1, self.turns_per_chunk // 5)
        i = 0
        while i < len(turns):
            batch = "\n\n".join(turns[i:i + self.turns_per_chunk])
            chunks.append(self._make_chunk(doc, batch, len(chunks), chunk_type="message_turn"))
            i += self.turns_per_chunk - overlap
        return chunks


class EmailChunker(BaseChunker):
    """Split by quoted replies; keep headers with each chunk. Target: 384 tokens."""
    name = "email"

    def chunk(self, doc: CanonicalDocument) -> list[Chunk]:
        parts = re.split(r'(?m)^>+\s*On .+ wrote:', doc.body)
        chunks = []
        for i, part in enumerate(parts):
            if part.strip():
                chunks.append(self._make_chunk(doc, part.strip(), i, chunk_type="email_part"))
        return chunks if chunks else [self._make_chunk(doc, doc.body, 0, chunk_type="email_full")]


class WebpageChunker(BaseChunker):
    """DOM section splitter (by double newlines/sections). Target: 512 tokens, 5% overlap."""
    name = "webpage"

    def __init__(self, chunk_size: int = 512) -> None:
        self.chunk_size = chunk_size

    def chunk(self, doc: CanonicalDocument) -> list[Chunk]:
        sections = re.split(r'\n{2,}', doc.body)
        chunks = []
        buffer = ""
        for section in sections:
            if len((buffer + "\n\n" + section).split()) > self.chunk_size and buffer:
                chunks.append(self._make_chunk(doc, buffer.strip(), len(chunks), chunk_type="webpage_section"))
                buffer = section
            else:
                buffer = (buffer + "\n\n" + section).strip()
        if buffer.strip():
            chunks.append(self._make_chunk(doc, buffer.strip(), len(chunks), chunk_type="webpage_section"))
        return chunks if chunks else [self._make_chunk(doc, doc.body, 0, chunk_type="webpage_full")]


class NotebookChunker(BaseChunker):
    """Cell group: group consecutive non-code cells. Target: 256 tokens."""
    name = "notebook"

    def chunk(self, doc: CanonicalDocument) -> list[Chunk]:
        cells = re.split(r'(?m)^(?:In\s*\[\d*\]:?|```)', doc.body)
        chunks = []
        for i, cell in enumerate(cells):
            if cell.strip():
                chunks.append(self._make_chunk(doc, cell.strip(), i, chunk_type="notebook_cell"))
        return chunks if chunks else [self._make_chunk(doc, doc.body, 0, chunk_type="notebook_full")]


class EventWindowChunker(BaseChunker):
    """Time slice: each event or group as chunk. Target: 128 tokens."""
    name = "event_window"

    def chunk(self, doc: CanonicalDocument) -> list[Chunk]:
        events = doc.body.split("\n")
        chunks = []
        batch: list[str] = []
        for event in events:
            batch.append(event)
            if len(" ".join(batch).split()) >= 128:
                chunks.append(self._make_chunk(doc, "\n".join(batch), len(chunks), chunk_type="event_batch"))
                batch = []
        if batch:
            chunks.append(self._make_chunk(doc, "\n".join(batch), len(chunks), chunk_type="event_batch"))
        return chunks


# ─── Registry ───

class ChunkerRegistry:
    def __init__(self) -> None:
        self._chunkers: dict[SemanticType, BaseChunker] = {}
        self._default = DocumentChunker()

    def register(self, semantic_type: SemanticType, chunker: BaseChunker) -> None:
        self._chunkers[semantic_type] = chunker

    def resolve(self, semantic_type: SemanticType) -> BaseChunker:
        return self._chunkers.get(semantic_type, self._default)

    def list(self) -> dict[str, str]:
        return {k.value: v.name for k, v in self._chunkers.items()}


_registry = ChunkerRegistry()


def get_chunker_registry() -> ChunkerRegistry:
    return _registry


def register_default_chunkers() -> None:
    _registry.register(SemanticType.DOCUMENT, DocumentChunker())
    _registry.register(SemanticType.TABLE, TableChunker())
    _registry.register(SemanticType.CODE, CodeChunker())
    _registry.register(SemanticType.CONVERSATION, ConversationChunker())
    _registry.register(SemanticType.EMAIL, EmailChunker())
    _registry.register(SemanticType.WEBPAGE, WebpageChunker())
    _registry.register(SemanticType.NOTEBOOK, NotebookChunker())
    _registry.register(SemanticType.EVENT_WINDOW, EventWindowChunker())
