"""Pipeline runner used by jobs route background task."""

import asyncio
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.job import Job, JobStatus
from app.pipeline.runtime import get_graph
from app.pipeline.state import PipelineState

async def _run_stream(graph, state: PipelineState, *, job_id: str) -> None:
    config = {"configurable": {"thread_id": job_id}}
    async for _ in graph.astream(state, config=config, stream_mode="values"):
        pass


async def run_pipeline(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        job.status = JobStatus.running
        job.current_stage = "ingest"
        db.commit()

        graph = get_graph()
        initial_state: PipelineState = {
            "job_id": job.id,
            "insured_name": job.insured_name,
            "errors": [],
            "current_stage": "ingest",
            "completed": False,
            "rejection_count": 0,
        }
        await _run_stream(graph, initial_state, job_id=job_id)

        # Graph is configured with interrupt_before=["hitl_gate"], so pause status here.
        job = db.query(Job).filter(Job.id == job_id).first()
        if job and job.status == JobStatus.running and job.current_stage != "deliver":
            job.status = JobStatus.hitl_pending
            job.current_stage = "hitl_pending"
            db.commit()

    except Exception as exc:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.failed
            job.current_stage = "failed"
            job.error_message = str(exc)
            db.commit()
    finally:
        db.close()


async def resume_pipeline(
    *,
    job_id: str,
    hitl_action: str,
    hitl_edit_content: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        job.status = JobStatus.running
        job.current_stage = "hitl_resume"
        db.commit()

        graph = get_graph()
        resume_state: PipelineState = {
            "job_id": job_id,
            "hitl_action": hitl_action,
            "hitl_edit_content": hitl_edit_content,
            "current_stage": "hitl_pending",
        }
        await _run_stream(graph, resume_state, job_id=job_id)

        job = db.query(Job).filter(Job.id == job_id).first()
        if job and job.status == JobStatus.running and job.current_stage != "deliver":
            # If graph did not complete, return to HITL queue.
            job.status = JobStatus.hitl_pending
            job.current_stage = "hitl_pending"
            db.commit()

    except Exception as exc:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.failed
            job.current_stage = "failed"
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
