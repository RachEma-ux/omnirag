"""Loader registry — auto-discovers and dispatches to loaders."""

from __future__ import annotations

from omnirag.intake.loaders.base import BaseLoader


class LoaderRegistry:
    """Registry of all available loaders."""

    def __init__(self) -> None:
        self._loaders: list[BaseLoader] = []

    def register(self, loader: BaseLoader) -> None:
        self._loaders.append(loader)

    def resolve(self, mime_type: str | None, extension: str | None) -> BaseLoader | None:
        for loader in self._loaders:
            if loader.supports(mime_type, extension):
                return loader
        return None

    def list(self) -> list[str]:
        return [l.name for l in self._loaders]


_registry = LoaderRegistry()


def get_registry() -> LoaderRegistry:
    return _registry


def register_loader(loader: BaseLoader) -> None:
    _registry.register(loader)
