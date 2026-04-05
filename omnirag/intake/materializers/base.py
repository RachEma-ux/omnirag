"""Materializer base + registry + all 8 semantic materializers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from omnirag.intake.models import (
    ACL, CanonicalDocument, ExtractedContent, SemanticType, SourceObject, Visibility,
)


class BaseMaterializer(ABC):
    """Transforms ExtractedContent + SourceObject into a CanonicalDocument."""

    name: str = "base"

    @abstractmethod
    def can_materialize(self, source_object: SourceObject, extracted: ExtractedContent) -> bool:
        ...

    @abstractmethod
    def materialize(self, source_object: SourceObject, extracted: ExtractedContent, acl: ACL | None = None) -> CanonicalDocument:
        ...


class DocumentMaterializer(BaseMaterializer):
    """PDF, DOCX, TXT, MD → document."""
    name = "document"

    def can_materialize(self, source_object: SourceObject, extracted: ExtractedContent) -> bool:
        ext = source_object.metadata.get("filename", "").rsplit(".", 1)[-1].lower() if "." in source_object.metadata.get("filename", "") else ""
        return ext in ("pdf", "docx", "doc", "txt", "md", "rst", "rtf", "epub") or (
            extracted.structure and extracted.structure.get("type") in ("pdf_page", "document")
        )

    def materialize(self, source_object: SourceObject, extracted: ExtractedContent, acl: ACL | None = None) -> CanonicalDocument:
        title = extracted.metadata.get("title") or source_object.metadata.get("filename")
        return CanonicalDocument(
            source_object_ref=source_object.id,
            semantic_type=SemanticType.DOCUMENT,
            title=title,
            language=extracted.language,
            body=extracted.text,
            structure=extracted.structure,
            metadata=extracted.metadata,
            provenance={"connector_id": source_object.connector_id, "external_id": source_object.external_id, "source_url": source_object.source_url},
            acl=acl or ACL(visibility=Visibility.TENANT),
        )


class TableMaterializer(BaseMaterializer):
    """CSV, XLSX, database rows → table."""
    name = "table"

    def can_materialize(self, source_object: SourceObject, extracted: ExtractedContent) -> bool:
        ext = source_object.metadata.get("filename", "").rsplit(".", 1)[-1].lower() if "." in source_object.metadata.get("filename", "") else ""
        return ext in ("csv", "tsv", "xlsx", "xls", "parquet")

    def materialize(self, source_object: SourceObject, extracted: ExtractedContent, acl: ACL | None = None) -> CanonicalDocument:
        return CanonicalDocument(
            source_object_ref=source_object.id,
            semantic_type=SemanticType.TABLE,
            title=source_object.metadata.get("filename"),
            body=extracted.text,
            structure=extracted.structure,
            metadata=extracted.metadata,
            provenance={"connector_id": source_object.connector_id, "external_id": source_object.external_id},
            acl=acl or ACL(visibility=Visibility.TENANT),
        )


class CodeMaterializer(BaseMaterializer):
    """Source code → code."""
    name = "code"

    def can_materialize(self, source_object: SourceObject, extracted: ExtractedContent) -> bool:
        return extracted.structure is not None and extracted.structure.get("type") == "code"

    def materialize(self, source_object: SourceObject, extracted: ExtractedContent, acl: ACL | None = None) -> CanonicalDocument:
        return CanonicalDocument(
            source_object_ref=source_object.id,
            semantic_type=SemanticType.CODE,
            title=source_object.metadata.get("filename"),
            language=extracted.language,
            body=extracted.text,
            structure=extracted.structure,
            metadata=extracted.metadata,
            provenance={"connector_id": source_object.connector_id, "external_id": source_object.external_id},
            acl=acl or ACL(visibility=Visibility.TENANT),
        )


class WebpageMaterializer(BaseMaterializer):
    """HTML → webpage."""
    name = "webpage"

    def can_materialize(self, source_object: SourceObject, extracted: ExtractedContent) -> bool:
        return extracted.structure is not None and extracted.structure.get("type") == "webpage"

    def materialize(self, source_object: SourceObject, extracted: ExtractedContent, acl: ACL | None = None) -> CanonicalDocument:
        title = extracted.structure.get("title") if extracted.structure else None
        return CanonicalDocument(
            source_object_ref=source_object.id,
            semantic_type=SemanticType.WEBPAGE,
            title=title or source_object.metadata.get("filename"),
            body=extracted.text,
            structure=extracted.structure,
            metadata=extracted.metadata,
            provenance={"connector_id": source_object.connector_id, "external_id": source_object.external_id, "source_url": source_object.source_url},
            acl=acl or ACL(visibility=Visibility.PUBLIC),
        )


class ConversationMaterializer(BaseMaterializer):
    """Slack threads, chat logs → conversation."""
    name = "conversation"

    def can_materialize(self, source_object: SourceObject, extracted: ExtractedContent) -> bool:
        return extracted.structure is not None and extracted.structure.get("type") == "conversation"

    def materialize(self, source_object: SourceObject, extracted: ExtractedContent, acl: ACL | None = None) -> CanonicalDocument:
        return CanonicalDocument(
            source_object_ref=source_object.id,
            semantic_type=SemanticType.CONVERSATION,
            title=extracted.metadata.get("thread_title"),
            body=extracted.text,
            structure=extracted.structure,
            metadata=extracted.metadata,
            provenance={"connector_id": source_object.connector_id, "external_id": source_object.external_id},
            acl=acl or ACL(visibility=Visibility.SHARED),
        )


class EmailMaterializer(BaseMaterializer):
    """Email → email."""
    name = "email"

    def can_materialize(self, source_object: SourceObject, extracted: ExtractedContent) -> bool:
        ext = source_object.metadata.get("filename", "").rsplit(".", 1)[-1].lower() if "." in source_object.metadata.get("filename", "") else ""
        return ext in ("eml", "mbox") or (extracted.structure and extracted.structure.get("type") == "email")

    def materialize(self, source_object: SourceObject, extracted: ExtractedContent, acl: ACL | None = None) -> CanonicalDocument:
        return CanonicalDocument(
            source_object_ref=source_object.id,
            semantic_type=SemanticType.EMAIL,
            title=extracted.metadata.get("subject"),
            body=extracted.text,
            structure=extracted.structure,
            metadata=extracted.metadata,
            provenance={"connector_id": source_object.connector_id, "external_id": source_object.external_id},
            acl=acl or ACL(visibility=Visibility.PRIVATE),
        )


class NotebookMaterializer(BaseMaterializer):
    """Jupyter notebooks → notebook."""
    name = "notebook"

    def can_materialize(self, source_object: SourceObject, extracted: ExtractedContent) -> bool:
        ext = source_object.metadata.get("filename", "").rsplit(".", 1)[-1].lower() if "." in source_object.metadata.get("filename", "") else ""
        return ext == "ipynb"

    def materialize(self, source_object: SourceObject, extracted: ExtractedContent, acl: ACL | None = None) -> CanonicalDocument:
        return CanonicalDocument(
            source_object_ref=source_object.id,
            semantic_type=SemanticType.NOTEBOOK,
            title=source_object.metadata.get("filename"),
            body=extracted.text,
            structure=extracted.structure,
            metadata=extracted.metadata,
            provenance={"connector_id": source_object.connector_id, "external_id": source_object.external_id},
            acl=acl or ACL(visibility=Visibility.TENANT),
        )


class EventWindowMaterializer(BaseMaterializer):
    """Kafka/MQTT/WebSocket events → event_window."""
    name = "event_window"

    def can_materialize(self, source_object: SourceObject, extracted: ExtractedContent) -> bool:
        return extracted.structure is not None and extracted.structure.get("type") == "event_window"

    def materialize(self, source_object: SourceObject, extracted: ExtractedContent, acl: ACL | None = None) -> CanonicalDocument:
        return CanonicalDocument(
            source_object_ref=source_object.id,
            semantic_type=SemanticType.EVENT_WINDOW,
            title=extracted.metadata.get("window_title"),
            body=extracted.text,
            structure=extracted.structure,
            metadata=extracted.metadata,
            provenance={"connector_id": source_object.connector_id, "external_id": source_object.external_id},
            acl=acl or ACL(visibility=Visibility.TENANT),
        )


# ─── Default materializer (fallback) ───

class FallbackMaterializer(BaseMaterializer):
    """Catch-all: unknown → document."""
    name = "fallback"

    def can_materialize(self, source_object: SourceObject, extracted: ExtractedContent) -> bool:
        return True

    def materialize(self, source_object: SourceObject, extracted: ExtractedContent, acl: ACL | None = None) -> CanonicalDocument:
        return CanonicalDocument(
            source_object_ref=source_object.id,
            semantic_type=SemanticType.DOCUMENT,
            title=source_object.metadata.get("filename"),
            body=extracted.text,
            structure=extracted.structure,
            metadata=extracted.metadata,
            provenance={"connector_id": source_object.connector_id, "external_id": source_object.external_id},
            acl=acl or ACL(visibility=Visibility.TENANT),
        )


# ─── Registry ───

class MaterializerRegistry:
    def __init__(self) -> None:
        self._materializers: list[BaseMaterializer] = []

    def register(self, m: BaseMaterializer) -> None:
        self._materializers.append(m)

    def resolve(self, source_object: SourceObject, extracted: ExtractedContent) -> BaseMaterializer:
        for m in self._materializers:
            if m.can_materialize(source_object, extracted):
                return m
        return FallbackMaterializer()

    def list(self) -> list[str]:
        return [m.name for m in self._materializers]


_registry = MaterializerRegistry()


def get_materializer_registry() -> MaterializerRegistry:
    return _registry


def register_default_materializers() -> None:
    """Register all 8 materializers + fallback in priority order."""
    for cls in [
        CodeMaterializer, WebpageMaterializer, ConversationMaterializer,
        EmailMaterializer, NotebookMaterializer, EventWindowMaterializer,
        TableMaterializer, DocumentMaterializer, FallbackMaterializer,
    ]:
        _registry.register(cls())
