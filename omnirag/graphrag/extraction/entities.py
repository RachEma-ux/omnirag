"""Entity extraction — spaCy NER with regex fallback."""

from __future__ import annotations

import re
from typing import Any

import structlog

from omnirag.graphrag.models import EntityMention

logger = structlog.get_logger(__name__)

# Regex patterns for fallback NER
PATTERNS = {
    "ORG": re.compile(r'\b(?:Inc|Corp|LLC|Ltd|Company|Foundation|Institute|University|Organization)\b', re.I),
    "PERSON": re.compile(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b'),
    "PRODUCT": re.compile(r'\b(?:v\d+\.\d+|[A-Z][a-zA-Z]*(?:DB|AI|ML|API|SDK|CLI))\b'),
    "PROJECT": re.compile(r'\b(?:OmniRAG|GraphRAG|OpenCode|Neo4j|Qdrant|Elasticsearch|PostgreSQL|Redis)\b', re.I),
}

# Capitalized multi-word proper nouns
PROPER_NOUN = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b')


class EntityExtractor:
    """Extracts entities from text using spaCy or regex fallback."""

    def __init__(self) -> None:
        self._nlp: Any = None
        self._use_fallback = True

    def _load_model(self) -> Any:
        if self._nlp is not None:
            return self._nlp
        try:
            import spacy
            self._nlp = spacy.load("en_core_web_sm")
            self._use_fallback = False
            return self._nlp
        except (ImportError, OSError):
            logger.warning("entity_extraction.no_spacy", msg="using regex fallback")
            self._use_fallback = True
            return None

    def extract(self, text: str, chunk_id: str, context: str = "") -> list[EntityMention]:
        """Extract entity mentions from text."""
        full_text = (context + " " + text).strip() if context else text
        mentions: list[EntityMention] = []

        nlp = self._load_model()
        if nlp and not self._use_fallback:
            doc = nlp(full_text)
            for ent in doc.ents:
                if ent.label_ in ("PERSON", "ORG", "GPE", "PRODUCT", "WORK_OF_ART", "EVENT", "LAW"):
                    mentions.append(EntityMention(
                        surface_form=ent.text.strip(),
                        entity_type=ent.label_,
                        confidence=0.85,
                        chunk_id=chunk_id,
                        start_char=ent.start_char,
                        end_char=ent.end_char,
                    ))
            return _deduplicate(mentions)

        # Regex fallback
        seen = set()
        for etype, pattern in PATTERNS.items():
            for match in pattern.finditer(full_text):
                surface = match.group().strip()
                if len(surface) < 2 or surface.lower() in seen:
                    continue
                seen.add(surface.lower())
                mentions.append(EntityMention(
                    surface_form=surface, entity_type=etype, confidence=0.6,
                    chunk_id=chunk_id, start_char=match.start(), end_char=match.end(),
                ))

        # Proper nouns
        for match in PROPER_NOUN.finditer(full_text):
            surface = match.group().strip()
            if surface.lower() in seen or len(surface) < 4:
                continue
            seen.add(surface.lower())
            mentions.append(EntityMention(
                surface_form=surface, entity_type="ENTITY", confidence=0.5,
                chunk_id=chunk_id, start_char=match.start(), end_char=match.end(),
            ))

        return _deduplicate(mentions)


def _deduplicate(mentions: list[EntityMention]) -> list[EntityMention]:
    seen: dict[str, EntityMention] = {}
    for m in mentions:
        key = m.surface_form.lower()
        if key not in seen or m.confidence > seen[key].confidence:
            seen[key] = m
    return list(seen.values())


_extractor = EntityExtractor()


def get_entity_extractor() -> EntityExtractor:
    return _extractor
