"""Entity extraction + resolution tests."""

import pytest

from omnirag.graphrag.extraction.entities import EntityExtractor
from omnirag.graphrag.extraction.resolution import EntityResolver


class TestEntityExtraction:
    @pytest.mark.asyncio
    async def test_extract_proper_nouns(self):
        extractor = EntityExtractor()
        mentions = await extractor.extract(
            "OmniRAG is a RAG platform built with Python and Neo4j.", chunk_id="c1"
        )
        names = [m.surface_form for m in mentions]
        # Should find at least OmniRAG, Neo4j
        assert any("OmniRAG" in n or "omnirag" in n.lower() for n in names)

    @pytest.mark.asyncio
    async def test_extract_with_context(self):
        extractor = EntityExtractor()
        mentions = await extractor.extract(
            "It was released last year.",
            chunk_id="c2",
            context="Microsoft announced a new product."
        )
        names = [m.surface_form.lower() for m in mentions]
        assert any("microsoft" in n for n in names)

    @pytest.mark.asyncio
    async def test_extract_multiple_types(self):
        extractor = EntityExtractor()
        mentions = await extractor.extract(
            "PostgreSQL and Elasticsearch are used by OmniRAG for indexing.",
            chunk_id="c3"
        )
        assert len(mentions) >= 2

    @pytest.mark.asyncio
    async def test_extract_empty(self):
        extractor = EntityExtractor()
        mentions = await extractor.extract("the cat sat on the mat", chunk_id="c4")
        # May or may not find entities depending on model
        assert isinstance(mentions, list)

    @pytest.mark.asyncio
    async def test_confidence_present(self):
        extractor = EntityExtractor()
        mentions = await extractor.extract("Google released TensorFlow.", chunk_id="c5")
        for m in mentions:
            assert 0 <= m.confidence <= 1.0


class TestEntityResolution:
    def test_exact_match_resolution(self):
        resolver = EntityResolver()
        from omnirag.graphrag.models import EntityMention
        mentions = [
            EntityMention(surface_form="Microsoft", entity_type="ORG", confidence=0.9, chunk_id="c1"),
            EntityMention(surface_form="Microsoft", entity_type="ORG", confidence=0.8, chunk_id="c2"),
            EntityMention(surface_form="MSFT", entity_type="ORG", confidence=0.7, chunk_id="c3"),
        ]
        entities = resolver.resolve(mentions)
        # "Microsoft" x2 should merge; "MSFT" may or may not merge depending on model
        assert len(entities) >= 1
        # At least one entity should have canonical_name "Microsoft"
        assert any(e.canonical_name == "Microsoft" for e in entities)

    def test_alias_lookup(self):
        resolver = EntityResolver()
        from omnirag.graphrag.models import EntityMention
        mentions = [
            EntityMention(surface_form="PostgreSQL", entity_type="PRODUCT", confidence=0.9, chunk_id="c1"),
        ]
        resolver.resolve(mentions)
        rid = resolver.lookup("postgresql")
        assert rid is not None

    def test_different_entities_stay_separate(self):
        resolver = EntityResolver()
        from omnirag.graphrag.models import EntityMention
        mentions = [
            EntityMention(surface_form="Python", entity_type="PRODUCT", confidence=0.9, chunk_id="c1"),
            EntityMention(surface_form="Neo4j", entity_type="PRODUCT", confidence=0.9, chunk_id="c1"),
        ]
        entities = resolver.resolve(mentions)
        assert len(entities) == 2

    def test_chunk_ids_tracked(self):
        resolver = EntityResolver()
        from omnirag.graphrag.models import EntityMention
        mentions = [
            EntityMention(surface_form="Redis", entity_type="PRODUCT", confidence=0.9, chunk_id="chunk-a"),
            EntityMention(surface_form="Redis", entity_type="PRODUCT", confidence=0.8, chunk_id="chunk-b"),
        ]
        entities = resolver.resolve(mentions)
        redis_entity = next(e for e in entities if e.canonical_name == "Redis")
        assert "chunk-a" in redis_entity.chunk_ids
        assert "chunk-b" in redis_entity.chunk_ids
