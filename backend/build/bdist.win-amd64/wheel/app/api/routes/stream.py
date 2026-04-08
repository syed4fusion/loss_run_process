from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.database import SessionLocal
from app.models.job import Job

router = APIRouter()

TERMINAL_STAGES = {"completed", "failed"}


def _event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.get("/{job_id}/stream")
def stream_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")

    async def generator():
        last_stage = None
        while True:
            loop_db = SessionLocal()
            try:
                curr = loop_db.query(Job).filter(Job.id == job_id).first()
                if not curr:
                    yield _event("stage_error", {"job_id": job_id, "error": "Job not found"})
                    break
                stage = curr.current_stage or "unknown"
                status = curr.status.value if hasattr(curr.status, "value") else str(curr.status)
                payload = {"job_id": job_id, "stage": stage, "status": status}
                if stage != last_stage:
                    yield _event("stage_update", payload)
                    last_stage = stage
                else:
                    yield _event("heartbeat", payload)

                if stage in TERMINAL_STAGES or status in TERMINAL_STAGES:
                    yield _event("completed" if status == "completed" else "failed", payload)
                    break
            finally:
                loop_db.close()
            await asyncio.sleep(1.0)

    return StreamingResponse(generator(), media_type="text/event-stream")
