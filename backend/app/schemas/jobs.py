from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel


class JobFileResponse(BaseModel):
    id: str
    filename: str
    carrier_code: str | None
    lob_code: str | None
    policy_period_start: str | None
    policy_period_end: str | None
    extraction_status: str

    model_config = {"from_attributes": True}


class JobCreate(BaseModel):
    insured_name: str


class JobResponse(BaseModel):
    id: str
    insured_name: str
    status: str
    current_stage: str | None
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    files: List[JobFileResponse] = []

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    items: List[JobResponse]
    total: int
    page: int
    page_size: int
