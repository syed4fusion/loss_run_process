from __future__ import annotations

from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, Form
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.job import Job, JobFile
from app.models.output import JobOutput
from app.schemas.jobs import JobListResponse, JobResponse
from app.services import storage

router = APIRouter()

MAX_FILES = 10
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("/", response_model=JobResponse, status_code=201)
async def create_job(
    insured_name: str = Form(...),
    files: List[UploadFile] = ...,
    db: Session = Depends(get_db),
):
    if not files or len(files) == 0:
        raise HTTPException(400, "At least one file is required")
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"Maximum {MAX_FILES} files allowed")

    job = Job(insured_name=insured_name)
    db.add(job)
    db.flush()  # get job.id

    # Create output record
    output = JobOutput(job_id=job.id)
    db.add(output)

    for upload in files:
        if not upload.filename or not upload.filename.lower().endswith(".pdf"):
            raise HTTPException(400, f"File '{upload.filename}' is not a PDF")

        content = await upload.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(400, f"File '{upload.filename}' exceeds 50 MB limit")

        file_path = await storage.save_upload(job.id, upload.filename, content)

        job_file = JobFile(
            job_id=job.id,
            filename=upload.filename,
            file_path=file_path,
        )
        db.add(job_file)

    db.commit()
    db.refresh(job)
    return job


@router.get("/", response_model=JobListResponse)
def list_jobs(
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    total = query.count()
    items = (
        query.order_by(Job.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return JobListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.post("/{job_id}/run", status_code=202)
def run_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status not in ("pending", "failed"):
        raise HTTPException(409, f"Job is already in status '{job.status}'")

    background_tasks.add_task(_run_pipeline_bg, job_id)
    return {"message": "Pipeline enqueued", "job_id": job_id}


async def _run_pipeline_bg(job_id: str):
    """Run in background — imports deferred to avoid circular imports."""
    from app.pipeline.runner import run_pipeline
    await run_pipeline(job_id)
