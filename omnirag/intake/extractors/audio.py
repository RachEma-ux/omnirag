"""Audio extractor — transcription via Whisper, speech_recognition, or metadata-only."""

from __future__ import annotations

import tempfile
from io import BytesIO

from omnirag.intake.extractors.base import BaseExtractor
from omnirag.intake.models import ExtractedContent, RawContent, SourceObject

AUDIO_EXTENSIONS = {"mp3", "wav", "flac", "ogg", "m4a", "aac", "wma", "opus", "webm"}


class AudioExtractor(BaseExtractor):
    name = "audio"

    def can_handle(self, mime_type: str | None, extension: str | None) -> bool:
        ext = (extension or "").lower().lstrip(".")
        if ext in AUDIO_EXTENSIONS:
            return True
        if mime_type and mime_type.startswith("audio/"):
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

        # Gather audio metadata (duration, sample rate, channels) if possible
        audio_info = self._extract_audio_info(raw, log)

        # ── Try Whisper (local model) ──
        try:
            import whisper

            log.info("Attempting Whisper transcription", filename=raw.filename)
            suffix = f".{ext}" if ext else ".wav"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
                tmp.write(raw.data)
                tmp.flush()

                model = whisper.load_model("base")
                result = model.transcribe(tmp.name)

            text = (result.get("text") or "").strip()
            if text:
                language = result.get("language")
                structure = {"type": "audio", "extraction_method": "whisper"}
                if audio_info:
                    structure.update(audio_info)
                if language:
                    structure["detected_language"] = language

                log.info(
                    "Whisper transcription succeeded",
                    filename=raw.filename,
                    text_length=len(text),
                    language=language,
                )
                return [ExtractedContent(
                    text=text,
                    structure=structure,
                    metadata={**base_metadata, **audio_info},
                    confidence=0.85,
                    language=language,
                )]
            else:
                log.debug("Whisper returned empty transcription", filename=raw.filename)
        except ImportError:
            log.debug("whisper not available, trying speech_recognition")
        except Exception as exc:
            log.warning("Whisper transcription failed", error=str(exc))

        # ── Try speech_recognition ──
        try:
            import speech_recognition as sr

            log.info("Attempting speech_recognition", filename=raw.filename)
            recognizer = sr.Recognizer()
            # speech_recognition AudioFile needs a file-like or path; BytesIO works for WAV
            # For non-WAV, write to temp file
            if ext == "wav":
                audio_source = sr.AudioFile(BytesIO(raw.data))
            else:
                suffix = f".{ext}" if ext else ".wav"
                tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
                tmp.write(raw.data)
                tmp.flush()
                tmp.close()
                audio_source = sr.AudioFile(tmp.name)

            with audio_source as source:
                audio_data = recognizer.record(source)

            text = recognizer.recognize_google(audio_data)
            text = (text or "").strip()

            if text:
                structure = {"type": "audio", "extraction_method": "speech_recognition"}
                if audio_info:
                    structure.update(audio_info)

                log.info(
                    "speech_recognition succeeded",
                    filename=raw.filename,
                    text_length=len(text),
                )
                return [ExtractedContent(
                    text=text,
                    structure=structure,
                    metadata={**base_metadata, **audio_info},
                    confidence=0.7,
                )]
            else:
                log.debug("speech_recognition returned empty text", filename=raw.filename)
        except ImportError:
            log.debug("speech_recognition not available, falling back to metadata-only")
        except Exception as exc:
            log.warning("speech_recognition failed", error=str(exc))

        # ── Metadata-only fallback ──
        meta_lines = [f"Audio: {raw.filename} ({raw.size_bytes} bytes)"]
        if audio_info.get("duration_seconds") is not None:
            meta_lines.append(f"Duration: {audio_info['duration_seconds']:.1f}s")
        if audio_info.get("sample_rate"):
            meta_lines.append(f"Sample rate: {audio_info['sample_rate']} Hz")
        if audio_info.get("channels"):
            meta_lines.append(f"Channels: {audio_info['channels']}")

        structure = {"type": "audio", "extraction_method": "metadata_only"}
        if audio_info:
            structure.update(audio_info)

        log.debug("Returning metadata-only for audio", filename=raw.filename)
        return [ExtractedContent(
            text="\n".join(meta_lines),
            structure=structure,
            metadata={**base_metadata, **audio_info},
            confidence=0.3,
        )]

    @staticmethod
    def _extract_audio_info(raw: RawContent, log: object) -> dict:
        """Try to extract duration, sample rate, and channels from audio bytes."""
        info: dict = {}

        # Try mutagen first (handles many formats)
        try:
            from mutagen import File as MutagenFile

            ext = (raw.extension or "").lower().lstrip(".")
            suffix = f".{ext}" if ext else ".mp3"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
                tmp.write(raw.data)
                tmp.flush()
                audio = MutagenFile(tmp.name)
                if audio is not None and audio.info is not None:
                    if hasattr(audio.info, "length") and audio.info.length:
                        info["duration_seconds"] = round(audio.info.length, 2)
                    if hasattr(audio.info, "sample_rate") and audio.info.sample_rate:
                        info["sample_rate"] = audio.info.sample_rate
                    if hasattr(audio.info, "channels") and audio.info.channels:
                        info["channels"] = audio.info.channels
            return info
        except ImportError:
            pass
        except Exception:
            pass

        # Try pydub
        try:
            from pydub import AudioSegment

            ext = (raw.extension or "").lower().lstrip(".")
            fmt = ext if ext in ("mp3", "wav", "ogg", "flac") else "mp3"
            audio_seg = AudioSegment.from_file(BytesIO(raw.data), format=fmt)
            info["duration_seconds"] = round(len(audio_seg) / 1000.0, 2)
            info["sample_rate"] = audio_seg.frame_rate
            info["channels"] = audio_seg.channels
            return info
        except ImportError:
            pass
        except Exception:
            pass

        return info
