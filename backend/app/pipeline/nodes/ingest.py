"""Ingest node — validates files and preps pipeline state."""
import logging
from pathlib import Path

from app.database import SessionLocal
from app.models.job import Job, JobFile, JobStatus
from app.pipeline.state import PipelineState

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF"


def _pdf_validation_error(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            header = f.read(4)
            if header != PDF_MAGIC:
                return "is not a valid PDF (bad magic bytes)"

            # Heuristic encryption detection (common in password-protected PDFs).
            # We check both early and late file sections because trailer dictionaries
            # may reference /Encrypt near the end.
            first_chunk = f.read(1024 * 1024)
            f.seek(0, 2)
            size = f.tell()
            tail_size = min(size, 1024 * 1024)
            f.seek(max(0, size - tail_size))
            tail_chunk = f.read(tail_size)
            if b"/Encrypt" in first_chunk or b"/Encrypt" in tail_chunk:
                return "appears to be password-protected/encrypted and cannot be processed"
            return None
    except OSError:
        return "could not be opened for validation"


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
            validation_error = _pdf_validation_error(f.file_path)
            if validation_error:
                errors.append(f"'{f.filename}' {validation_error}")
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
