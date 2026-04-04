"""HTML loader — strips tags, extracts clean text."""

from __future__ import annotations

from omnirag.intake.loaders.base import BaseLoader
from omnirag.intake.models import RawContent, TextSegment


class HtmlLoader(BaseLoader):
    """Extracts clean text from HTML pages."""

    name = "html"

    def supports(self, mime_type: str | None, extension: str | None) -> bool:
        ext = (extension or "").lower().lstrip(".")
        if ext in ("html", "htm"):
            return True
        if mime_type and "html" in mime_type:
            return True
        return False

    async def load(self, content: RawContent) -> list[TextSegment]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("Install beautifulsoup4: pip install beautifulsoup4")

        try:
            html = content.data.decode("utf-8")
        except UnicodeDecodeError:
            html = content.data.decode("latin-1", errors="replace")

        soup = BeautifulSoup(html, "html.parser")

        # Remove script/style
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else None
        text = soup.get_text(separator="\n", strip=True)

        if not text.strip():
            return []

        return [
            TextSegment(
                text=text,
                source_uri=content.source_uri,
                format="html",
                section=title,
                metadata={
                    **content.metadata,
                    "filename": content.filename,
                    "title": title,
                },
            )
        ]
