"""Base extractor interface — replaces simple Loaders with structured output."""

from __future__ import annotations

from abc import ABC, abstractmethod

from omnirag.intake.models import ExtractedContent, RawContent, SourceObject


class BaseExtractor(ABC):
    """Converts raw bytes to ExtractedContent with text, structure, metadata, and confidence."""

    name: str = "base"

    @abstractmethod
    async def extract(self, raw: RawContent, source_object: SourceObject) -> list[ExtractedContent]:
        """Extract structured content from raw bytes. May return multiple (e.g., pages)."""
        ...

    @abstractmethod
    def can_handle(self, mime_type: str | None, extension: str | None) -> bool:
        """Return True if this extractor handles the given format."""
        ...


class ExtractorRegistry:
    """Registry of all available extractors."""

    def __init__(self) -> None:
        self._extractors: list[BaseExtractor] = []

    def register(self, extractor: BaseExtractor) -> None:
        self._extractors.append(extractor)

    def resolve(self, mime_type: str | None, extension: str | None) -> BaseExtractor | None:
        for ext in self._extractors:
            if ext.can_handle(mime_type, extension):
                return ext
        return None

    def list(self) -> list[str]:
        return [e.name for e in self._extractors]


_registry = ExtractorRegistry()


def get_extractor_registry() -> ExtractorRegistry:
    return _registry


def register_extractor(extractor: BaseExtractor) -> None:
    _registry.register(extractor)
