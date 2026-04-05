"""HTML extractor — boilerplate removal, main content extraction."""

from __future__ import annotations

from omnirag.intake.extractors.base import BaseExtractor
from omnirag.intake.models import ExtractedContent, RawContent, SourceObject


class HtmlExtractor(BaseExtractor):
    name = "html"

    def can_handle(self, mime_type: str | None, extension: str | None) -> bool:
        ext = (extension or "").lower().lstrip(".")
        if ext in ("html", "htm"):
            return True
        if mime_type and "html" in mime_type:
            return True
        return False

    async def extract(self, raw: RawContent, source_object: SourceObject) -> list[ExtractedContent]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("Install beautifulsoup4: pip install beautifulsoup4")

        try:
            html = raw.data.decode("utf-8")
        except UnicodeDecodeError:
            html = raw.data.decode("latin-1", errors="replace")

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else None
        headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3", "h4"])]
        text = soup.get_text(separator="\n", strip=True)

        if not text.strip():
            return []

        return [ExtractedContent(
            text=text,
            structure={"type": "webpage", "title": title, "headings": headings},
            metadata={"filename": raw.filename, "title": title, "heading_count": len(headings)},
            confidence=0.9,
        )]
