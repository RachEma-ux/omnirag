"""Image extractor — OCR via pytesseract, PIL metadata, SVG text extraction."""

from __future__ import annotations

import re
from io import BytesIO

from omnirag.intake.extractors.base import BaseExtractor
from omnirag.intake.models import ExtractedContent, RawContent, SourceObject

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "tiff", "tif", "webp", "svg"}


class ImageExtractor(BaseExtractor):
    name = "image"

    def can_handle(self, mime_type: str | None, extension: str | None) -> bool:
        ext = (extension or "").lower().lstrip(".")
        if ext in IMAGE_EXTENSIONS:
            return True
        if mime_type and mime_type.startswith("image/"):
            return True
        return False

    async def extract(self, raw: RawContent, source_object: SourceObject) -> list[ExtractedContent]:
        try:
            import structlog
            log = structlog.get_logger(__name__)
        except ImportError:
            import logging
            log = logging.getLogger(__name__)

        ext = (raw.extension or "").lower().lstrip(".")
        base_metadata = {"filename": raw.filename, "extension": ext, "size_bytes": raw.size_bytes}

        # ── SVG: decode as text and extract text content ──
        if ext == "svg" or (raw.mime_type and "svg" in raw.mime_type):
            return self._extract_svg(raw, base_metadata, log)

        # ── Raster images: try OCR, then PIL metadata, then basic metadata ──
        pil_image = None
        image_info: dict = {}

        try:
            from PIL import Image
            from PIL.ExifTags import TAGS

            pil_image = Image.open(BytesIO(raw.data))
            image_info = {
                "width": pil_image.width,
                "height": pil_image.height,
                "format": pil_image.format,
                "color_mode": pil_image.mode,
            }

            # Extract EXIF data
            exif_data: dict = {}
            try:
                raw_exif = pil_image._getexif()  # type: ignore[attr-defined]
                if raw_exif:
                    for tag_id, value in raw_exif.items():
                        tag_name = TAGS.get(tag_id, str(tag_id))
                        try:
                            exif_data[tag_name] = str(value)
                        except Exception:
                            exif_data[tag_name] = repr(value)
            except Exception:
                pass

            if exif_data:
                image_info["exif"] = exif_data

        except ImportError:
            log.debug("PIL not available, falling back to basic metadata")
        except Exception as exc:
            log.warning("PIL failed to open image", error=str(exc))

        # ── Try OCR via pytesseract ──
        if pil_image is not None:
            try:
                import pytesseract

                ocr_text = pytesseract.image_to_string(pil_image).strip()
                if ocr_text:
                    log.info("OCR extraction succeeded", filename=raw.filename, text_length=len(ocr_text))
                    return [ExtractedContent(
                        text=ocr_text,
                        structure={"type": "image", "extraction_method": "ocr", **image_info},
                        metadata={**base_metadata, **image_info},
                        confidence=0.9,
                    )]
                else:
                    log.debug("OCR returned empty text", filename=raw.filename)
            except ImportError:
                log.debug("pytesseract not available, falling back to metadata-only")
            except Exception as exc:
                log.warning("pytesseract OCR failed", error=str(exc))

        # ── PIL metadata-only fallback ──
        if image_info:
            meta_lines = [f"Image: {raw.filename}"]
            meta_lines.append(f"Dimensions: {image_info.get('width')}x{image_info.get('height')}")
            meta_lines.append(f"Format: {image_info.get('format')}")
            meta_lines.append(f"Color mode: {image_info.get('color_mode')}")
            if image_info.get("exif"):
                meta_lines.append(f"EXIF tags: {len(image_info['exif'])}")

            return [ExtractedContent(
                text="\n".join(meta_lines),
                structure={"type": "image", "extraction_method": "pil_metadata", **image_info},
                metadata={**base_metadata, **image_info},
                confidence=0.5,
            )]

        # ── Bare minimum: just file size and extension ──
        log.debug("No image libraries available, returning basic metadata", filename=raw.filename)
        return [ExtractedContent(
            text=f"Image: {raw.filename} ({raw.size_bytes} bytes)",
            structure={"type": "image", "extraction_method": "basic"},
            metadata=base_metadata,
            confidence=0.3,
        )]

    def _extract_svg(self, raw: RawContent, base_metadata: dict, log: object) -> list[ExtractedContent]:
        """Extract text content from SVG XML."""
        try:
            svg_text = raw.data.decode("utf-8")
        except UnicodeDecodeError:
            svg_text = raw.data.decode("latin-1", errors="replace")

        # Extract text elements from SVG
        text_parts: list[str] = []
        # Match <text>...</text> and <tspan>...</tspan> content
        for match in re.finditer(r"<(?:text|tspan)[^>]*>([^<]+)</(?:text|tspan)>", svg_text):
            content = match.group(1).strip()
            if content:
                text_parts.append(content)

        # Also try to extract title and desc elements
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", svg_text)
        desc_match = re.search(r"<desc[^>]*>([^<]+)</desc>", svg_text)

        extracted_text = "\n".join(text_parts) if text_parts else ""
        if title_match:
            extracted_text = f"Title: {title_match.group(1).strip()}\n{extracted_text}"
        if desc_match:
            extracted_text = f"Description: {desc_match.group(1).strip()}\n{extracted_text}"

        extracted_text = extracted_text.strip()
        if not extracted_text:
            extracted_text = f"SVG image: {raw.filename} ({raw.size_bytes} bytes)"

        # Extract viewBox dimensions if available
        structure: dict = {"type": "image", "format": "svg", "extraction_method": "svg_parse"}
        viewbox_match = re.search(r'viewBox=["\']([^"\']+)["\']', svg_text)
        if viewbox_match:
            structure["viewBox"] = viewbox_match.group(1)
        width_match = re.search(r'width=["\']([^"\']+)["\']', svg_text)
        height_match = re.search(r'height=["\']([^"\']+)["\']', svg_text)
        if width_match:
            structure["width"] = width_match.group(1)
        if height_match:
            structure["height"] = height_match.group(1)

        confidence = 0.8 if text_parts else 0.4

        return [ExtractedContent(
            text=extracted_text,
            structure=structure,
            metadata={**base_metadata, "text_element_count": len(text_parts)},
            confidence=confidence,
        )]
