"""Schema-guided extraction — ontology-constrained entity/relationship extraction.

Loads domain schemas from YAML files, constrains LLM extraction to allowed types.
Validates output against schema. Used for regulated domains: legal, medical, financial.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import structlog
import yaml

from omnirag.graphrag.models import EntityMention

logger = structlog.get_logger(__name__)

SCHEMAS_DIR = Path(__file__).parent / "schemas"


class ExtractionSchema:
    """Loaded domain schema for constrained extraction."""

    def __init__(self, name: str = "default") -> None:
        self.name = name
        self.entity_types: list[str] = []
        self.relationship_types: list[str] = []
        self.constraints: str = ""
        self._load(name)

    def _load(self, name: str) -> None:
        path = SCHEMAS_DIR / f"{name}.yaml"
        if not path.exists():
            path = SCHEMAS_DIR / "default.yaml"
        if not path.exists():
            logger.warning("schema.not_found", name=name)
            return
        with open(path) as f:
            data = yaml.safe_load(f)
        self.name = data.get("name", name)
        self.entity_types = data.get("entity_types", [])
        self.relationship_types = data.get("relationship_types", [])
        self.constraints = data.get("constraints", "")

    def validate_entity(self, entity_type: str) -> bool:
        """Check if an entity type is allowed by this schema."""
        if not self.entity_types:
            return True
        return entity_type in self.entity_types

    def validate_relationship(self, rel_type: str) -> bool:
        """Check if a relationship type is allowed."""
        if not self.relationship_types:
            return True
        return rel_type in self.relationship_types

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "entity_types": self.entity_types,
            "relationship_types": self.relationship_types,
            "constraints": self.constraints,
        }


def list_schemas() -> list[str]:
    """List available domain schemas."""
    if not SCHEMAS_DIR.exists():
        return []
    return [f.stem for f in SCHEMAS_DIR.glob("*.yaml")]


def get_schema(name: str = "default") -> ExtractionSchema:
    return ExtractionSchema(name)


def validate_extractions(mentions: list[EntityMention], schema: ExtractionSchema) -> list[EntityMention]:
    """Filter extractions to only those conforming to the schema."""
    if not schema.entity_types:
        return mentions
    valid = [m for m in mentions if schema.validate_entity(m.entity_type)]
    filtered = len(mentions) - len(valid)
    if filtered > 0:
        logger.info("schema.filtered", schema=schema.name, filtered=filtered, kept=len(valid))
    return valid
