#!/usr/bin/env python3
"""Export CFTC threshold report + grid JSON artifacts to PDF for email."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import markdown
from weasyprint import HTML

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "docs" / "ssi_validation" / "pdf"
ART_DIR = ROOT / "macro_intelligence" / "analysis" / "ssi_validation"
DOC_DIR = ROOT / "docs" / "ssi_validation"


def _latest(directory: Path, pattern: str) -> Path:
    """Newest artifact matching ``pattern``.

    These were pinned to the 4 Aug filenames, so every later run re-exported August's numbers
    under a fresh timestamp -- the export silently disagreed with the grids it was named after.
    """
    matches = sorted(directory.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No file matching {pattern} in {directory}")
    return matches[-1]

CSS = """
@page { size: A4; margin: 18mm 16mm; }
body {
  font-family: "DejaVu Sans", "Liberation Sans", Arial, sans-serif;
  font-size: 10pt;
  line-height: 1.45;
  color: #111;
}
h1 { font-size: 18pt; margin: 0 0 10pt; border-bottom: 2px solid #333; padding-bottom: 6pt; }
h2 { font-size: 13pt; margin: 16pt 0 8pt; color: #222; }
h3 { font-size: 11pt; margin: 12pt 0 6pt; }
p, li { margin: 4pt 0; }
hr { border: none; border-top: 1px solid #ccc; margin: 12pt 0; }
table {
  border-collapse: collapse;
  width: 100%;
  margin: 8pt 0 12pt;
  font-size: 8.5pt;
}
th, td {
  border: 1px solid #bbb;
  padding: 4pt 5pt;
  text-align: left;
  vertical-align: top;
}
th { background: #f0f0f0; font-weight: 600; }
tr:nth-child(even) td { background: #fafafa; }
code, pre {
  font-family: "DejaVu Sans Mono", monospace;
  font-size: 8pt;
}
pre {
  background: #f5f5f5;
  border: 1px solid #ddd;
  padding: 8pt;
  white-space: pre-wrap;
  word-break: break-all;
}
.meta { color: #444; font-size: 9pt; margin-bottom: 12pt; }
.small { font-size: 8pt; color: #555; }
"""


def md_to_pdf(md_path: Path, pdf_path: Path, title: str) -> None:
    text = md_path.read_text(encoding="utf-8")
    html_body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "nl2br"],
    )
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>{CSS}</style></head>
<body>{html_body}</body></html>"""
    HTML(string=html, base_url=str(md_path.parent)).write_pdf(str(pdf_path))


def _metric(row: dict, horizon: str, field: str) -> str:
    val = row.get("metrics", {}).get(horizon, {}).get(field)
    if val is None:
        return "—"
    if field in ("avg", "median", "worst"):
        return f"{val:.4f}"
    if field == "win_pct":
        return f"{val:.2f}"
    if field == "sharpe":
        return f"{val:.4f}"
    return str(val)


def squeeze_rows_html(rows: list[dict]) -> str:
    sorted_rows = sorted(rows, key=lambda r: (r["fm_max"], r["rm_min"]))
    body = []
    for r in sorted_rows:
        body.append(
            "<tr>"
            f"<td>{r['fm_max']}</td><td>{r['rm_min']}</td><td>{r['n']}</td>"
            f"<td>{_metric(r, '4w', 'avg')}</td><td>{_metric(r, '4w', 'win_pct')}</td>"
            f"<td>{_metric(r, '4w', 'sharpe')}</td>"
            f"<td>{_metric(r, '8w', 'avg')}</td><td>{_metric(r, '8w', 'win_pct')}</td>"
            f"<td>{_metric(r, '8w', 'sharpe')}</td>"
            f"<td>{_metric(r, '12w', 'avg')}</td><td>{_metric(r, '12w', 'win_pct')}</td>"
            f"<td>{_metric(r, '12w', 'sharpe')}</td>"
            "</tr>"
        )
    return "\n".join(body)


def liq_rows_html(rows: list[dict]) -> str:
    sorted_rows = sorted(rows, key=lambda r: (r["rm_max"], r["fm_min"]))
    body = []
    for r in sorted_rows:
        body.append(
            "<tr>"
            f"<td>{r['rm_max']}</td><td>{r['fm_min']}</td><td>{r['n']}</td>"
            f"<td>{_metric(r, '4w', 'avg')}</td><td>{_metric(r, '4w', 'win_pct')}</td>"
            f"<td>{_metric(r, '4w', 'sharpe')}</td>"
            f"<td>{_metric(r, '8w', 'avg')}</td><td>{_metric(r, '8w', 'win_pct')}</td>"
            f"<td>{_metric(r, '8w', 'sharpe')}</td>"
            f"<td>{_metric(r, '12w', 'avg')}</td><td>{_metric(r, '12w', 'win_pct')}</td>"
            f"<td>{_metric(r, '12w', 'sharpe')}</td>"
            "</tr>"
        )
    return "\n".join(body)


def grid_json_to_pdf(json_path: Path, pdf_path: Path, *, kind: str) -> None:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    rows = data["rows"]
    test_id = data.get("test_id", json_path.stem)

    if kind == "squeeze":
        title = f"CFTC SQUEEZE Grid — {json_path.stem}"
        subtitle = "Condition: FM pctile &lt; FM_max AND RM pctile &gt; RM_min (same week)"
        header = (
            "<tr><th>FM &lt;</th><th>RM &gt;</th><th>n</th>"
            "<th>4w avg %</th><th>4w win %</th><th>4w Sharpe</th>"
            "<th>8w avg %</th><th>8w win %</th><th>8w Sharpe</th>"
            "<th>12w avg %</th><th>12w win %</th><th>12w Sharpe</th></tr>"
        )
        tbody = squeeze_rows_html(rows)
        note = "SQUEEZE 12w win % = share of episodes with positive 12w SPX return."
    else:
        title = f"CFTC LIQUIDITY EXIT Grid — {json_path.stem}"
        subtitle = "Condition: RM pctile &lt; RM_max AND FM pctile &gt; FM_min (same week)"
        header = (
            "<tr><th>RM &lt;</th><th>FM &gt;</th><th>n</th>"
            "<th>4w avg %</th><th>4w down %</th><th>4w Sharpe</th>"
            "<th>8w avg %</th><th>8w down %</th><th>8w Sharpe</th>"
            "<th>12w avg %</th><th>12w down %</th><th>12w Sharpe</th></tr>"
        )
        tbody = liq_rows_html(rows)
        note = "LIQUIDITY EXIT win % column = share of episodes with negative SPX return at that horizon."

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>{CSS}</style></head>
<body>
<h1>{title}</h1>
<p class="meta">Test ID: {test_id} · Source: {json_path.name} · Rows: {len(rows)}</p>
<p class="meta">{subtitle}</p>
<p class="small">{note}</p>
<table>
<thead>{header}</thead>
<tbody>
{tbody}
</tbody>
</table>
</body></html>"""
    HTML(string=html).write_pdf(str(pdf_path))


def main() -> None:
    parser = argparse.ArgumentParser(description="Export CFTC threshold artifacts to PDF")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    report_md = _latest(DOC_DIR, "CFTC_PATTERN_THRESHOLD_REPORT_FOR_ROHIT_*.md")
    squeeze_json = _latest(ART_DIR, "03_squeeze_grid_2*.json")
    liq_json = _latest(ART_DIR, "04_liquidity_exit_grid_2*.json")

    report_pdf = out / f"{report_md.stem}.pdf"
    squeeze_pdf = out / f"{squeeze_json.stem}.pdf"
    liq_pdf = out / f"{liq_json.stem}.pdf"

    md_to_pdf(report_md, report_pdf, "CFTC Pattern Threshold Report")
    grid_json_to_pdf(squeeze_json, squeeze_pdf, kind="squeeze")
    grid_json_to_pdf(liq_json, liq_pdf, kind="liquidity")

    print(f"Wrote {report_pdf}")
    print(f"Wrote {squeeze_pdf}")
    print(f"Wrote {liq_pdf}")


if __name__ == "__main__":
    main()
