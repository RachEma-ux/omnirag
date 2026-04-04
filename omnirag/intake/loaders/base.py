"""Base loader interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from omnirag.intake.models import RawContent, TextSegment


class BaseLoader(ABC):
    """Parses raw content into text segments."""

    name: str = "base"

    @abstractmethod
    async def load(self, content: RawContent) -> list[TextSegment]:
        """Parse raw bytes into text segments with metadata."""
        ...  # pragma: no cover

    @abstractmethod
    def supports(self, mime_type: str | None, extension: str | None) -> bool:
        """Return True if this loader handles the given format."""
        ...  # pragma: no cover
