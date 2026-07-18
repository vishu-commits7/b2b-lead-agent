# Change the top of models/__init__.py to this:
from .schemas import (
    LeadCompanyInfo,
    OutreachDraft,
    LeadQualificationResult,
    ContactEnrichment,
    EmailSequenceTouch,
    EmailSequence,
    EnrichedLeadResult,
)

__all__ = [
    "LeadCompanyInfo",
    "OutreachDraft",
    "LeadQualificationResult",
    "ContactEnrichment",
    "EmailSequenceTouch",
    "EmailSequence",
    "EnrichedLeadResult",
]