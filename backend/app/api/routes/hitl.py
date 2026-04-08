from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.hitl import HitlAction
from app.models.job import Job, JobStatus
from app.models.output import JobOutput
from app.pipeline.runner import resume_pipeline

router = APIRouter()


class HitlApproveBody(BaseModel):
    user_id: str


class HitlEditBody(BaseModel):
    user_id: str
    edited_sections: dict[str, Any]


class HitlRejectBody(BaseModel):
    user_id: str
    reason: str


def _get_job_and_output(job_id: str, db: Session) -> tuple[Job, JobOutput]:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    output = db.query(JobOutput).filter(JobOutput.job_id == job_id).first()
    if not output:
        raise HTTPException(404, "Job output not found")
    return job, output


def _parse_json(value: str | None, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


@router.get("/queue")
def get_hitl_queue(db: Session = Depends(get_db)):
    jobs = (
        db.query(Job)
        .filter(Job.status == JobStatus.hitl_pending)
        .order_by(Job.created_at.asc())
        .all()
    )
    items = []
    for job in jobs:
        output = db.query(JobOutput).filter(JobOutput.job_id == job.id).first()
        redflags = _parse_json(output.redflags_json if output else None, {"flags": []})
        items.append(
            {
                "job_id": job.id,
                "insured_name": job.insured_name,
                "created_at": job.created_at,
                "critical_count": sum(1 for f in redflags.get("flags", []) if f.get("severity") == "critical"),
                "warning_count": sum(1 for f in redflags.get("flags", []) if f.get("severity") == "warning"),
                "info_count": sum(1 for f in redflags.get("flags", []) if f.get("severity") == "info"),
            }
        )
    return {"items": items}


@router.get("/{job_id}")
def get_hitl_detail(job_id: str, db: Session = Depends(get_db)):
    job, output = _get_job_and_output(job_id, db)
    if job.status != JobStatus.hitl_pending:
        raise HTTPException(409, f"Job is not awaiting HITL review (status={job.status})")
    return {
        "job_id": job.id,
        "insured_name": job.insured_name,
        "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        "draft_summary": _parse_json(output.draft_summary, {}),
        "red_flags": _parse_json(output.redflags_json, {}),
        "claims": _parse_json(output.claims_json, {}),
        "analytics": _parse_json(output.analytics_json, {}),
    }


@router.post("/{job_id}/approve")
def approve_hitl(
    job_id: str,
    body: HitlApproveBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    job, _ = _get_job_and_output(job_id, db)
    if job.status != JobStatus.hitl_pending:
        raise HTTPException(409, f"Job is not in hitl_pending (status={job.status})")

    db.add(HitlAction(job_id=job_id, action="approve", user_id=body.user_id))
    db.commit()
    background_tasks.add_task(
        _resume_pipeline_bg,
        job_id,
        "approve",
        None,
    )
    return {"message": "Approval received. Pipeline resumed.", "job_id": job_id}


@router.post("/{job_id}/edit")
def edit_hitl(
    job_id: str,
    body: HitlEditBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    job, _ = _get_job_and_output(job_id, db)
    if job.status != JobStatus.hitl_pending:
        raise HTTPException(409, f"Job is not in hitl_pending (status={job.status})")

    edit_payload = json.dumps(body.edited_sections, default=str)
    db.add(
        HitlAction(
            job_id=job_id,
            action="edit",
            user_id=body.user_id,
            edit_content=edit_payload,
        )
    )
    db.commit()
    background_tasks.add_task(
        _resume_pipeline_bg,
        job_id,
        "edit",
        edit_payload,
    )
    return {"message": "Edits received. Pipeline resumed.", "job_id": job_id}


@router.post("/{job_id}/reject")
def reject_hitl(
    job_id: str,
    body: HitlRejectBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    job, _ = _get_job_and_output(job_id, db)
    if job.status != JobStatus.hitl_pending:
        raise HTTPException(409, f"Job is not in hitl_pending (status={job.status})")

    reject_count = (
        db.query(HitlAction)
        .filter(HitlAction.job_id == job_id, HitlAction.action == "reject")
        .count()
    )
    if reject_count >= 2:
        raise HTTPException(409, "Maximum rejection count reached; manual escalation required")

    db.add(
        HitlAction(
            job_id=job_id,
            action="reject",
            user_id=body.user_id,
            reason=body.reason,
        )
    )
    db.commit()
    background_tasks.add_task(
        _resume_pipeline_bg,
        job_id,
        "reject",
        None,
    )
    return {"message": "Rejection received. Summary regeneration started.", "job_id": job_id}


async def _resume_pipeline_bg(job_id: str, hitl_action: str, hitl_edit_content: str | None):
    await resume_pipeline(
        job_id=job_id,
        hitl_action=hitl_action,
        hitl_edit_content=hitl_edit_content,
    )
