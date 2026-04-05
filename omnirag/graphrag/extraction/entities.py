"""Entity extraction — 4 modes: regex, LLM, schema, hybrid.

Tier 1: LLM (Ollama/OpenAI) — highest quality, prompted extraction
Tier 2: spaCy NER — medium quality, no LLM needed
Tier 3: Regex patterns — lowest quality, always available
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog

from omnirag.graphrag.models import EntityMention
from omnirag.graphrag.extraction.prompts import ENTITY_EXTRACTION_PROMPT, SCHEMA_EXTRACTION_PROMPT
from omnirag.models.canonical import Extraction

logger = structlog.get_logger(__name__)

# Regex patterns for fallback NER
PATTERNS = {
    "ORG": re.compile(r'\b(?:Inc|Corp|LLC|Ltd|Company|Foundation|Institute|University|Organization)\b', re.I),
    "PERSON": re.compile(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b'),
    "PRODUCT": re.compile(r'\b(?:v\d+\.\d+|[A-Z][a-zA-Z]*(?:DB|AI|ML|API|SDK|CLI))\b'),
    "PROJECT": re.compile(r'\b(?:OmniRAG|OmniGraph|GraphRAG|OpenCode|Neo4j|Qdrant|Elasticsearch|PostgreSQL|Redis|LangGraph|AutoGen)\b', re.I),
}
PROPER_NOUN = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b')


class EntityExtractor:
    """Extracts entities using configurable mode: regex | llm | schema | hybrid."""

    def __init__(self) -> None:
        self._nlp: Any = None
        self._spacy_available = False

    def _load_spacy(self) -> Any:
        if self._nlp is not None:
            return self._nlp
        try:
            import spacy
            self._nlp = spacy.load("en_core_web_sm")
            self._spacy_available = True
            return self._nlp
        except (ImportError, OSError):
            self._spacy_available = False
            return None

    async def extract(self, text: str, chunk_id: str, context: str = "",
                      mode: str = "hybrid", schema: dict | None = None) -> list[EntityMention]:
        """Extract entities using the specified mode."""
        if mode == "llm":
            return await self._extract_llm(text, chunk_id, context)
        elif mode == "schema":
            return await self._extract_schema(text, chunk_id, schema or {})
        elif mode == "regex":
            return self._extract_regex(text, chunk_id, context)
        elif mode == "hybrid":
            return await self._extract_hybrid(text, chunk_id, context, schema)
        return self._extract_regex(text, chunk_id, context)

    async def _extract_hybrid(self, text: str, chunk_id: str, context: str = "",
                              schema: dict | None = None) -> list[EntityMention]:
        """Hybrid: try LLM first → spaCy → regex."""
        # Try LLM
        llm_results = await self._extract_llm(text, chunk_id, context)
        if llm_results:
            # If schema provided, validate against it
            if schema:
                allowed_types = set(schema.get("entity_types", []))
                if allowed_types:
                    llm_results = [m for m in llm_results if m.entity_type in allowed_types]
            return llm_results

        # Fallback to spaCy
        spacy_results = self._extract_spacy(text, chunk_id, context)
        if spacy_results:
            return spacy_results

        # Final fallback: regex
        return self._extract_regex(text, chunk_id, context)

    async def _extract_llm(self, text: str, chunk_id: str, context: str = "") -> list[EntityMention]:
        """LLM-powered extraction via Ollama or OpenAI."""
        try:
            from omnirag.output.generation.engine import get_generation_engine

            engine = get_generation_engine()
            if engine.get_adapter_name() == "fallback":
                return []

            full_text = (context + "\n" + text).strip() if context else text
            prompt = ENTITY_EXTRACTION_PROMPT.format(text=full_text[:3000])

            result = await engine.generate(prompt, [])

            # Parse JSON from LLM response
            return self._parse_llm_entities(result.answer, chunk_id)
        except Exception as e:
            logger.warning("entity_extraction.llm_failed", error=str(e))
            return []

    def _parse_llm_entities(self, response: str, chunk_id: str) -> list[EntityMention]:
        """Parse LLM JSON response into EntityMention objects."""
        mentions = []
        try:
            # Find JSON array in response
            start = response.find("[")
            end = response.rfind("]") + 1
            if start == -1 or end == 0:
                return []
            raw = json.loads(response[start:end])
            for item in raw:
                if isinstance(item, dict) and "name" in item:
                    mentions.append(EntityMention(
                        surface_form=item["name"],
                        entity_type=item.get("type", "ENTITY"),
                        confidence=float(item.get("confidence", 0.8)),
                        chunk_id=chunk_id,
                    ))
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("entity_extraction.parse_failed", error=str(e))
        return _deduplicate(mentions)

    async def _extract_schema(self, text: str, chunk_id: str, schema: dict) -> list[EntityMention]:
        """Schema-guided extraction: LLM constrained to allowed types."""
        try:
            from omnirag.output.generation.engine import get_generation_engine

            engine = get_generation_engine()
            if engine.get_adapter_name() == "fallback":
                return self._extract_regex(text, chunk_id, "")

            entity_types = ", ".join(schema.get("entity_types", ["PERSON", "ORG", "PRODUCT"]))
            rel_types = ", ".join(schema.get("relationship_types", ["RELATED_TO"]))
            constraints = schema.get("constraints", "No additional constraints")

            prompt = SCHEMA_EXTRACTION_PROMPT.format(
                entity_types=entity_types, relationship_types=rel_types,
                constraints=constraints, text=text[:3000],
            )

            result = await engine.generate(prompt, [])

            return self._parse_llm_entities(result.answer, chunk_id)
        except Exception as e:
            logger.warning("entity_extraction.schema_failed", error=str(e))
            return self._extract_regex(text, chunk_id, "")

    def _extract_spacy(self, text: str, chunk_id: str, context: str = "") -> list[EntityMention]:
        """spaCy NER extraction."""
        nlp = self._load_spacy()
        if not nlp:
            return []
        full_text = (context + " " + text).strip() if context else text
        doc = nlp(full_text)
        mentions = []
        for ent in doc.ents:
            if ent.label_ in ("PERSON", "ORG", "GPE", "PRODUCT", "WORK_OF_ART", "EVENT", "LAW"):
                mentions.append(EntityMention(
                    surface_form=ent.text.strip(), entity_type=ent.label_,
                    confidence=0.85, chunk_id=chunk_id,
                    start_char=ent.start_char, end_char=ent.end_char,
                ))
        return _deduplicate(mentions)

    def _extract_regex(self, text: str, chunk_id: str, context: str = "") -> list[EntityMention]:
        """Regex pattern matching fallback."""
        full_text = (context + " " + text).strip() if context else text
        mentions = []
        seen: set[str] = set()
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
