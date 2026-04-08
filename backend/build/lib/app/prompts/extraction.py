"""Gemini extraction prompt and response schema for loss run PDFs."""

EXTRACTION_PROMPT = """You are a specialist insurance data extraction system. Your task is to extract ALL claim-level data from this loss run document and return it as structured JSON.

CRITICAL RULES:
1. Extract EVERY individual claim — do not summarize, aggregate, or skip any claim.
2. If a field is not present in the document, use null. NEVER guess or estimate values.
3. "amount_incurred" MUST equal amount_paid + amount_reserved. If the document shows a different value, use the document's value and note the discrepancy in extraction_notes.
4. Dates must be returned in YYYY-MM-DD format. Parse all variants: MM/DD/YYYY, DD-Mon-YY, YYYY-MM-DD, etc.
5. Amounts must be returned as plain numbers (no $ signs, no commas). Negative values in parentheses like (1,234.00) = -1234.00.
6. For "status": use "open" or "closed" only.
7. For "lob": map carrier-specific line names to one of: GL, CA, WC, PROP, PL, UMB, UNKNOWN.
   - General Liability, CPKG, Commercial Package, BOP → GL
   - Workers Comp, WCOM, WC → WC
   - Business Auto, BAUT, Commercial Auto → CA
   - Commercial Umbrella, CUMB → UMB
   - Crime, CRIM → PROP
   - Professional Liability, E&O, D&O → PL
   - If uncertain, use UNKNOWN
8. policy_period_start and policy_period_end: the coverage dates for this loss run file.
9. earned_premium: the policy premium for this period. Use null if not stated.
10. carrier_code: use the carrier abbreviation if visible in headers/filename. Use null if not found.
11. Add a note to extraction_notes for every field you could not confidently extract.

Document to process:
"""

# Structured output schema passed to Gemini
EXTRACTION_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "carrier_name": {"type": "string"},
        "carrier_code": {"type": "string", "nullable": True},
        "lob": {
            "type": "string",
            "enum": ["GL", "CA", "WC", "PROP", "PL", "UMB", "UNKNOWN"],
        },
        "policy_period_start": {"type": "string", "nullable": True},
        "policy_period_end": {"type": "string", "nullable": True},
        "earned_premium": {"type": "number", "nullable": True},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_number": {"type": "string"},
                    "occurrence_date": {"type": "string", "nullable": True},
                    "close_date": {"type": "string", "nullable": True},
                    "status": {"type": "string", "enum": ["open", "closed"]},
                    "claim_type": {"type": "string"},
                    "description": {"type": "string"},
                    "amount_paid": {"type": "number"},
                    "amount_reserved": {"type": "number"},
                    "amount_incurred": {"type": "number"},
                },
                "required": [
                    "claim_number",
                    "status",
                    "claim_type",
                    "description",
                    "amount_paid",
                    "amount_reserved",
                    "amount_incurred",
                ],
            },
        },
        "extraction_notes": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["carrier_name", "lob", "claims", "extraction_notes"],
}
