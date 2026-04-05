"""PDF extractor — layout-aware text extraction with structure."""

from __future__ import annotations

import io

from omnirag.intake.extractors.base import BaseExtractor
from omnirag.intake.models import ExtractedContent, RawContent, SourceObject


class PdfExtractor(BaseExtractor):
    name = "pdf"

    def can_handle(self, mime_type: str | None, extension: str | None) -> bool:
        if extension and extension.lower().lstrip(".") == "pdf":
            return True
        if mime_type and "pdf" in mime_type.lower():
            return True
        return False

    async def extract(self, raw: RawContent, source_object: SourceObject) -> list[ExtractedContent]:
        results: list[ExtractedContent] = []

        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(raw.data)) as pdf:
                total = len(pdf.pages)
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    tables = page.extract_tables() or []
                    text = text.strip()
                    if not text and not tables:
                        continue

                    structure = {
                        "type": "pdf_page",
                        "page": i + 1,
                        "total_pages": total,
                        "width": page.width,
                        "height": page.height,
                        "has_tables": len(tables) > 0,
                        "table_count": len(tables),
                    }

                    # Append table text
                    if tables:
                        for t_idx, table in enumerate(tables):
                            if table:
                                header = table[0] if table else []
                                rows = table[1:] if len(table) > 1 else []
                                table_text = "\n".join([
                                    " | ".join(str(c or "") for c in row) for row in [header] + rows
                                ])
                                text += f"\n\n[Table {t_idx + 1}]\n{table_text}"

                    results.append(ExtractedContent(
                        text=text,
                        structure=structure,
                        metadata={"filename": raw.filename, "total_pages": total},
                        confidence=0.95,
                        page=i + 1,
                    ))
            return results
        except ImportError:
            pass

        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(raw.data))
            total = len(reader.pages)
            for i, page in enumerate(reader.pages):
                text = (page.extract_text() or "").strip()
                if not text:
                    continue
                results.append(ExtractedContent(
                    text=text,
                    structure={"type": "pdf_page", "page": i + 1, "total_pages": total},
                    metadata={"filename": raw.filename, "total_pages": total},
                    confidence=0.85,
                    page=i + 1,
                ))
            return results
        except ImportError:
            raise ImportError("Install pdfplumber or PyPDF2: pip install pdfplumber")
