from __future__ import annotations

"""Deterministic red-flag rules engine."""

import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from app.database import SessionLocal
from app.models.output import JobOutput
from app.pipeline.state import PipelineState
from app.schemas.redflags import RedFlag, RedFlagReport, RedFlagSeverity

LARGE_LOSS_THRESHOLD = Decimal("25000")
CATASTROPHIC_LOSS_THRESHOLD = Decimal("100000")
FREQUENCY_INCREASE_THRESHOLD = Decimal("0.20")
RESERVE_ESCALATION_THRESHOLD = Decimal("1.25")
LOSS_RATIO_CRITICAL = Decimal("0.85")
PATTERN_CONCENTRATION_COUNT = 4
RECENT_CLAIM_DAYS = 90


def _as_decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%b-%y", "%d-%b-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _iter_claims(claims_array: dict | None) -> list[dict]:
    claims: list[dict] = []
    for period in (claims_array or {}).get("policy_periods", []):
        claims.extend(period.get("claims", []))
    return claims


def _make_flag(
    *,
    flag_type: str,
    severity: RedFlagSeverity,
    triggered_by: str,
    rule_description: str,
    source_data: dict[str, Any],
) -> RedFlag:
    source_json = json.dumps(source_data, sort_keys=True, default=str)
    flag_id = f"{flag_type}:{abs(hash(source_json))}"
    return RedFlag(
        flag_id=flag_id,
        flag_type=flag_type,
        severity=severity,
        triggered_by=triggered_by,
        rule_description=rule_description,
        narrative="",
        source_data=source_data,
    )


def rule_large_single_loss(claims: list[dict]) -> list[RedFlag]:
    flags: list[RedFlag] = []
    for claim in claims:
        incurred = _as_decimal(claim.get("amount_incurred"))
        if incurred > LARGE_LOSS_THRESHOLD:
            flags.append(
                _make_flag(
                    flag_type="large_single_loss",
                    severity=RedFlagSeverity.WARNING,
                    triggered_by=f"claim:{claim.get('claim_id')}",
                    rule_description="Claim incurred exceeds $25,000 threshold.",
                    source_data={
                        "claim_id": claim.get("claim_id"),
                        "amount_incurred": str(incurred),
                        "threshold": str(LARGE_LOSS_THRESHOLD),
                    },
                )
            )
    return flags


def rule_catastrophic_loss(claims: list[dict], yearly_stats: list[dict]) -> list[RedFlag]:
    flags: list[RedFlag] = []
    for claim in claims:
        incurred = _as_decimal(claim.get("amount_incurred"))
        if incurred > CATASTROPHIC_LOSS_THRESHOLD:
            flags.append(
                _make_flag(
                    flag_type="catastrophic_loss",
                    severity=RedFlagSeverity.CRITICAL,
                    triggered_by=f"claim:{claim.get('claim_id')}",
                    rule_description="Claim incurred exceeds catastrophic threshold.",
                    source_data={
                        "claim_id": claim.get("claim_id"),
                        "amount_incurred": str(incurred),
                        "threshold": str(CATASTROPHIC_LOSS_THRESHOLD),
                    },
                )
            )
    for year in yearly_stats:
        loss_ratio = _as_decimal(year.get("loss_ratio"), default="0")
        if loss_ratio > LOSS_RATIO_CRITICAL:
            flags.append(
                _make_flag(
                    flag_type="catastrophic_loss_ratio",
                    severity=RedFlagSeverity.CRITICAL,
                    triggered_by=f"year:{year.get('year')}",
                    rule_description="Annual loss ratio exceeds critical threshold.",
                    source_data={
                        "year": year.get("year"),
                        "loss_ratio": str(loss_ratio),
                        "threshold": str(LOSS_RATIO_CRITICAL),
                    },
                )
            )
    return flags


def rule_deteriorating_frequency(yearly_stats: list[dict]) -> RedFlag | None:
    if len(yearly_stats) < 3:
        return None
    years = sorted(yearly_stats, key=lambda item: item.get("year", 0))
    consecutive_increases: list[dict[str, Any]] = []
    for idx in range(1, len(years)):
        prev = years[idx - 1]
        curr = years[idx]
        prev_freq = _as_decimal(prev.get("loss_frequency"), default="0")
        curr_freq = _as_decimal(curr.get("loss_frequency"), default="0")
        if prev_freq <= 0:
            continue
        growth = (curr_freq - prev_freq) / prev_freq
        if growth > FREQUENCY_INCREASE_THRESHOLD and int(curr["year"]) - int(prev["year"]) == 1:
            consecutive_increases.append(
                {
                    "from_year": prev["year"],
                    "to_year": curr["year"],
                    "growth": str(growth.quantize(Decimal("0.000001"))),
                }
            )
        else:
            consecutive_increases = []
        if len(consecutive_increases) >= 2:
            return _make_flag(
                flag_type="deteriorating_frequency",
                severity=RedFlagSeverity.WARNING,
                triggered_by="analytics:yearly_frequency_trend",
                rule_description="Loss frequency increased by more than 20% in consecutive years.",
                source_data={
                    "threshold": str(FREQUENCY_INCREASE_THRESHOLD),
                    "consecutive_increases": consecutive_increases,
                },
            )
    return None


def rule_open_claim_growing_reserve(raw_extractions: list[dict]) -> list[RedFlag]:
    snapshots: dict[str, list[dict[str, Any]]] = {}
    for extraction in raw_extractions:
        carrier_code = str(extraction.get("carrier_code") or extraction.get("carrier_name") or "UNKNOWN").upper()
        period_start = _parse_date(extraction.get("policy_period_start"))
        if not period_start:
            continue
        for claim in extraction.get("claims", []):
            claim_number = str(claim.get("claim_number", "")).strip()
            if not claim_number:
                continue
            key = f"{carrier_code}-{claim_number}"
            snapshots.setdefault(key, []).append(
                {
                    "year": period_start.year,
                    "reserved": _as_decimal(claim.get("amount_reserved")),
                    "status": str(claim.get("status", "")).strip().lower(),
                }
            )

    flags: list[RedFlag] = []
    for claim_id, points in snapshots.items():
        if len(points) < 2:
            continue
        ordered = sorted(points, key=lambda item: item["year"])
        prior = ordered[-2]
        current = ordered[-1]
        if prior["reserved"] <= 0:
            continue
        ratio = current["reserved"] / prior["reserved"]
        if current["status"] == "open" and ratio > RESERVE_ESCALATION_THRESHOLD:
            flags.append(
                _make_flag(
                    flag_type="open_claim_growing_reserve",
                    severity=RedFlagSeverity.WARNING,
                    triggered_by=f"claim:{claim_id}",
                    rule_description="Open claim reserve has increased by more than 25% across loss-run years.",
                    source_data={
                        "claim_id": claim_id,
                        "prior_year": prior["year"],
                        "current_year": current["year"],
                        "prior_reserved": str(prior["reserved"]),
                        "current_reserved": str(current["reserved"]),
                        "ratio": str(ratio.quantize(Decimal("0.000001"))),
                        "threshold": str(RESERVE_ESCALATION_THRESHOLD),
                    },
                )
            )
    return flags


def rule_litigation_indicator(claims: list[dict]) -> list[RedFlag]:
    flags: list[RedFlag] = []
    for claim in claims:
        if bool(claim.get("litigation_flag")):
            flags.append(
                _make_flag(
                    flag_type="litigation_indicator",
                    severity=RedFlagSeverity.WARNING,
                    triggered_by=f"claim:{claim.get('claim_id')}",
                    rule_description="Claim has deterministic litigation indicator.",
                    source_data={
                        "claim_id": claim.get("claim_id"),
                        "litigation_flag": True,
                    },
                )
            )
    return flags


def rule_pattern_concentration(claims: list[dict]) -> list[RedFlag]:
    grouped: dict[str, list[str]] = {}
    for claim in claims:
        claim_type = re.sub(r"\s+", " ", str(claim.get("claim_type", "")).strip().lower())
        if not claim_type:
            claim_type = "unknown"
        grouped.setdefault(claim_type, []).append(str(claim.get("claim_id")))
    flags: list[RedFlag] = []
    for claim_type, claim_ids in grouped.items():
        if len(claim_ids) >= PATTERN_CONCENTRATION_COUNT:
            flags.append(
                _make_flag(
                    flag_type="pattern_concentration",
                    severity=RedFlagSeverity.WARNING,
                    triggered_by=f"claim_type:{claim_type}",
                    rule_description="Claim type concentration exceeds threshold.",
                    source_data={
                        "claim_type": claim_type,
                        "claim_count": len(claim_ids),
                        "threshold": PATTERN_CONCENTRATION_COUNT,
                        "claim_ids": claim_ids,
                    },
                )
            )
    return flags


def rule_recent_claims(claims: list[dict], *, today: date | None = None) -> list[RedFlag]:
    ref = today or date.today()
    cutoff = ref - timedelta(days=RECENT_CLAIM_DAYS)
    flags: list[RedFlag] = []
    for claim in claims:
        occurrence = _parse_date(claim.get("occurrence_date"))
        if occurrence and occurrence >= cutoff:
            flags.append(
                _make_flag(
                    flag_type="recent_claim",
                    severity=RedFlagSeverity.INFO,
                    triggered_by=f"claim:{claim.get('claim_id')}",
                    rule_description="Recent claim occurred within 90 days.",
                    source_data={
                        "claim_id": claim.get("claim_id"),
                        "occurrence_date": occurrence.isoformat(),
                        "cutoff_date": cutoff.isoformat(),
                    },
                )
            )
    return flags


def rule_missing_years(missing_years: list[int]) -> RedFlag | None:
    if not missing_years:
        return None
    return _make_flag(
        flag_type="missing_years",
        severity=RedFlagSeverity.WARNING,
        triggered_by="analytics:missing_years",
        rule_description="Missing years found in expected year sequence.",
        source_data={"missing_years": missing_years},
    )


def rule_high_open_reserve_ratio(analytics: dict | None) -> RedFlag | None:
    analytics = analytics or {}
    total_open_reserves = _as_decimal(analytics.get("total_open_reserves"), default="0")
    total_incurred = sum(
        _as_decimal(year.get("total_incurred"), default="0")
        for year in analytics.get("yearly_stats", [])
    )
    if total_incurred <= 0:
        return None
    ratio = total_open_reserves / total_incurred
    if ratio > Decimal("0.30"):
        return _make_flag(
            flag_type="high_open_reserve_ratio",
            severity=RedFlagSeverity.WARNING,
            triggered_by="analytics:open_reserve_ratio",
            rule_description="Open reserves exceed 30% of total incurred.",
            source_data={
                "total_open_reserves": str(total_open_reserves),
                "total_incurred": str(total_incurred),
                "ratio": str(ratio.quantize(Decimal("0.000001"))),
                "threshold": "0.30",
            },
        )
    return None


def build_redflag_report(state: PipelineState) -> RedFlagReport:
    claims_array = state.get("claims_array") or {}
    analytics = state.get("analytics") or {}
    raw_extractions = state.get("raw_extractions") or []
    claims = _iter_claims(claims_array)
    yearly_stats = analytics.get("yearly_stats", [])
    missing_years = analytics.get("missing_years", [])

    flags: list[RedFlag] = []
    flags.extend(rule_large_single_loss(claims))
    flags.extend(rule_catastrophic_loss(claims, yearly_stats))
    freq_flag = rule_deteriorating_frequency(yearly_stats)
    if freq_flag:
        flags.append(freq_flag)
    flags.extend(rule_open_claim_growing_reserve(raw_extractions))
    flags.extend(rule_litigation_indicator(claims))
    flags.extend(rule_pattern_concentration(claims))
    flags.extend(rule_recent_claims(claims))
    missing_years_flag = rule_missing_years(missing_years)
    if missing_years_flag:
        flags.append(missing_years_flag)
    reserve_ratio_flag = rule_high_open_reserve_ratio(analytics)
    if reserve_ratio_flag:
        flags.append(reserve_ratio_flag)

    report = RedFlagReport(
        job_id=state["job_id"],
        flags=flags,
        critical_count=sum(1 for flag in flags if flag.severity == RedFlagSeverity.CRITICAL),
        warning_count=sum(1 for flag in flags if flag.severity == RedFlagSeverity.WARNING),
        info_count=sum(1 for flag in flags if flag.severity == RedFlagSeverity.INFO),
    )
    return report


def redflag_node(state: PipelineState) -> PipelineState:
    report = build_redflag_report(state)
    db = SessionLocal()
    try:
        output = db.query(JobOutput).filter(JobOutput.job_id == state["job_id"]).first()
        if output:
            output.redflags_json = report.model_dump_json()
            db.commit()
    finally:
        db.close()
    return {
        **state,
        "red_flags": report.model_dump(mode="json"),
        "current_stage": "redflags",
    }
