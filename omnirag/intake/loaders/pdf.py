"""PDF loader — extracts text page by page."""

from __future__ import annotations

import io

from omnirag.intake.loaders.base import BaseLoader
from omnirag.intake.models import RawContent, TextSegment


class PdfLoader(BaseLoader):
    """Extracts text from PDF files, page by page."""

    name = "pdf"

    def supports(self, mime_type: str | None, extension: str | None) -> bool:
        if extension and extension.lower().lstrip(".") == "pdf":
            return True
        if mime_type and "pdf" in mime_type.lower():
            return True
        return False

    async def load(self, content: RawContent) -> list[TextSegment]:
        segments: list[TextSegment] = []

        # Try pdfplumber first (better table/layout extraction)
        try:
            import pdfplumber

            with pdfplumber.open(io.BytesIO(content.data)) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    text = text.strip()
                    if not text:
                        continue
                    segments.append(
                        TextSegment(
                            text=text,
                            source_uri=content.source_uri,
                            format="pdf",
                            page=i + 1,
                            metadata={
                                **content.metadata,
                                "filename": content.filename,
                                "total_pages": len(pdf.pages),
                                "page_width": page.width,
                                "page_height": page.height,
                            },
                        )
                    )
            return segments
        except ImportError:
            pass

        # Fallback to PyPDF2
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(io.BytesIO(content.data))
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                text = text.strip()
                if not text:
                    continue
                segments.append(
                    TextSegment(
                        text=text,
                        source_uri=content.source_uri,
                        format="pdf",
                        page=i + 1,
                        metadata={
                            **content.metadata,
                            "filename": content.filename,
                            "total_pages": len(reader.pages),
                        },
                    )
                )
            return segments
        except ImportError:
            raise ImportError(
                "No PDF library available. Install one:\n"
                "  pip install pdfplumber\n"
                "  pip install PyPDF2"
            )
