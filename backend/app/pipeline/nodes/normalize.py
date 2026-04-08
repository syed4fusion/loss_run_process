from __future__ import annotations

"""Normalize node — merges, deduplicates, and validates raw extractions."""
import logging
import re
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app.database import SessionLocal
from app.models.output import JobOutput
from app.pipeline.state import PipelineState
from app.schemas.claims import ClaimsArray

logger = logging.getLogger(__name__)

# LOB lookup: carrier-specific terms → standard code
LOB_LOOKUP: dict[str, str] = {
    "gl": "GL", "general liability": "GL", "cpkg": "GL",
    "commercial package": "GL", "bop": "GL",
    "wc": "WC", "workers comp": "WC", "workers' comp": "WC",
    "workers compensation": "WC", "wcom": "WC",
    "ca": "CA", "commercial auto": "CA", "business auto": "CA", "baut": "CA",
    "umb": "UMB", "umbrella": "UMB", "commercial umbrella": "UMB", "cumb": "UMB",
    "prop": "PROP", "property": "PROP", "crime": "PROP", "crim": "PROP",
    "pl": "PL", "professional liability": "PL", "e&o": "PL", "d&o": "PL",
}

LITIGATION_KEYWORDS: frozenset[str] = frozenset({
    "lawsuit", "litigation", "attorney", "legal action", "suit filed",
    "civil action", "complaint filed", "deposition", "plaintiff", "defendant",
    "counsel", "litigated", "litigating",
})

DATE_FORMATS = [
    "%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d-%b-%y", "%d-%b-%Y",
    "%m-%d-%Y", "%m-%d-%y", "%b %d, %Y", "%B %d, %Y",
]


def _parse_date(val: str | None) -> date | None:
    if not val or str(val).strip().lower() in ("", "null", "none", "n/a"):
        return None
    val = str(val).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    logger.warning("Could not parse date: %s", val)
    return None


def _parse_amount(val) -> Decimal:
    if val is None:
        return Decimal("0")
    s = str(val).strip().replace("$", "").replace(",", "")
    # Handle parenthetical negatives: (1234.00) → -1234.00
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")


def _normalize_lob(raw: str | None) -> str:
    if not raw:
        return "UNKNOWN"
    return LOB_LOOKUP.get(raw.strip().lower(), raw.upper() if len(raw) <= 5 else "UNKNOWN")


def _has_litigation(description: str) -> bool:
    desc_lower = description.lower()
    return any(kw in desc_lower for kw in LITIGATION_KEYWORDS)


def normalize_node(state: PipelineState) -> PipelineState:
    job_id = state["job_id"]
    insured_name = state.get("insured_name", "")
    raw_extractions = state.get("raw_extractions", [])
    errors = list(state.get("errors", []))
    extraction_notes: list[str] = []

    seen_claims: dict[str, dict] = {}  # key: carrier_code-claim_number
    policy_periods: list[dict] = []

    for extraction in raw_extractions:
        carrier_name = extraction.get("carrier_name", "UNKNOWN")
        carrier_code = (extraction.get("carrier_code") or carrier_name[:8]).upper().replace(" ", "_")
        lob = _normalize_lob(extraction.get("lob"))
        period_start = extraction.get("policy_period_start") or ""
        period_end = extraction.get("policy_period_end") or ""
        period_str = f"{period_start}/{period_end}" if period_start and period_end else "UNKNOWN"
        earned_premium = _parse_amount(extraction.get("earned_premium"))

        extraction_notes.extend(extraction.get("extraction_notes", []))

        claims_out: list[dict] = []
        for raw_claim in extraction.get("claims", []):
            claim_number = str(raw_claim.get("claim_number", "")).strip()
            dedup_key = f"{carrier_code}-{claim_number}"

            amount_paid = _parse_amount(raw_claim.get("amount_paid"))
            amount_reserved = _parse_amount(raw_claim.get("amount_reserved"))
            amount_incurred = _parse_amount(raw_claim.get("amount_incurred"))

            # Validate incurred = paid + reserved (within $1 tolerance)
            expected_incurred = amount_paid + amount_reserved
            if abs(amount_incurred - expected_incurred) > Decimal("1.00"):
                extraction_notes.append(
                    f"Claim {claim_number}: incurred {amount_incurred} ≠ paid {amount_paid} + reserved {amount_reserved}"
                )

            description = str(raw_claim.get("description", ""))
            claim_type = str(raw_claim.get("claim_type", "general"))
            status = raw_claim.get("status", "closed")

            claim = {
                "claim_id": dedup_key,
                "carrier_code": carrier_code,
                "lob": lob,
                "policy_period": period_str,
                "occurrence_date": _parse_date(raw_claim.get("occurrence_date")),
                "close_date": _parse_date(raw_claim.get("close_date")),
                "status": status if status in ("open", "closed") else "closed",
                "claim_type": claim_type,
                "description": description,
                "amount_paid": str(amount_paid),
                "amount_reserved": str(amount_reserved),
                "amount_incurred": str(amount_incurred),
                "earned_premium": str(earned_premium) if earned_premium else None,
                "subrogation_potential": "subroga" in description.lower(),
                "litigation_flag": _has_litigation(description),
            }

            if dedup_key not in seen_claims:
                seen_claims[dedup_key] = claim
                claims_out.append(claim)
            else:
                # Keep the version with higher incurred (more recent data)
                existing = seen_claims[dedup_key]
                if amount_incurred > Decimal(existing["amount_incurred"]):
                    seen_claims[dedup_key] = claim
                    # Replace in claims_out
                    claims_out = [c if c["claim_id"] != dedup_key else claim for c in claims_out]

        policy_periods.append({
            "carrier_code": carrier_code,
            "lob": lob,
            "period": period_str,
            "earned_premium": str(earned_premium),
            "claims": claims_out,
        })

    claims_array = {
        "job_id": job_id,
        "insured_name": insured_name,
        "policy_periods": policy_periods,
        "extraction_notes": extraction_notes,
    }
    # Ensure output shape is valid against the ClaimsArray schema.
    claims_array = ClaimsArray.model_validate(claims_array).model_dump(mode="json")

    # Persist normalized ClaimsArray JSON after normalization succeeds.
    db = SessionLocal()
    try:
        output = db.query(JobOutput).filter(JobOutput.job_id == job_id).first()
        if output:
            output.claims_json = json.dumps(claims_array)
            db.commit()
    finally:
        db.close()

    logger.info(
        "Normalize: %d policy periods, %d unique claims for job %s",
        len(policy_periods),
        len(seen_claims),
        job_id,
    )
    return {**state, "claims_array": claims_array, "errors": errors, "current_stage": "normalize"}
