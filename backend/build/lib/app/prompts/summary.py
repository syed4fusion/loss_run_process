"""Prompts for red flag narratives and the underwriter summary."""

import json
from typing import Any

from app.schemas.summary import MANDATORY_DISCLAIMER

REDFLAG_NARRATIVE_PROMPT = """You are writing a single professional sentence for inclusion in an insurance underwriting summary.

A red flag has been CONFIRMED by a deterministic rules engine. Your job is to narrate it clearly and factually.

Flag type: {flag_type}
Rule triggered: {rule_description}
Source data: {source_data}

Requirements:
- One sentence only, maximum 100 words.
- Professional insurance underwriting tone.
- Reference only the specific numbers/dates/facts in source_data.
- Do not speculate beyond the data provided.
- Do not add caveats, disclaimers, or recommendations.
- Do not question whether the flag is valid — it has already been confirmed.
"""

UNDERWRITER_SUMMARY_PROMPT = """You are an experienced insurance underwriter writing a formal loss run analysis summary.

INSURED: {insured_name}
YEARS ANALYZED: {years_analyzed}
OVERALL LOSS RATIO: {overall_loss_ratio}
FREQUENCY TREND: {frequency_trend}
SEVERITY TREND: {severity_trend}

YEARLY STATISTICS:
{yearly_stats_json}

LARGE LOSSES (> $25,000):
{large_losses_json}

OPEN CLAIMS:
{open_claims_json}

CONFIRMED RED FLAGS:
{red_flags_json}

Write a formal underwriter summary with these exact sections. Return as JSON with these keys:
- executive_summary: 2-3 sentence overview of the account's loss history
- year_by_year: Analysis of each year's performance, trends observed
- large_loss_detail: Each large loss described with claim number, date, type, amount, and current status
- open_claim_status: Current open claims with reserves and exposure assessment
- red_flag_disclosure: Each confirmed red flag with its narrative, grouped by severity
- risk_management_observations: Professional observations on risk patterns (do not make coverage recommendations)
- disclaimer: exactly this fixed text "{mandatory_disclaimer}"

Requirements:
- Formal insurance underwriting tone throughout
- Reference only figures present in the provided data — never invent claim numbers, dates, or amounts
- Do not make coverage recommendations or underwriting decisions
- Do not speculate about future losses
- Each section should be substantive (minimum 2-3 sentences)
"""


def build_redflag_narrative_prompt(flag: dict) -> str:
    return REDFLAG_NARRATIVE_PROMPT.format(
        flag_type=flag.get("flag_type", ""),
        rule_description=flag.get("rule_description", ""),
        source_data=json.dumps(flag.get("source_data", {}), default=str),
    )


def build_summary_prompt(
    insured_name: str,
    years_analyzed: list[int],
    yearly_stats: list[Any],
    red_flags: list[Any],
    overall_loss_ratio: Any,
    frequency_trend: Any,
    severity_trend: Any,
    large_losses: list[Any],
    open_claims: list[Any],
) -> str:
    def _fmt(v: Any) -> str:
        if v is None:
            return "N/A"
        try:
            return f"{float(v):.2%}"
        except Exception:
            return str(v)

    return UNDERWRITER_SUMMARY_PROMPT.format(
        insured_name=insured_name,
        years_analyzed=", ".join(str(y) for y in sorted(years_analyzed)),
        overall_loss_ratio=_fmt(overall_loss_ratio),
        frequency_trend=_fmt(frequency_trend),
        severity_trend=_fmt(severity_trend),
        yearly_stats_json=json.dumps(yearly_stats, default=str, indent=2),
        large_losses_json=json.dumps(large_losses, default=str, indent=2),
        open_claims_json=json.dumps(open_claims, default=str, indent=2),
        red_flags_json=json.dumps(red_flags, default=str, indent=2),
        mandatory_disclaimer=MANDATORY_DISCLAIMER,
    )
