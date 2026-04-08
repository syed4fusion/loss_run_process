from __future__ import annotations

from decimal import Decimal
from typing import List

from pydantic import BaseModel, Field


class YearlyStats(BaseModel):
    year: int
    claim_count: int
    total_incurred: Decimal
    total_paid: Decimal
    total_reserved: Decimal
    earned_premium: Decimal
    loss_ratio: Decimal | None = None  # null when premium = 0
    loss_frequency: Decimal | None = None
    loss_severity: Decimal
    large_loss_count: int
    open_claim_count: int


class AnalyticsResult(BaseModel):
    job_id: str
    yearly_stats: List[YearlyStats] = Field(default_factory=list)
    overall_loss_ratio: Decimal | None = None
    frequency_trend: Decimal | None = None  # % change first→last year
    severity_trend: Decimal | None = None
    avg_days_to_close: float | None = None
    total_open_reserves: Decimal
    large_loss_ratio: Decimal | None = None
    years_analyzed: List[int] = Field(default_factory=list)
    missing_years: List[int] = Field(default_factory=list)
