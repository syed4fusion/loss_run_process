from __future__ import annotations

import base64
import io
from collections import Counter

import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")

PALETTE = {
    "primary": "#0b3b66",
    "secondary": "#1c6aa8",
    "accent": "#3f95d2",
    "danger_line": "#b42318",
}


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def loss_ratio_bar_chart(yearly_stats: list[dict]) -> str:
    years = [str(s["year"]) for s in yearly_stats]
    vals = [float(s.get("loss_ratio") or 0.0) * 100 for s in yearly_stats]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(years, vals, color=PALETTE["primary"])
    ax.axhline(65, color=PALETTE["danger_line"], linestyle="--", linewidth=1.5)
    ax.set_title("Loss Ratio by Year")
    ax.set_xlabel("Policy Year")
    ax.set_ylabel("Loss Ratio (%)")
    return _fig_to_b64(fig)


def frequency_trend_chart(yearly_stats: list[dict]) -> str:
    years = [str(s["year"]) for s in yearly_stats]
    claim_counts = [int(s.get("claim_count") or 0) for s in yearly_stats]
    frequencies = [float(s.get("loss_frequency") or 0.0) for s in yearly_stats]
    fig, ax1 = plt.subplots(figsize=(8, 4))
    ax1.plot(years, claim_counts, marker="o", color=PALETTE["secondary"], label="Claim Count")
    ax1.set_ylabel("Claim Count", color=PALETTE["secondary"])
    ax2 = ax1.twinx()
    ax2.plot(years, frequencies, marker="o", color=PALETTE["accent"], label="Frequency")
    ax2.set_ylabel("Loss Frequency", color=PALETTE["accent"])
    ax1.set_xlabel("Policy Year")
    ax1.set_title("Frequency Trend")
    return _fig_to_b64(fig)


def severity_trend_chart(yearly_stats: list[dict]) -> str:
    years = [str(s["year"]) for s in yearly_stats]
    severity = [float(s.get("loss_severity") or 0.0) for s in yearly_stats]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(years, severity, marker="o", color=PALETTE["primary"])
    ax.set_title("Severity Trend")
    ax.set_xlabel("Policy Year")
    ax.set_ylabel("Average Severity")
    return _fig_to_b64(fig)


def claims_by_type_pie(claims_array: dict) -> str:
    counts = Counter()
    for period in claims_array.get("policy_periods", []):
        for claim in period.get("claims", []):
            label = str(claim.get("claim_type", "unknown")).strip() or "unknown"
            counts[label] += 1
    if not counts:
        counts["no_claims"] = 1
    labels = list(counts.keys())
    values = list(counts.values())
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie(values, labels=labels, autopct="%1.0f%%", startangle=90)
    ax.set_title("Claim Type Distribution")
    return _fig_to_b64(fig)


def generate_all_charts(*, claims_array: dict, analytics: dict) -> dict[str, str]:
    yearly_stats = analytics.get("yearly_stats", [])
    return {
        "loss_ratio_bar_chart": loss_ratio_bar_chart(yearly_stats),
        "frequency_trend_chart": frequency_trend_chart(yearly_stats),
        "severity_trend_chart": severity_trend_chart(yearly_stats),
        "claims_by_type_pie": claims_by_type_pie(claims_array),
    }
