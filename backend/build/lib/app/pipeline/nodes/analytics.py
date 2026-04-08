from __future__ import annotations

"""Analytics node — pure pandas/numpy stats engine."""
import logging
from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pandas as pd

from app.pipeline.state import PipelineState

logger = logging.getLogger(__name__)

LARGE_LOSS_THRESHOLD = Decimal("25000")


def _to_date(val: str | None) -> date | None:
    if not val or val == "None" or val.strip() == "":
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(val.strip(), fmt).date()
        except ValueError:
            continue
    return None


def analytics_node(state: PipelineState) -> PipelineState:
    job_id = state["job_id"]
    claims_array = state.get("claims_array") or {}
    errors = list(state.get("errors", []))

    # Flatten all claims into a single list
    all_claims: list[dict] = []
    premium_by_year: dict[int, Decimal] = {}

    for pp in claims_array.get("policy_periods", []):
        period = pp.get("period", "")
        period_start_year: int | None = None
        try:
            period_start_year = int(period[:4])
        except (ValueError, TypeError):
            pass

        premium = Decimal(str(pp.get("earned_premium", "0") or "0"))
        if period_start_year and premium > 0:
            premium_by_year[period_start_year] = premium_by_year.get(period_start_year, Decimal("0")) + premium

        for claim in pp.get("claims", []):
            occ_date = _to_date(claim.get("occurrence_date"))
            close_date = _to_date(claim.get("close_date"))
            all_claims.append({
                **claim,
                "occurrence_date_parsed": occ_date,
                "close_date_parsed": close_date,
                "year": occ_date.year if occ_date else period_start_year,
                "incurred": Decimal(str(claim.get("amount_incurred", "0") or "0")),
                "paid": Decimal(str(claim.get("amount_paid", "0") or "0")),
                "reserved": Decimal(str(claim.get("amount_reserved", "0") or "0")),
            })

    if not all_claims:
        return {
            **state,
            "analytics": {
                "job_id": job_id,
                "yearly_stats": [],
                "overall_loss_ratio": None,
                "frequency_trend": None,
                "severity_trend": None,
                "avg_days_to_close": None,
                "total_open_reserves": "0",
                "large_loss_ratio": None,
                "years_analyzed": [],
                "missing_years": [],
            },
            "errors": errors,
            "current_stage": "analytics",
        }

    df = pd.DataFrame(all_claims)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year"])
    df["year"] = df["year"].astype(int)
    df["incurred_f"] = df["incurred"].apply(float)
    df["paid_f"] = df["paid"].apply(float)
    df["reserved_f"] = df["reserved"].apply(float)
    df["is_large"] = df["incurred"] >= LARGE_LOSS_THRESHOLD
    df["is_open"] = df["status"] == "open"

    years = sorted(df["year"].unique().tolist())
    yearly_stats = []

    for year in years:
        ydf = df[df["year"] == year]
        premium = float(premium_by_year.get(year, Decimal("0")))
        total_incurred = ydf["incurred_f"].sum()
        claim_count = len(ydf)

        loss_ratio = total_incurred / premium if premium > 0 else None
        loss_frequency = (claim_count / (premium / 1_000_000)) if premium > 0 else None
        loss_severity = total_incurred / claim_count if claim_count > 0 else 0.0

        yearly_stats.append({
            "year": year,
            "claim_count": claim_count,
            "total_incurred": round(total_incurred, 2),
            "total_paid": round(ydf["paid_f"].sum(), 2),
            "total_reserved": round(ydf["reserved_f"].sum(), 2),
            "earned_premium": round(premium, 2),
            "loss_ratio": round(loss_ratio, 6) if loss_ratio is not None else None,
            "loss_frequency": round(loss_frequency, 6) if loss_frequency is not None else None,
            "loss_severity": round(loss_severity, 2),
            "large_loss_count": int(ydf["is_large"].sum()),
            "open_claim_count": int(ydf["is_open"].sum()),
        })

    # Overall metrics
    total_incurred_all = df["incurred_f"].sum()
    total_premium_all = float(sum(premium_by_year.values()))
    overall_loss_ratio = total_incurred_all / total_premium_all if total_premium_all > 0 else None

    # Trend: % change from first to last year using linear regression slope
    def _pct_trend(series: list[float]) -> float | None:
        if len(series) < 2:
            return None
        x = np.arange(len(series), dtype=float)
        slope, _ = np.polyfit(x, series, 1)
        base = series[0] if series[0] != 0 else 1.0
        return float(slope / base)

    freqs = [s["loss_frequency"] for s in yearly_stats if s["loss_frequency"] is not None]
    sevs = [s["loss_severity"] for s in yearly_stats]
    frequency_trend = _pct_trend(freqs)
    severity_trend = _pct_trend(sevs)

    # avg days to close
    closed = df[df["is_open"] == False].copy()  # noqa: E712
    closed["days_to_close"] = closed.apply(
        lambda r: (r["close_date_parsed"] - r["occurrence_date_parsed"]).days
        if r["close_date_parsed"] and r["occurrence_date_parsed"] else None,
        axis=1,
    )
    avg_days = float(closed["days_to_close"].dropna().mean()) if not closed["days_to_close"].dropna().empty else None

    total_open_reserves = float(df[df["is_open"]]["reserved_f"].sum())
    total_large_loss = float(df[df["is_large"]]["incurred_f"].sum())
    large_loss_ratio = total_large_loss / total_incurred_all if total_incurred_all > 0 else None

    # Missing years: gaps in year range
    if years:
        full_range = set(range(min(years), max(years) + 1))
        missing_years = sorted(full_range - set(years))
    else:
        missing_years = []

    analytics = {
        "job_id": job_id,
        "yearly_stats": yearly_stats,
        "overall_loss_ratio": round(overall_loss_ratio, 6) if overall_loss_ratio is not None else None,
        "frequency_trend": round(frequency_trend, 6) if frequency_trend is not None else None,
        "severity_trend": round(severity_trend, 6) if severity_trend is not None else None,
        "avg_days_to_close": round(avg_days, 1) if avg_days is not None else None,
        "total_open_reserves": round(total_open_reserves, 2),
        "large_loss_ratio": round(large_loss_ratio, 6) if large_loss_ratio is not None else None,
        "years_analyzed": years,
        "missing_years": missing_years,
    }

    logger.info("Analytics: %d years, LR=%.2f%% for job %s", len(years), (overall_loss_ratio or 0) * 100, job_id)
    return {**state, "analytics": analytics, "errors": errors, "current_stage": "analytics"}
