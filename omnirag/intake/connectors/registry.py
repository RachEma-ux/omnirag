"""Connector registry — auto-discovers and dispatches to connectors."""

from __future__ import annotations

from omnirag.intake.connectors.base import BaseConnector


class ConnectorRegistry:
    """Registry of all available connectors."""

    def __init__(self) -> None:
        self._connectors: list[BaseConnector] = []

    def register(self, connector: BaseConnector) -> None:
        self._connectors.append(connector)

    def resolve(self, source: str) -> BaseConnector | None:
        for connector in self._connectors:
            if connector.supports(source):
                return connector
        return None

    def list(self) -> list[str]:
        return [c.name for c in self._connectors]


_registry = ConnectorRegistry()


def get_registry() -> ConnectorRegistry:
    return _registry


def register_connector(connector: BaseConnector) -> None:
    _registry.register(connector)
