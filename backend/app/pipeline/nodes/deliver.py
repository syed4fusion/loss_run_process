from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.job import Job, JobStatus
from app.models.output import JobOutput
from app.pipeline.state import PipelineState
from app.schemas.summary import MANDATORY_DISCLAIMER, UnderwriterSummary
from app.services.chart_generator import generate_all_charts
from app.services.pdf_generator import generate_pdf
from app.services.storage import save_output


def _parse_summary(summary_json: str | None, job_id: str) -> dict:
    if not summary_json:
        return UnderwriterSummary(job_id=job_id).model_dump(mode="json")
    try:
        payload = json.loads(summary_json)
        payload["job_id"] = job_id
        payload["disclaimer"] = payload.get("disclaimer") or MANDATORY_DISCLAIMER
        return UnderwriterSummary.model_validate(payload).model_dump(mode="json")
    except Exception:
        return UnderwriterSummary(job_id=job_id).model_dump(mode="json")


def deliver_node(state: PipelineState) -> PipelineState:
    job_id = state["job_id"]
    claims_array = state.get("claims_array") or {}
    analytics = state.get("analytics") or {}
    red_flags = state.get("red_flags") or {"flags": []}

    draft_summary = state.get("draft_summary")
    final_summary = state.get("final_summary") or draft_summary
    summary_data = _parse_summary(final_summary, job_id)
    charts = generate_all_charts(claims_array=claims_array, analytics=analytics)

    pdf_bytes = generate_pdf(
        job_id=job_id,
        insured_name=state.get("insured_name", ""),
        summary_data=summary_data,
        analytics=analytics,
        red_flags=red_flags,
        charts=charts,
    )
    pdf_path = asyncio.run(save_output(job_id, "underwriter_summary.pdf", pdf_bytes))

    db = SessionLocal()
    try:
        output = db.query(JobOutput).filter(JobOutput.job_id == job_id).first()
        if output:
            output.claims_json = json.dumps(claims_array, default=str)
            output.analytics_json = json.dumps(analytics, default=str)
            output.redflags_json = json.dumps(red_flags, default=str)
            output.draft_summary = draft_summary
            output.final_summary = json.dumps(summary_data, default=str)
            output.charts_json = json.dumps(charts)
            output.pdf_path = pdf_path

        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.completed
            job.current_stage = "deliver"
            job.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()

    return {
        **state,
        "current_stage": "deliver",
        "completed": True,
        "final_summary": json.dumps(summary_data, default=str),
    }
