"""Text extractor — plain text, markdown, code, config files."""

from __future__ import annotations

from omnirag.intake.extractors.base import BaseExtractor
from omnirag.intake.models import ExtractedContent, RawContent, SourceObject

TEXT_EXTENSIONS = {
    "txt", "md", "rst", "log", "text", "readme",
    "cfg", "conf", "ini", "env", "properties",
    "yaml", "yml", "toml", "json", "jsonl", "ndjson",
    "xml", "svg", "csv", "tsv",
    "sh", "bash", "zsh", "fish",
    "py", "pyw", "pyi", "js", "mjs", "ts", "tsx", "jsx",
    "java", "kt", "scala", "go", "rs", "c", "cpp", "h", "hpp", "cs",
    "rb", "php", "lua", "r", "swift", "sql", "graphql",
    "html", "htm", "css", "scss", "less",
    "dockerfile", "makefile", "cmake", "tf", "hcl", "nix",
    "proto", "thrift", "avsc", "ipynb", "eml",
}


class TextExtractor(BaseExtractor):
    name = "text"

    def can_handle(self, mime_type: str | None, extension: str | None) -> bool:
        if mime_type and (mime_type.startswith("text/") or mime_type in (
            "application/json", "application/x-yaml", "application/xml",
            "application/javascript", "application/x-sh",
        )):
            return True
        if extension and extension.lower().lstrip(".") in TEXT_EXTENSIONS:
            return True
        return False

    async def extract(self, raw: RawContent, source_object: SourceObject) -> list[ExtractedContent]:
        try:
            text = raw.data.decode("utf-8")
        except UnicodeDecodeError:
            try:
                import chardet
                detected = chardet.detect(raw.data)
                enc = detected.get("encoding", "latin-1") or "latin-1"
                text = raw.data.decode(enc, errors="replace")
            except ImportError:
                text = raw.data.decode("latin-1", errors="replace")

        text = text.strip()
        if not text:
            return []

        ext = (raw.extension or "").lower().lstrip(".")
        # Detect if code
        code_exts = {"py", "js", "ts", "tsx", "jsx", "java", "go", "rs", "c", "cpp", "rb", "php", "swift", "kt", "cs"}
        structure = None
        if ext in code_exts:
            lines = text.split("\n")
            structure = {"type": "code", "language": ext, "line_count": len(lines)}

        return [
            ExtractedContent(
                text=text,
                structure=structure,
                metadata={"filename": raw.filename, "extension": ext, "size_bytes": raw.size_bytes},
                confidence=1.0,
                language=ext if ext in code_exts else None,
            )
        ]
