"""Extraction prompt templates — entity, relationship, verification, community report."""

ENTITY_EXTRACTION_PROMPT = """Extract ALL entities from the following text.
For each entity, provide:
- name: the entity name (proper noun form)
- type: one of PERSON, ORG, PRODUCT, PROJECT, LOCATION, EVENT, CONCEPT, REGULATORY_TERM
- description: one sentence describing the entity in the context of this text
- confidence: 0.0 to 1.0

Text:
{text}

Return as a JSON array. Example:
[{{"name": "OmniRAG", "type": "PROJECT", "description": "A RAG control plane for knowledge management", "confidence": 0.95}}]

Entities:"""

RELATIONSHIP_EXTRACTION_PROMPT = """Extract ALL relationships between entities in the following text.
For each relationship, provide:
- source: source entity name
- target: target entity name
- relation_type: one of USES, DEPENDS_ON, INTEGRATES_WITH, SUPPORTS, CONTRADICTS, REGULATES, REPORTS_TO, PRODUCES, CONSUMES, RELATED_TO
- description: one sentence describing the relationship
- weight: 1 to 5 (strength of relationship in this context)

Text:
{text}

Return as a JSON array. Example:
[{{"source": "OmniRAG", "target": "Neo4j", "relation_type": "INTEGRATES_WITH", "description": "OmniRAG uses Neo4j as its graph store for entity-relationship reasoning", "weight": 4}}]

Relationships:"""

ENTITY_VERIFICATION_PROMPT = """Are these entities referring to the same real-world entity?

Entity A: {entity_a_name} (type: {entity_a_type})
  Context: {entity_a_context}

Entity B: {entity_b_name} (type: {entity_b_type})
  Context: {entity_b_context}

Answer with ONLY one of:
- SAME: They are the same entity
- DIFFERENT: They are different entities
- UNCERTAIN: Not enough information to decide

Answer:"""

COMMUNITY_REPORT_PROMPT = """You are an AI analyst. Given the following list of entities and their relationships in this community, write a concise community report (max 300 words) covering:

1. Main theme or function of this community
2. Key entities and their roles
3. Important relationships and patterns
4. Supporting evidence from text chunks
5. Any risks or opportunities mentioned

Entities:
{entities}

Relationships:
{relationships}

Evidence chunks:
{evidence}

Report:"""

SCHEMA_EXTRACTION_PROMPT = """Extract entities and relationships from the text, following ONLY the schema below.

Allowed entity types: {entity_types}
Allowed relationship types: {relationship_types}
Constraints: {constraints}

Text:
{text}

Return as JSON with "entities" and "relationships" arrays, conforming strictly to the schema.

Extraction:"""
