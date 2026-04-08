from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class RedFlagSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class RedFlag(BaseModel):
    flag_id: str
    flag_type: str
    severity: RedFlagSeverity
    triggered_by: str
    rule_description: str
    narrative: str = ""  # filled by Gemini in summary node
    source_data: Dict[str, Any] = Field(default_factory=dict)


class RedFlagReport(BaseModel):
    job_id: str
    flags: List[RedFlag] = Field(default_factory=list)
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
