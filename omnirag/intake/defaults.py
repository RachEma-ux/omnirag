"""Register all default connectors, extractors, materializers, and chunkers."""

from __future__ import annotations


def register_defaults() -> None:
    """Register all built-in components for the intake gate."""

    # ── Connectors ──
    from omnirag.intake.connectors.registry import register_connector
    from omnirag.intake.connectors.local import LocalConnector
    from omnirag.intake.connectors.http import HttpConnector

    register_connector(LocalConnector())
    register_connector(HttpConnector())

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

    # ── Extractors ──
    from omnirag.intake.extractors.base import register_extractor
    from omnirag.intake.extractors.text import TextExtractor
    from omnirag.intake.extractors.pdf import PdfExtractor
    from omnirag.intake.extractors.html import HtmlExtractor
    from omnirag.intake.extractors.docx import DocxExtractor

    register_extractor(PdfExtractor())
    register_extractor(DocxExtractor())
    register_extractor(HtmlExtractor())
    register_extractor(TextExtractor())  # last — widest match

    # ── Materializers ──
    from omnirag.intake.materializers.base import register_default_materializers
    register_default_materializers()

    # ── Chunkers ──
    from omnirag.intake.chunkers.base import register_default_chunkers
    register_default_chunkers()
