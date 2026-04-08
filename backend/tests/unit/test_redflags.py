from datetime import date, timedelta

from app.pipeline.nodes.redflags import (
    rule_catastrophic_loss,
    rule_deteriorating_frequency,
    rule_high_open_reserve_ratio,
    rule_large_single_loss,
    rule_litigation_indicator,
    rule_missing_years,
    rule_open_claim_growing_reserve,
    rule_pattern_concentration,
    rule_recent_claims,
)
from app.schemas.redflags import RedFlagSeverity


def _claim(
    claim_id: str,
    *,
    incurred: str = "0",
    reserved: str = "0",
    status: str = "closed",
    claim_type: str = "slip_fall",
    litigation: bool = False,
    occurrence_date: str = "2024-01-01",
):
    return {
        "claim_id": claim_id,
        "amount_incurred": incurred,
        "amount_reserved": reserved,
        "status": status,
        "claim_type": claim_type,
        "litigation_flag": litigation,
        "occurrence_date": occurrence_date,
    }


def test_rule_1_large_single_loss_boundary():
    claims = [
        _claim("c-1", incurred="25000"),
        _claim("c-2", incurred="25000.01"),
    ]
    flags = rule_large_single_loss(claims)
    assert len(flags) == 1
    assert flags[0].triggered_by == "claim:c-2"
    assert flags[0].severity == RedFlagSeverity.WARNING


def test_rule_2_catastrophic_loss_and_loss_ratio():
    flags = rule_catastrophic_loss(
        [_claim("c-1", incurred="100000"), _claim("c-2", incurred="100000.01")],
        [{"year": 2024, "loss_ratio": "0.85"}, {"year": 2025, "loss_ratio": "0.850001"}],
    )
    assert len(flags) == 2
    assert all(flag.severity == RedFlagSeverity.CRITICAL for flag in flags)


def test_rule_3_deteriorating_frequency_boundary():
    no_flag = rule_deteriorating_frequency(
        [
            {"year": 2022, "loss_frequency": "1.00"},
            {"year": 2023, "loss_frequency": "1.20"},  # exactly 20%: no trigger
            {"year": 2024, "loss_frequency": "1.440000"},  # exactly 20%: no trigger
        ]
    )
    assert no_flag is None

    yes_flag = rule_deteriorating_frequency(
        [
            {"year": 2022, "loss_frequency": "1.00"},
            {"year": 2023, "loss_frequency": "1.2001"},   # > 20%
            {"year": 2024, "loss_frequency": "1.4403"},   # > 20% over prior
        ]
    )
    assert yes_flag is not None
    assert yes_flag.severity == RedFlagSeverity.WARNING


def test_rule_4_open_claim_growing_reserve():
    raw_extractions = [
        {
            "carrier_code": "ABC",
            "policy_period_start": "2023-01-01",
            "claims": [{"claim_number": "123", "amount_reserved": "1000", "status": "open"}],
        },
        {
            "carrier_code": "ABC",
            "policy_period_start": "2024-01-01",
            "claims": [{"claim_number": "123", "amount_reserved": "1300", "status": "open"}],
        },
    ]
    flags = rule_open_claim_growing_reserve(raw_extractions)
    assert len(flags) == 1
    assert flags[0].flag_type == "open_claim_growing_reserve"


def test_rule_5_litigation_indicator():
    flags = rule_litigation_indicator([_claim("c-1", litigation=True), _claim("c-2", litigation=False)])
    assert len(flags) == 1
    assert flags[0].triggered_by == "claim:c-1"


def test_rule_6_pattern_concentration():
    flags = rule_pattern_concentration(
        [
            _claim("c-1", claim_type="rear-end collision"),
            _claim("c-2", claim_type="rear-end collision"),
            _claim("c-3", claim_type="rear-end collision"),
            _claim("c-4", claim_type="rear-end collision"),
        ]
    )
    assert len(flags) == 1
    assert flags[0].flag_type == "pattern_concentration"


def test_rule_7_recent_claims():
    today = date(2026, 4, 8)
    recent_day = (today - timedelta(days=90)).isoformat()
    old_day = (today - timedelta(days=91)).isoformat()
    flags = rule_recent_claims(
        [_claim("c-1", occurrence_date=recent_day), _claim("c-2", occurrence_date=old_day)],
        today=today,
    )
    assert len(flags) == 1
    assert flags[0].triggered_by == "claim:c-1"
    assert flags[0].severity == RedFlagSeverity.INFO


def test_rule_8_missing_years():
    assert rule_missing_years([]) is None
    flag = rule_missing_years([2021])
    assert flag is not None
    assert flag.flag_type == "missing_years"


def test_rule_9_high_open_reserve_ratio_boundary():
    no_flag = rule_high_open_reserve_ratio(
        {
            "total_open_reserves": "300",
            "yearly_stats": [{"total_incurred": "1000"}],
        }
    )
    assert no_flag is None

    flag = rule_high_open_reserve_ratio(
        {
            "total_open_reserves": "300.01",
            "yearly_stats": [{"total_incurred": "1000"}],
        }
    )
    assert flag is not None
    assert flag.flag_type == "high_open_reserve_ratio"
