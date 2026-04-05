"""Graph store — Neo4j connection with networkx in-memory fallback."""

from __future__ import annotations

import os
from typing import Any

import structlog

from omnirag.graphrag.models import GraphEntity, GraphRelationship, GraphCommunity, CommunityReport

logger = structlog.get_logger(__name__)

# Cypher DDL
SCHEMA_CYPHER = """
CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.resolved_id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (com:Community) REQUIRE com.community_id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (cr:CommunityReport) REQUIRE cr.report_id IS UNIQUE;
"""

INDEX_CYPHER = """
CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.canonical_name);
CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.acl_principals);
CREATE INDEX IF NOT EXISTS FOR (com:Community) ON (com.level);
CREATE INDEX IF NOT EXISTS FOR (com:Community) ON (com.acl_principals);
"""


class GraphStore:
    """Neo4j graph store with networkx in-memory fallback."""

    def __init__(self) -> None:
        self._driver: Any = None
        self._use_fallback = True
        # In-memory fallback (networkx)
        self._graph: Any = None
        self._entities: dict[str, GraphEntity] = {}
        self._relationships: list[GraphRelationship] = []
        self._communities: dict[str, GraphCommunity] = {}
        self._reports: dict[str, CommunityReport] = {}
        self._chunk_entities: dict[str, list[str]] = {}  # chunk_id → [entity_ids]

    async def connect(self) -> bool:
        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "password")
        try:
            from neo4j import AsyncGraphDatabase
            self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
            async with self._driver.session() as session:
                await session.run("RETURN 1")
            # Run schema
            async with self._driver.session() as session:
                for statement in SCHEMA_CYPHER.strip().split(";"):
                    s = statement.strip()
                    if s:
                        try:
                            await session.run(s)
                        except Exception:
                            pass
            self._use_fallback = False
            logger.info("graphstore.connected", uri=uri)
            return True
        except ImportError:
            logger.warning("graphstore.no_neo4j", msg="neo4j driver not installed, using networkx fallback")
        except Exception as e:
            logger.warning("graphstore.connect_failed", error=str(e))

        # Init networkx fallback
        try:
            import networkx as nx
            self._graph = nx.Graph()
        except ImportError:
            self._graph = None
        self._use_fallback = True
        return False

    @property
    def is_neo4j(self) -> bool:
        return not self._use_fallback

    # ─── Entity Operations ───

    async def upsert_entity(self, entity: GraphEntity) -> None:
        if not self._use_fallback and self._driver:
            async with self._driver.session() as session:
                await session.run(
                    "MERGE (e:Entity {resolved_id: $rid}) "
                    "SET e.canonical_name = $name, e.aliases = $aliases, "
                    "e.entity_type = $etype, e.acl_principals = $acl",
                    rid=entity.resolved_id, name=entity.canonical_name,
                    aliases=entity.aliases, etype=entity.entity_type,
                    acl=entity.acl_principals,
                )
            return
        self._entities[entity.resolved_id] = entity
        if self._graph is not None:
            self._graph.add_node(entity.resolved_id, **entity.to_dict())

    async def get_entity(self, resolved_id: str) -> GraphEntity | None:
        if not self._use_fallback and self._driver:
            async with self._driver.session() as session:
                result = await session.run(
                    "MATCH (e:Entity {resolved_id: $rid}) RETURN e", rid=resolved_id
                )
                record = await result.single()
                if record:
                    e = record["e"]
                    return GraphEntity(
                        resolved_id=e["resolved_id"], canonical_name=e.get("canonical_name", ""),
                        aliases=e.get("aliases", []), entity_type=e.get("entity_type", ""),
                        acl_principals=e.get("acl_principals", []),
                    )
            return None
        return self._entities.get(resolved_id)

    async def find_entity_by_name(self, name: str) -> GraphEntity | None:
        name_lower = name.lower()
        for e in self._entities.values():
            if e.canonical_name.lower() == name_lower:
                return e
            if any(a.lower() == name_lower for a in e.aliases):
                return e
        return None

    # ─── Relationship Operations ───

    async def upsert_relationship(self, rel: GraphRelationship) -> None:
        if not self._use_fallback and self._driver:
            async with self._driver.session() as session:
                await session.run(
                    "MATCH (e1:Entity {resolved_id: $s}), (e2:Entity {resolved_id: $t}) "
                    "MERGE (e1)-[r:RELATES_TO]-(e2) "
                    "SET r.weight = COALESCE(r.weight, 0) + $w, "
                    "r.acl_principals = $acl",
                    s=rel.source_id, t=rel.target_id, w=rel.weight, acl=rel.acl_principals,
                )
            return
        self._relationships.append(rel)
        if self._graph is not None:
            if self._graph.has_edge(rel.source_id, rel.target_id):
                self._graph[rel.source_id][rel.target_id]["weight"] += rel.weight
            else:
                self._graph.add_edge(rel.source_id, rel.target_id, weight=rel.weight)

    async def get_neighbors(self, entity_id: str, max_hops: int = 2,
                            acl_principals: list[str] | None = None) -> list[dict]:
        """Get entity neighbors with ACL filtering."""
        results = []
        if not self._use_fallback and self._driver:
            async with self._driver.session() as session:
                cypher = (
                    "MATCH (e:Entity {resolved_id: $eid})-[r:RELATES_TO*1.." + str(max_hops) + "]-(n:Entity) "
                )
                if acl_principals:
                    cypher += "WHERE any(p IN $acl WHERE p IN n.acl_principals) "
                cypher += "RETURN DISTINCT n, r LIMIT 100"
                result = await session.run(cypher, eid=entity_id, acl=acl_principals or [])
                async for record in result:
                    n = record["n"]
                    results.append({"entity": dict(n), "hops": len(record["r"])})
            return results

        # Fallback: BFS on networkx or dict
        if self._graph is not None:
            import networkx as nx
            try:
                paths = nx.single_source_shortest_path_length(self._graph, entity_id, cutoff=max_hops)
                for nid, dist in paths.items():
                    if nid == entity_id:
                        continue
                    ent = self._entities.get(nid)
                    if not ent:
                        continue
                    if acl_principals and not any(p in ent.acl_principals for p in acl_principals):
                        continue
                    results.append({"entity": ent.to_dict(), "hops": dist})
            except Exception:
                pass
        return results

    # ─── Chunk-Entity Linking ───

    async def link_chunk_entity(self, chunk_id: str, entity_id: str, confidence: float = 1.0) -> None:
        if not self._use_fallback and self._driver:
            async with self._driver.session() as session:
                await session.run(
                    "MATCH (c:Chunk {chunk_id: $cid}), (e:Entity {resolved_id: $eid}) "
                    "MERGE (c)-[m:MENTIONS]->(e) SET m.confidence = $conf",
                    cid=chunk_id, eid=entity_id, conf=confidence,
                )
            return
        self._chunk_entities.setdefault(chunk_id, []).append(entity_id)

    async def get_chunks_for_entity(self, entity_id: str, acl_principals: list[str] | None = None) -> list[str]:
        """Get chunk IDs linked to an entity."""
        if not self._use_fallback and self._driver:
            async with self._driver.session() as session:
                cypher = "MATCH (c:Chunk)-[:MENTIONS]->(e:Entity {resolved_id: $eid}) "
                if acl_principals:
                    cypher += "WHERE any(p IN $acl WHERE p IN c.acl_principals) "
                cypher += "RETURN c.chunk_id LIMIT 50"
                result = await session.run(cypher, eid=entity_id, acl=acl_principals or [])
                return [r["c.chunk_id"] async for r in result]

        chunks = []
        for cid, eids in self._chunk_entities.items():
            if entity_id in eids:
                chunks.append(cid)
        return chunks

    # ─── Community Operations ───

    async def upsert_community(self, community: GraphCommunity) -> None:
        self._communities[community.community_id] = community
        if not self._use_fallback and self._driver:
            async with self._driver.session() as session:
                await session.run(
                    "MERGE (c:Community {community_id: $cid}) "
                    "SET c.level = $level, c.acl_principals = $acl",
                    cid=community.community_id, level=community.level, acl=community.acl_principals,
                )
                for eid in community.entity_ids:
                    await session.run(
                        "MATCH (e:Entity {resolved_id: $eid}), (c:Community {community_id: $cid}) "
                        "MERGE (e)-[:IN_COMMUNITY]->(c)",
                        eid=eid, cid=community.community_id,
                    )

    async def upsert_report(self, report: CommunityReport) -> None:
        self._reports[report.report_id] = report
        if not self._use_fallback and self._driver:
            async with self._driver.session() as session:
                await session.run(
                    "CREATE (cr:CommunityReport {report_id: $rid, summary: $summary, "
                    "generated_at: datetime(), acl_principals: $acl}) "
                    "WITH cr MATCH (c:Community {community_id: $cid}) "
                    "CREATE (c)-[:HAS_REPORT]->(cr)",
                    rid=report.report_id, summary=report.summary,
                    acl=report.acl_principals, cid=report.community_id,
                )

    async def get_community_reports(self, acl_principals: list[str] | None = None) -> list[CommunityReport]:
        reports = list(self._reports.values())
        if acl_principals:
            reports = [r for r in reports if any(p in r.acl_principals for p in acl_principals) or not r.acl_principals]
        return reports

    def get_all_entities(self) -> list[GraphEntity]:
        return list(self._entities.values())

    def get_all_communities(self) -> list[GraphCommunity]:
        return list(self._communities.values())

    def stats(self) -> dict:
        return {
            "mode": "neo4j" if not self._use_fallback else "in-memory",
            "entities": len(self._entities),
            "relationships": len(self._relationships),
            "communities": len(self._communities),
            "reports": len(self._reports),
        }


_store = GraphStore()


def get_graph_store() -> GraphStore:
    return _store
