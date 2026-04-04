"""Format detector — identifies file format from MIME, extension, and magic bytes."""

from __future__ import annotations

# Magic byte signatures
MAGIC_SIGNATURES: list[tuple[bytes, str, str]] = [
    (b"%PDF", "application/pdf", "pdf"),
    (b"PK\x03\x04", "application/zip", "zip"),  # also docx, xlsx, pptx
    (b"\x89PNG", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"GIF8", "image/gif", "gif"),
    (b"RIFF", "audio/wav", "wav"),
    (b"ID3", "audio/mpeg", "mp3"),
    (b"\x1f\x8b", "application/gzip", "gz"),
    (b"SQLite format 3", "application/x-sqlite3", "sqlite"),
    (b"PAR1", "application/parquet", "parquet"),
]

# OOXML detection (PK archive subtypes)
OOXML_MARKERS: dict[bytes, tuple[str, str]] = {
    b"word/": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    b"xl/": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    b"ppt/": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "pptx"),
}

EXTENSION_TO_MIME: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "html": "text/html",
    "htm": "text/html",
    "csv": "text/csv",
    "tsv": "text/tab-separated-values",
    "json": "application/json",
    "jsonl": "application/x-jsonlines",
    "xml": "application/xml",
    "yaml": "application/x-yaml",
    "yml": "application/x-yaml",
    "md": "text/markdown",
    "txt": "text/plain",
    "py": "text/x-python",
    "js": "application/javascript",
    "ts": "text/x-typescript",
    "epub": "application/epub+zip",
    "rtf": "application/rtf",
    "eml": "message/rfc822",
    "mbox": "application/mbox",
    "ipynb": "application/x-ipynb+json",
    "sql": "application/sql",
    "parquet": "application/parquet",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "mp4": "video/mp4",
}


def detect_format(
    data: bytes,
    filename: str | None = None,
    mime_hint: str | None = None,
) -> tuple[str | None, str | None]:
    """Detect (mime_type, extension) from data, filename, or hint.

    Returns best-guess (mime_type, extension) tuple.
    """
    ext = None
    if filename and "." in filename:
        ext = filename.rsplit(".", 1)[-1].lower()

    # 1. Magic bytes
    for sig, mime, sig_ext in MAGIC_SIGNATURES:
        if data[:len(sig)] == sig:
            # Check OOXML subtypes for PK archives
            if sig == b"PK\x03\x04":
                for marker, (ooxml_mime, ooxml_ext) in OOXML_MARKERS.items():
                    if marker in data[:2000]:
                        return ooxml_mime, ooxml_ext
            return mime, sig_ext

    # 2. Extension mapping
    if ext and ext in EXTENSION_TO_MIME:
        return EXTENSION_TO_MIME[ext], ext

    # 3. MIME hint
    if mime_hint:
        return mime_hint, ext

    # 4. Try as text
    try:
        data[:1000].decode("utf-8")
        return "text/plain", ext or "txt"
    except UnicodeDecodeError:
        pass

    return None, ext
