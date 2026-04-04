"""Register default connectors and loaders."""

from __future__ import annotations


def register_defaults() -> None:
    """Register all built-in connectors and loaders."""
    from omnirag.intake.connectors.registry import register_connector
    from omnirag.intake.loaders.registry import register_loader

    # Connectors (always available)
    from omnirag.intake.connectors.local import LocalConnector
    register_connector(LocalConnector())

    from omnirag.intake.connectors.http import HttpConnector
    register_connector(HttpConnector())

    # Connectors (optional deps)
    try:
        from omnirag.intake.connectors.s3 import S3Connector
        register_connector(S3Connector())
    except Exception:
        pass

    try:
        from omnirag.intake.connectors.github import GitHubConnector
        register_connector(GitHubConnector())
    except Exception:
        pass

    # Loaders (always available)
    from omnirag.intake.loaders.text import TextLoader
    register_loader(TextLoader())

    # Loaders (optional deps — registered if library is available)
    from omnirag.intake.loaders.pdf import PdfLoader
    register_loader(PdfLoader())

    from omnirag.intake.loaders.docx import DocxLoader
    register_loader(DocxLoader())

    from omnirag.intake.loaders.html import HtmlLoader
    register_loader(HtmlLoader())
