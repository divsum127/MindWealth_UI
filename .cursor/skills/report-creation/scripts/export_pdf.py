#!/usr/bin/env python3.12
"""
Export a Markdown report to a styled PDF.

Usage:
    python3.12 export_pdf.py <input.md> [output.pdf]

If output path is omitted, saves to the same directory as the input
with the same base name and a .pdf extension.
"""

import sys
import pathlib

try:
    import markdown
    import weasyprint
except ImportError:
    print("ERROR: Required packages missing. Run:")
    print("  python3.12 -m pip install weasyprint markdown --break-system-packages")
    sys.exit(1)

CSS = """
body {
    font-family: Georgia, serif;
    max-width: 860px;
    margin: 40px auto;
    font-size: 14px;
    line-height: 1.75;
    color: #1a1a1a;
}
h1 {
    font-size: 22px;
    border-bottom: 2px solid #1a3a5c;
    padding-bottom: 8px;
    margin-bottom: 20px;
    color: #0d2137;
}
h2 {
    font-size: 17px;
    margin-top: 32px;
    color: #1a3a5c;
    border-left: 4px solid #1a3a5c;
    padding-left: 10px;
}
h3 {
    font-size: 14px;
    margin-top: 22px;
    color: #333;
}
p { margin: 10px 0; }
table {
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
    font-size: 13px;
}
th {
    background: #1a3a5c;
    color: white;
    padding: 8px 12px;
    text-align: left;
    font-weight: bold;
}
td {
    padding: 7px 12px;
    border-bottom: 1px solid #dde3ea;
}
tr:nth-child(even) { background: #f4f7fb; }
blockquote {
    border-left: 4px solid #aaa;
    margin: 10px 0;
    padding: 4px 14px;
    color: #555;
    font-style: italic;
}
code {
    background: #f0f0f0;
    padding: 1px 4px;
    font-family: monospace;
    font-size: 12px;
}
"""


def export(md_path: pathlib.Path, pdf_path: pathlib.Path) -> None:
    md_text = md_path.read_text(encoding="utf-8")
    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "nl2br"],
    )
    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>{CSS}</style>
</head>
<body>
{html_body}
</body>
</html>"""

    weasyprint.HTML(string=full_html).write_pdf(str(pdf_path))
    size = pdf_path.stat().st_size
    print(f"[OK] PDF exported: {pdf_path}  ({size:,} bytes)")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    md_path = pathlib.Path(sys.argv[1]).resolve()
    if not md_path.exists():
        print(f"ERROR: File not found: {md_path}")
        sys.exit(1)

    if len(sys.argv) >= 3:
        pdf_path = pathlib.Path(sys.argv[2]).resolve()
    else:
        pdf_path = md_path.with_suffix(".pdf")

    export(md_path, pdf_path)


if __name__ == "__main__":
    main()
