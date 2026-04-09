import json
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.job import Job, JobStatus
from app.models.output import JobOutput
from app.pipeline.runtime import get_graph
from app.pipeline.nodes.deliver import deliver_node
from app.pipeline.state import PipelineState


def _load_json(value: str | None, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default

def run_pipeline(job_id: str) -> None:
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
        graph.invoke(
            initial_state,
            {"configurable": {"thread_id": job_id}},
        )

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


def resume_pipeline(
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

        if hitl_action in {"approve", "edit"}:
            output = db.query(JobOutput).filter(JobOutput.job_id == job_id).first()
            if not output:
                raise RuntimeError("Job output not found")

            deliver_state: PipelineState = {
                "job_id": job_id,
                "insured_name": job.insured_name,
                "claims_array": _load_json(output.claims_json, {}),
                "analytics": _load_json(output.analytics_json, {}),
                "red_flags": _load_json(output.redflags_json, {"flags": []}),
                "draft_summary": output.draft_summary,
                "final_summary": hitl_edit_content if hitl_action == "edit" else output.draft_summary,
                "current_stage": "hitl_resume",
                "completed": False,
                "errors": [],
            }
            deliver_node(deliver_state)
            return

        graph = get_graph()
        resume_state: PipelineState = {
            "job_id": job_id,
            "hitl_action": hitl_action,
            "hitl_edit_content": hitl_edit_content,
            "current_stage": "hitl_pending",
        }
        graph.invoke(
            resume_state,
            {"configurable": {"thread_id": job_id}},
        )

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
