"""Intake data models — shared across connectors, loaders, and gate."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IntakeStatus(str, Enum):
    PENDING = "pending"
    FETCHING = "fetching"
    LOADING = "loading"
    NORMALIZING = "normalizing"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class RawContent:
    """Raw bytes fetched by a connector, before parsing."""

    data: bytes
    source_uri: str
    filename: str
    mime_type: str | None = None
    extension: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    size_bytes: int = 0

    def __post_init__(self) -> None:
        self.size_bytes = len(self.data)
        if not self.extension and "." in self.filename:
            self.extension = self.filename.rsplit(".", 1)[-1].lower()


@dataclass
class TextSegment:
    """A unit of text extracted by a loader, before normalization."""

    text: str
    source_uri: str
    format: str
    page: int | None = None
    section: str | None = None
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OmniDocument:
    """Normalized document ready for the OmniRAG pipeline."""

    id: str
    text: str
    metadata: dict[str, Any]
    source_uri: str
    format: str
    connector: str
    loader: str
    created_at: float
    chunk_hint: str | None = None

    @staticmethod
    def from_segment(
        segment: TextSegment,
        connector_name: str,
        loader_name: str,
    ) -> OmniDocument:
        doc_id = hashlib.sha256(
            f"{segment.source_uri}:{segment.page}:{segment.text[:200]}".encode()
        ).hexdigest()[:16]
        return OmniDocument(
            id=doc_id,
            text=segment.text,
            metadata={
                **segment.metadata,
                "page": segment.page,
                "section": segment.section,
                "language": segment.language,
            },
            source_uri=segment.source_uri,
            format=segment.format,
            connector=connector_name,
            loader=loader_name,
            created_at=time.time(),
        )


@dataclass
class IntakeRequest:
    """Incoming intake request from the API."""

    source: str
    config: dict[str, Any] = field(default_factory=dict)
    pipeline: str | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class IntakeJob:
    """Tracks the state of an intake operation."""

    id: str
    request: IntakeRequest
    status: IntakeStatus = IntakeStatus.PENDING
    files_found: int = 0
    files_loaded: int = 0
    documents_created: int = 0
    errors: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    def fail(self, message: str) -> None:
        self.status = IntakeStatus.FAILED
        self.errors.append(message)
        self.completed_at = time.time()

    def complete(self) -> None:
        self.status = IntakeStatus.COMPLETE
        self.completed_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "intake_id": self.id,
            "status": self.status.value,
            "source": self.request.source,
            "pipeline": self.request.pipeline,
            "files_found": self.files_found,
            "files_loaded": self.files_loaded,
            "documents_created": self.documents_created,
            "errors": self.errors,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }
