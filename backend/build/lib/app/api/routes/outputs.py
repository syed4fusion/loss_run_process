from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.job import Job, JobStatus
from app.models.output import JobOutput

router = APIRouter()


def _get_job_and_output(job_id: str, db: Session) -> tuple[Job, JobOutput]:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    output = db.query(JobOutput).filter(JobOutput.job_id == job_id).first()
    if not output:
        raise HTTPException(404, "Output not found")
    if job.status != JobStatus.completed:
        raise HTTPException(409, f"Job not completed (status={job.status})")
    return job, output


def _parse_json(value: str | None, name: str):
    if not value:
        raise HTTPException(404, f"{name} not generated")
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(500, f"{name} is malformed JSON") from exc


@router.get("/{job_id}/claims")
def get_claims(job_id: str, db: Session = Depends(get_db)):
    _, output = _get_job_and_output(job_id, db)
    return _parse_json(output.claims_json, "claims")


@router.get("/{job_id}/analytics")
def get_analytics(job_id: str, db: Session = Depends(get_db)):
    _, output = _get_job_and_output(job_id, db)
    return _parse_json(output.analytics_json, "analytics")


@router.get("/{job_id}/redflags")
def get_redflags(job_id: str, db: Session = Depends(get_db)):
    _, output = _get_job_and_output(job_id, db)
    return _parse_json(output.redflags_json, "redflags")


@router.get("/{job_id}/summary")
def get_summary(job_id: str, db: Session = Depends(get_db)):
    _, output = _get_job_and_output(job_id, db)
    return _parse_json(output.final_summary, "summary")


@router.get("/{job_id}/charts")
def get_charts(job_id: str, db: Session = Depends(get_db)):
    _, output = _get_job_and_output(job_id, db)
    return _parse_json(output.charts_json, "charts")


@router.get("/{job_id}/pdf")
def get_pdf(job_id: str, db: Session = Depends(get_db)):
    _, output = _get_job_and_output(job_id, db)
    if not output.pdf_path:
        raise HTTPException(404, "PDF not generated")
    pdf_path = Path(output.pdf_path)
    if not pdf_path.exists():
        raise HTTPException(404, "PDF file not found on disk")
    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename=f"underwriter_summary_{job_id}.pdf",
    )
