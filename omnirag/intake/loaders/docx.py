"""DOCX loader — extracts text from Word documents."""

from __future__ import annotations

import io

from omnirag.intake.loaders.base import BaseLoader
from omnirag.intake.models import RawContent, TextSegment


class DocxLoader(BaseLoader):
    """Extracts text from DOCX files, paragraph by paragraph."""

    name = "docx"

    def supports(self, mime_type: str | None, extension: str | None) -> bool:
        ext = (extension or "").lower().lstrip(".")
        if ext in ("docx", "doc"):
            return True
        if mime_type and "wordprocessingml" in mime_type:
            return True
        if mime_type and "msword" in mime_type:
            return True
        return False

    async def load(self, content: RawContent) -> list[TextSegment]:
        try:
            from docx import Document
        except ImportError:
            raise ImportError("Install python-docx: pip install python-docx")

        doc = Document(io.BytesIO(content.data))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

        if not paragraphs:
            return []

        full_text = "\n\n".join(paragraphs)

        return [
            TextSegment(
                text=full_text,
                source_uri=content.source_uri,
                format="docx",
                metadata={
                    **content.metadata,
                    "filename": content.filename,
                    "paragraph_count": len(paragraphs),
                },
            )
        ]
