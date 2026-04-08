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


async def extract_node(state: PipelineState) -> PipelineState:
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

        job_files = (
            db.query(JobFile)
            .filter(JobFile.job_id == job_id, JobFile.file_path.in_(file_paths))
            .all()
        )
        for job_file in job_files:
            job_file.extraction_status = ExtractionStatus.processing
        db.commit()

        client = get_gemini_client()
        tasks = [asyncio.create_task(_extract_one(fp, client)) for fp in file_paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

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
                    if result.get("_malformed_json"):
                        errors.append(
                            f"Extraction produced malformed JSON for '{fp}'. Raw response stored in extraction payload."
                        )
                        jf.extraction_status = ExtractionStatus.failed
                    else:
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
