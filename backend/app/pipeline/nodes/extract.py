"""Extract node — sends each PDF to Gemini and collects raw extraction dicts."""
import asyncio
import json
import logging

from app.database import SessionLocal
from app.models.job import Job, JobFile, ExtractionStatus
from app.models.output import JobOutput
from app.pipeline.state import PipelineState
from app.prompts.extraction import EXTRACTION_PROMPT, EXTRACTION_RESPONSE_SCHEMA
from app.services.gemini_client import GeminiClient, get_gemini_client

logger = logging.getLogger(__name__)


async def _extract_one(file_path: str, client: GeminiClient) -> dict:
    file_ref = await client.upload_pdf(file_path)
    try:
        result = await client.extract_claims(
            file_ref, EXTRACTION_PROMPT, EXTRACTION_RESPONSE_SCHEMA
        )
        result["_source_file"] = file_path
        return result
    finally:
        client.delete_file(file_ref)


def extract_node(state: PipelineState) -> PipelineState:
    job_id = state["job_id"]
    file_paths = state.get("file_paths", [])
    errors = list(state.get("errors", []))
    raw_extractions: list[dict] = []

    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.current_stage = "extract"
            db.commit()

        async def _run_all():
            client = get_gemini_client()
            tasks = [_extract_one(fp, client) for fp in file_paths]
            return await asyncio.gather(*tasks, return_exceptions=True)

        # This node executes in a worker thread (runner uses asyncio.to_thread),
        # so it is safe to create and close a local event loop with asyncio.run.
        results = asyncio.run(_run_all())

        for fp, result in zip(file_paths, results):
            if isinstance(result, Exception):
                errors.append(f"Extraction failed for '{fp}': {result}")
                logger.error("Extraction error for %s: %s", fp, result)
                # Mark corresponding JobFile as failed
                jf = db.query(JobFile).filter(JobFile.job_id == job_id, JobFile.file_path == fp).first()
                if jf:
                    jf.extraction_status = ExtractionStatus.failed
                    db.commit()
            else:
                raw_extractions.append(result)
                # Update JobFile metadata from extraction
                jf = db.query(JobFile).filter(JobFile.job_id == job_id, JobFile.file_path == fp).first()
                if jf:
                    jf.carrier_code = result.get("carrier_code") or result.get("carrier_name", "")[:16]
                    jf.lob_code = result.get("lob")
                    jf.policy_period_start = result.get("policy_period_start")
                    jf.policy_period_end = result.get("policy_period_end")
                    jf.extraction_status = ExtractionStatus.completed
                    db.commit()

        if not raw_extractions:
            if job:
                job.current_stage = "extract_failed"
                job.error_message = "All file extractions failed"
                db.commit()
            raise RuntimeError("All file extractions failed")

        # Persist intermediate claims JSON
        output = db.query(JobOutput).filter(JobOutput.job_id == job_id).first()
        if output:
            output.claims_json = json.dumps(raw_extractions)
            db.commit()

        logger.info("Extract: %d/%d files extracted for job %s", len(raw_extractions), len(file_paths), job_id)
        return {**state, "raw_extractions": raw_extractions, "errors": errors, "current_stage": "extract"}
    finally:
        db.close()
