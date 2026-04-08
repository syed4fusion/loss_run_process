from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from jinja2 import Template

HTML_TEMPLATE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    @page { size: A4; margin: 20mm; @bottom-right { content: "Page " counter(page); } }
    body { font-family: Arial, sans-serif; color: #172b4d; font-size: 12px; }
    h1,h2,h3 { color: #0b3b66; margin-bottom: 6px; }
    .muted { color: #6b7280; font-size: 11px; }
    .meta { margin-bottom: 12px; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 12px; }
    th, td { border: 1px solid #d1d5db; padding: 6px; text-align: left; font-size: 11px; }
    th { background: #f3f4f6; }
    .flag-critical { background: #fee2e2; }
    .flag-warning { background: #fef3c7; }
    .flag-info { background: #dcfce7; }
    .chart { margin: 10px 0; }
    .chart img { width: 100%; max-height: 280px; object-fit: contain; border: 1px solid #e5e7eb; }
    footer { position: fixed; bottom: -8mm; left: 0; right: 0; font-size: 10px; color: #6b7280; }
  </style>
</head>
<body>
  <h1>Underwriter Summary</h1>
  <div class="meta">
    <div><b>Insured:</b> {{ insured_name }}</div>
    <div><b>Job ID:</b> {{ job_id }}</div>
    <div><b>Report Date:</b> {{ report_date }}</div>
    <div><b>Generated:</b> {{ generated_ts }}</div>
  </div>

  <h2>Executive Summary</h2>
  <p>{{ summary.executive_summary }}</p>

  <h2>Claims Summary</h2>
  <table>
    <thead>
      <tr><th>Year</th><th>Claim Count</th><th>Incurred</th><th>Premium</th><th>Loss Ratio</th></tr>
    </thead>
    <tbody>
      {% for y in analytics.yearly_stats %}
      <tr>
        <td>{{ y.year }}</td>
        <td>{{ y.claim_count }}</td>
        <td>{{ y.total_incurred }}</td>
        <td>{{ y.earned_premium }}</td>
        <td>{{ y.loss_ratio if y.loss_ratio is not none else "N/A" }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <h2>Charts</h2>
  {% for chart_name, image_b64 in charts.items() %}
  <div class="chart">
    <div><b>{{ chart_name }}</b></div>
    <img src="data:image/png;base64,{{ image_b64 }}" alt="{{ chart_name }}"/>
  </div>
  {% endfor %}

  <h2>Large Loss Detail</h2>
  <p>{{ summary.large_loss_detail }}</p>

  <h2>Open Claim Status</h2>
  <p>{{ summary.open_claim_status }}</p>

  <h2>Red Flag Disclosure</h2>
  <table>
    <thead><tr><th>Type</th><th>Severity</th><th>Narrative</th></tr></thead>
    <tbody>
      {% for f in red_flags.flags %}
      <tr class="flag-{{ f.severity }}">
        <td>{{ f.flag_type }}</td>
        <td>{{ f.severity }}</td>
        <td>{{ f.narrative }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  <p>{{ summary.red_flag_disclosure }}</p>

  <h2>Year-by-Year Analysis</h2>
  <p>{{ summary.year_by_year }}</p>

  <h2>Risk Management Observations</h2>
  <p>{{ summary.risk_management_observations }}</p>

  <footer>{{ summary.disclaimer }}</footer>
</body>
</html>
"""


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _simple_pdf_fallback(text: str) -> bytes:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        lines = ["Underwriter Summary"]
    content_lines = ["BT", "/F1 10 Tf", "50 780 Td", "14 TL"]
    for line in lines[:60]:
        content_lines.append(f"({_escape_pdf_text(line[:110])}) Tj")
        content_lines.append("T*")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("utf-8")

    objs: list[bytes] = []
    objs.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    objs.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    objs.append(
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
    )
    objs.append(b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")
    objs.append(f"5 0 obj << /Length {len(stream)} >> stream\n".encode("utf-8") + stream + b"\nendstream endobj\n")

    output = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objs:
        offsets.append(len(output))
        output += obj
    xref_pos = len(output)
    output += f"xref\n0 {len(offsets)}\n".encode("utf-8")
    output += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        output += f"{off:010d} 00000 n \n".encode("utf-8")
    output += (
        f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode("utf-8")
    )
    return output


def generate_pdf(
    *,
    job_id: str,
    insured_name: str,
    summary_data: dict[str, Any],
    analytics: dict[str, Any],
    red_flags: dict[str, Any],
    charts: dict[str, str],
) -> bytes:
    rendered_html = Template(HTML_TEMPLATE).render(
        job_id=job_id,
        insured_name=insured_name,
        report_date=datetime.now(timezone.utc).date().isoformat(),
        generated_ts=datetime.now(timezone.utc).isoformat(),
        summary=summary_data,
        analytics=analytics,
        red_flags=red_flags,
        charts=charts,
    )
    try:
        from weasyprint import HTML

        return HTML(string=rendered_html).write_pdf()
    except Exception:
        # Fallback for environments without WeasyPrint system libs.
        return _simple_pdf_fallback(rendered_html)
