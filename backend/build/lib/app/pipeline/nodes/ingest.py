"""Ingest node — validates files and preps pipeline state."""
import logging
from pathlib import Path

from app.database import SessionLocal
from app.models.job import Job, JobFile, JobStatus
from app.pipeline.state import PipelineState

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF"


def _is_valid_pdf(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(4) == PDF_MAGIC
    except OSError:
        return False


def ingest_node(state: PipelineState) -> PipelineState:
    job_id = state["job_id"]
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {**state, "errors": [*state.get("errors", []), "Job not found"], "current_stage": "ingest_failed"}

        job.status = JobStatus.running
        job.current_stage = "ingest"
        db.commit()

        files = db.query(JobFile).filter(JobFile.job_id == job_id).all()
        file_paths: list[str] = []
        errors: list[str] = list(state.get("errors", []))

        for f in files:
            if not Path(f.file_path).exists():
                errors.append(f"File not found on disk: {f.filename}")
                continue
            if not _is_valid_pdf(f.file_path):
                errors.append(f"'{f.filename}' is not a valid PDF (bad magic bytes)")
                continue
            file_paths.append(f.file_path)

        if not file_paths:
            job.status = JobStatus.failed
            job.current_stage = "ingest_failed"
            job.error_message = "; ".join(errors) or "No valid PDF files found"
            db.commit()
            return {**state, "file_paths": [], "errors": errors, "current_stage": "ingest_failed"}

        logger.info("Ingest: %d valid files for job %s", len(file_paths), job_id)
        return {**state, "file_paths": file_paths, "errors": errors, "current_stage": "ingest"}
    finally:
        db.close()
