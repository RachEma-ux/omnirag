"""Template-based community reports — Tier 3 fallback when no LLM available."""

from __future__ import annotations

from omnirag.graphrag.models import GraphEntity, GraphRelationship, CommunityReport, GraphCommunity


def generate_template_report(
    community: GraphCommunity,
    entities: list[GraphEntity],
    relationships: list[GraphRelationship],
) -> CommunityReport:
    """Generate a structured report using templates (no LLM needed).

    Quality score: 0.4 (vs 1.0 for LLM, 0.7 for local model).
    """
    if not entities:
        return CommunityReport(
            community_id=community.community_id,
            summary="Empty community with no entities.",
            acl_principals=community.acl_principals,
        )

    # Sort entities by connection count
    entity_connections: dict[str, int] = {}
    for rel in relationships:
        entity_connections[rel.source_id] = entity_connections.get(rel.source_id, 0) + 1
        entity_connections[rel.target_id] = entity_connections.get(rel.target_id, 0) + 1

    sorted_entities = sorted(entities, key=lambda e: entity_connections.get(e.resolved_id, 0), reverse=True)
    top_entity = sorted_entities[0]

    # Entity list
    entity_lines = []
    for e in sorted_entities[:10]:
        conn = entity_connections.get(e.resolved_id, 0)
        line = f"  - {e.canonical_name} ({e.entity_type})"
        if e.aliases:
            line += f" — also known as: {', '.join(e.aliases[:3])}"
        if conn > 0:
            line += f" [{conn} connections]"
        entity_lines.append(line)

    # Strongest relationships
    sorted_rels = sorted(relationships, key=lambda r: r.weight, reverse=True)
    rel_lines = []
    entity_map = {e.resolved_id: e.canonical_name for e in entities}
    for rel in sorted_rels[:5]:
        src = entity_map.get(rel.source_id, rel.source_id[:8])
        tgt = entity_map.get(rel.target_id, rel.target_id[:8])
        rel_lines.append(f"  - {src} → {tgt} (weight: {rel.weight:.1f}, type: {rel.relation_type})")

    # Build summary
    parts = [
        f"Community: {community.community_id[:8]}",
        f"Level: {community.level}",
        f"",
        f"Theme: This community centers around {top_entity.canonical_name} ({top_entity.entity_type}) "
        f"and {len(entities) - 1} related entities.",
        f"",
        f"Key entities ({len(entities)}):",
    ]
    parts.extend(entity_lines)

    if rel_lines:
        parts.append(f"")
        parts.append(f"Key relationships ({len(relationships)}):")
        parts.extend(rel_lines)

    if len(entities) > 10:
        parts.append(f"")
        parts.append(f"... and {len(entities) - 10} more entities.")

    parts.append(f"")
    strongest = sorted_rels[0] if sorted_rels else None
    if strongest:
        src = entity_map.get(strongest.source_id, "?")
        tgt = entity_map.get(strongest.target_id, "?")
        parts.append(f"The strongest relationship is between {src} and {tgt} (weight {strongest.weight:.1f}).")

    summary = "\n".join(parts)

    return CommunityReport(
        community_id=community.community_id,
        summary=summary,
        acl_principals=community.acl_principals,
    )
