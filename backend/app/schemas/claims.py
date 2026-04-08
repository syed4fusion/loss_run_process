from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Literal

from pydantic import BaseModel, Field


class Claim(BaseModel):
    claim_id: str
    carrier_code: str
    lob: Literal["GL", "CA", "WC", "PROP", "PL", "UMB", "UNKNOWN"]
    policy_period: str  # "2023-01-01/2024-01-01"
    occurrence_date: date | None = None
    close_date: date | None = None
    status: Literal["open", "closed"]
    claim_type: str
    description: str
    amount_paid: Decimal = Decimal("0")
    amount_reserved: Decimal = Decimal("0")
    amount_incurred: Decimal = Decimal("0")  # paid + reserved
    earned_premium: Decimal | None = None
    subrogation_potential: bool = False
    litigation_flag: bool = False


class PolicyPeriodSummary(BaseModel):
    carrier_code: str
    lob: str
    period: str  # "2023-01-01/2024-01-01"
    earned_premium: Decimal = Decimal("0")
    claims: List[Claim] = Field(default_factory=list)


class ClaimsArray(BaseModel):
    job_id: str
    insured_name: str
    policy_periods: List[PolicyPeriodSummary] = Field(default_factory=list)
    extraction_notes: List[str] = Field(default_factory=list)
