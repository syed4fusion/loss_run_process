from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JobStatus(str, PyEnum):
    pending = "pending"
    running = "running"
    hitl_pending = "hitl_pending"
    completed = "completed"
    failed = "failed"


class ExtractionStatus(str, PyEnum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    insured_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(JobStatus), nullable=False, default=JobStatus.pending
    )
    current_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    files: Mapped[list["JobFile"]] = relationship(
        "JobFile", back_populates="job", cascade="all, delete-orphan"
    )
    output: Mapped[Optional["JobOutput"]] = relationship(  # noqa: F821
        "JobOutput", back_populates="job", uselist=False, cascade="all, delete-orphan"
    )
    hitl_actions: Mapped[list["HitlAction"]] = relationship(  # noqa: F821
        "HitlAction", back_populates="job", cascade="all, delete-orphan"
    )


class JobFile(Base):
    __tablename__ = "job_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    carrier_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    lob_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    policy_period_start: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    policy_period_end: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    extraction_status: Mapped[str] = mapped_column(
        Enum(ExtractionStatus), nullable=False, default=ExtractionStatus.pending
    )

    job: Mapped[Job] = relationship("Job", back_populates="files")
