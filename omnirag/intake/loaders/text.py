"""Text loader — plain text, markdown, RST, logs, config files."""

from __future__ import annotations

from omnirag.intake.loaders.base import BaseLoader
from omnirag.intake.models import RawContent, TextSegment

TEXT_EXTENSIONS = {
    "txt", "md", "rst", "log", "text", "readme",
    "cfg", "conf", "ini", "env", "properties",
    "yaml", "yml", "toml",
    "json", "jsonl", "ndjson",
    "xml", "svg",
    "csv", "tsv",
    "sh", "bash", "zsh", "fish",
    "py", "pyw", "pyi",
    "js", "mjs", "cjs", "ts", "tsx", "jsx",
    "java", "kt", "scala", "groovy",
    "go", "rs", "c", "cpp", "h", "hpp", "cs",
    "rb", "php", "pl", "pm", "lua", "r",
    "swift", "m", "mm",
    "sql", "graphql", "gql",
    "html", "htm", "css", "scss", "less", "sass",
    "dockerfile", "makefile", "cmake",
    "tf", "hcl", "nix",
    "proto", "thrift", "avsc",
}

TEXT_MIMES = {
    "text/plain", "text/markdown", "text/x-rst",
    "text/csv", "text/tab-separated-values",
    "text/html", "text/xml", "text/css",
    "application/json", "application/x-yaml",
    "application/xml", "application/javascript",
    "application/x-sh",
}


class TextLoader(BaseLoader):
    """Loads plain text, markdown, code, config, and structured text files."""

    name = "text"

    def supports(self, mime_type: str | None, extension: str | None) -> bool:
        if mime_type and (mime_type in TEXT_MIMES or mime_type.startswith("text/")):
            return True
        if extension and extension.lower().lstrip(".") in TEXT_EXTENSIONS:
            return True
        return False

    async def load(self, content: RawContent) -> list[TextSegment]:
        # Try UTF-8 first, then detect encoding
        try:
            text = content.data.decode("utf-8")
        except UnicodeDecodeError:
            try:
                import chardet
                detected = chardet.detect(content.data)
                encoding = detected.get("encoding", "latin-1") or "latin-1"
                text = content.data.decode(encoding, errors="replace")
            except ImportError:
                text = content.data.decode("latin-1", errors="replace")

        text = text.strip()
        if not text:
            return []

        ext = (content.extension or "").lower().lstrip(".")
        fmt = ext if ext else "text"

        return [
            TextSegment(
                text=text,
                source_uri=content.source_uri,
                format=fmt,
                metadata={**content.metadata, "filename": content.filename},
            )
        ]
