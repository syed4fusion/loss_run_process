from __future__ import annotations

from app.pipeline.nodes.analytics import analytics_node


def _claim(
    claim_id: str,
    occurrence_date: str,
    *,
    incurred: str,
    paid: str,
    reserved: str,
    status: str = "closed",
    close_date: str | None = "2024-12-31",
):
    return {
        "claim_id": claim_id,
        "occurrence_date": occurrence_date,
        "close_date": close_date,
        "amount_incurred": incurred,
        "amount_paid": paid,
        "amount_reserved": reserved,
        "status": status,
    }


def test_loss_ratio_and_zero_claim_year_behavior():
    state = {
        "job_id": "j1",
        "claims_array": {
            "policy_periods": [
                {
                    "period": "2023-01-01/2024-01-01",
                    "earned_premium": "100000",
                    "claims": [],
                },
                {
                    "period": "2024-01-01/2025-01-01",
                    "earned_premium": "100000",
                    "claims": [
                        _claim("c1", "2024-02-01", incurred="20000", paid="15000", reserved="5000"),
                    ],
                },
            ]
        },
        "errors": [],
    }

    result = analytics_node(state)["analytics"]
    by_year = {row["year"]: row for row in result["yearly_stats"]}
    assert by_year[2024]["loss_ratio"] == 0.2
    assert 2023 not in by_year  # no claims in year, so year excluded from DF-based stats


def test_frequency_trend_with_3_year_increase_and_missing_years():
    state = {
        "job_id": "j2",
        "claims_array": {
            "policy_periods": [
                {
                    "period": "2019-01-01/2020-01-01",
                    "earned_premium": "1000000",
                    "claims": [_claim("c1", "2019-02-01", incurred="1000", paid="1000", reserved="0")],
                },
                {
                    "period": "2020-01-01/2021-01-01",
                    "earned_premium": "1000000",
                    "claims": [
                        _claim("c2", "2020-02-01", incurred="1000", paid="1000", reserved="0"),
                        _claim("c3", "2020-03-01", incurred="1000", paid="1000", reserved="0"),
                    ],
                },
                {
                    "period": "2022-01-01/2023-01-01",
                    "earned_premium": "1000000",
                    "claims": [
                        _claim("c4", "2022-02-01", incurred="1000", paid="1000", reserved="0"),
                        _claim("c5", "2022-03-01", incurred="1000", paid="1000", reserved="0"),
                        _claim("c6", "2022-04-01", incurred="1000", paid="1000", reserved="0"),
                    ],
                },
            ]
        },
        "errors": [],
    }

    result = analytics_node(state)["analytics"]
    assert result["frequency_trend"] is not None
    assert result["frequency_trend"] > 0
    assert result["missing_years"] == [2021]


def test_null_premium_year_skips_frequency_division():
    state = {
        "job_id": "j3",
        "claims_array": {
            "policy_periods": [
                {
                    "period": "2024-01-01/2025-01-01",
                    "earned_premium": "0",
                    "claims": [_claim("c1", "2024-02-01", incurred="1000", paid="1000", reserved="0")],
                },
            ]
        },
        "errors": [],
    }
    result = analytics_node(state)["analytics"]
    row = result["yearly_stats"][0]
    assert row["loss_ratio"] is None
    assert row["loss_frequency"] is None
