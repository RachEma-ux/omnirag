"""Demo: Full pipeline on A Christmas Carol — intake → index → graph → query.

Run: python -m omnirag.demo
"""

from __future__ import annotations

import asyncio

async def run_demo():
    from omnirag.intake.gate import get_gate
    from omnirag.output.index_writers.base import get_writer_registry
    from omnirag.output.index_writers.vector import VectorIndexWriter
    from omnirag.output.index_writers.keyword import KeywordIndexWriter
    from omnirag.output.index_writers.metadata import MetadataIndexWriter
    from omnirag.output.embedding import get_embedding_pipeline
    from omnirag.graphrag.projection import get_projection_service
    from omnirag.graphrag.store import get_graph_store

    # Register intake defaults (connectors + extractors + materializers + chunkers)
    from omnirag.intake.defaults import register_defaults as register_intake
    register_intake()

    # Ensure index writers registered
    registry = get_writer_registry()
    if not registry.names():
        registry.register(VectorIndexWriter())
        registry.register(KeywordIndexWriter())
        registry.register(MetadataIndexWriter())

    # Connect graph store
    await get_graph_store().connect()

    # 1. Ingest
    print("=== 1. Ingesting A Christmas Carol ===")
    gate = get_gate()
    job = await gate.ingest("/data/data/com.termux/files/usr/tmp/christmas_carol.txt", {})
    print(f"  State: {job.state.value}")
    print(f"  Files: {job.files_found}, Docs: {job.documents_created}, Chunks: {job.chunks_created}")

    # Get chunks from gate
    chunks = gate.get_chunks(job.id)
    docs = gate.get_documents(job.id)
    print(f"  Chunks in memory: {len(chunks)}")

    if not chunks:
        print("  No chunks — aborting demo")
        return

    # 2. Embed + Index
    print("\n=== 2. Embedding + Indexing ===")
    pipeline = get_embedding_pipeline()
    results = await pipeline.embed_chunks(chunks)
    completed = [r for r in results if r.status == "completed"]
    print(f"  Embedded: {len(completed)} chunks")

    for writer in registry.all():
        count = await writer.write(chunks, results)
        print(f"  {writer.name}: wrote {count} chunks")

    # 3. Graph projection
    print("\n=== 3. Graph Projection (entities + relationships + communities) ===")
    projector = get_projection_service()
    stats = await projector.project(docs, chunks)
    print(f"  Entities: {stats['entities']}")
    print(f"  Relationships: {stats['relationships']}")
    print(f"  Communities: {stats['communities']}")
    print(f"  Reports: {stats['reports']}")

    store = get_graph_store()
    print(f"\n=== Graph Store ===")
    print(f"  {store.stats()}")

    # 4. Test searches
    print("\n=== 4. Test Searches ===")

    # Keyword search
    kw = registry.get("keyword")
    if kw:
        results = await kw.search(None, "Scrooge", ["public"], top_k=3)
        print(f"  Keyword 'Scrooge': {len(results)} results")
        for r in results[:2]:
            print(f"    - {r.get('payload', {}).get('content', r.get('payload', {}).get('text', ''))[:80]}...")

    # Vector search
    vec = registry.get("vector")
    if vec and completed:
        # Use first chunk's embedding as query
        qvec = completed[0].vector
        results = await vec.search(qvec, None, ["public"], top_k=3)
        print(f"  Vector: {len(results)} results")

    # Entity lookup
    entities = store.get_all_entities()
    print(f"\n=== Entities ({len(entities)}) ===")
    for e in entities[:10]:
        print(f"  {e.canonical_name} ({e.entity_type}) — aliases: {e.aliases[:3]}")

    # Communities
    communities = store.get_all_communities()
    print(f"\n=== Communities ({len(communities)}) ===")
    for c in communities[:5]:
        print(f"  {c.community_id[:8]} — {len(c.entity_ids)} entities, level {c.level}")

    # Reports
    reports = await store.get_community_reports()
    print(f"\n=== Reports ({len(reports)}) ===")
    for r in reports[:3]:
        print(f"  {r.community_id[:8]}: {r.summary[:100]}...")

    print("\n=== Demo Complete ===")
    print(f"Pipeline: intake → 71 chunks → {len(completed)} embeddings → {stats['entities']} entities → {stats['communities']} communities")
    print("Open http://127.0.0.1:8100/ → Visualization tab → the graph is populated")


if __name__ == "__main__":
    asyncio.run(run_demo())
