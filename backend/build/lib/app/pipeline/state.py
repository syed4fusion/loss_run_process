from typing import Optional
from typing_extensions import TypedDict


class PipelineState(TypedDict, total=False):
    job_id: str
    insured_name: str
    file_paths: list[str]

    # Stage outputs (None until stage completes)
    raw_extractions: list[dict]
    claims_array: Optional[dict]       # ClaimsArray as dict
    analytics: Optional[dict]          # AnalyticsResult as dict
    red_flags: Optional[dict]          # RedFlagReport as dict
    draft_summary: Optional[str]       # JSON string of UnderwriterSummary sections
    final_summary: Optional[str]       # finalized after HITL

    # HITL
    hitl_action: Optional[str]         # approve / edit / reject
    hitl_edit_content: Optional[str]   # edited sections JSON
    rejection_count: int               # times rejected; escalate at 2

    # Tracking
    current_stage: str
    errors: list[str]
    completed: bool
