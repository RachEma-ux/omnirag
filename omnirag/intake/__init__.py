"""OmniRAG Universal Intake Gate — governed control plane for all sources and formats.

Architecture:
  Source URI → Connector (discover/fetch/permissions) → RawContent
  RawContent → FormatDetector → Extractor → ExtractedContent
  ExtractedContent → Materializer → CanonicalDocument
  CanonicalDocument → Chunker → Chunk[]
  All stages: ACL binding, lineage tracking, backpressure control

12-state pipeline:
  REGISTERED → DISCOVERED → AUTHORIZED → FETCHED → EXTRACTED →
  MATERIALIZED → ENRICHED → ACL_BOUND → CHUNKED → INDEXED → VERIFIED → ACTIVE
"""

from omnirag.intake.gate import IntakeGate, get_gate
from omnirag.intake.models import (
    ACL, CanonicalDocument, Chunk, ConnectorConfig, ExtractedContent,
    JobState, RawContent, SourceObject, SyncJob,
)

__all__ = [
    "IntakeGate", "get_gate",
    "ACL", "CanonicalDocument", "Chunk", "ConnectorConfig",
    "ExtractedContent", "JobState", "RawContent", "SourceObject", "SyncJob",
]
