"""OmniRAG Universal Intake Gate — ingest any source, any format."""

from omnirag.intake.gate import IntakeGate
from omnirag.intake.models import IntakeJob, IntakeRequest, RawContent, TextSegment

__all__ = ["IntakeGate", "IntakeJob", "IntakeRequest", "RawContent", "TextSegment"]
