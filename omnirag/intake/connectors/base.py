"""Base connector interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from omnirag.intake.models import RawContent


class BaseConnector(ABC):
    """Fetches raw content from a source."""

    name: str = "base"

    @abstractmethod
    async def fetch(self, source: str, config: dict) -> AsyncIterator[RawContent]:
        """Yield RawContent objects from the source."""
        ...  # pragma: no cover

    @abstractmethod
    def supports(self, source: str) -> bool:
        """Return True if this connector handles the given source URI."""
        ...  # pragma: no cover
