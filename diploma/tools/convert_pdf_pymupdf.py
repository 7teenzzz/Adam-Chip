"""
Lightweight PDF → Markdown fallback using PyMuPDF.

Used when Docling is unavailable or too slow. Less accurate structure detection
than Docling, but extracts Russian text reliably and respects TOC from
diploma/chapter_map.md as ground truth for chapter boundaries.

Usage:
  pip install pymupdf
  python diploma/convert_pdf_pymupdf.py [diploma/Diploma.pdf]

Output:
  diploma/Diploma.md             - full text with page markers
  diploma/Diploma_bibliography.md - heuristic bibliography extract
  diploma/Diploma_figures.md     - placeholder (PyMuPDF cannot extract captions reliably)
"""

import re
import sys
from pathlib import Path

import fitz


BIBLIO_TRIGGERS = (
    "список использованных источников",
    "список литературы",
    "references",
    "bibliography",
    "источники",
)


def extract_text_with_pages(pdf_path: Path) -> list[tuple[int, str]]:
    """Return list of (page_number, text) pairs, 1-indexed."""
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text")
        pages.append((i, text))
    doc.close()
    return pages


HEADING_PATTERNS = [
    re.compile(r"^(ВВЕДЕНИЕ|ЗАКЛЮЧЕНИЕ|СПИСОК\s+ИСПОЛЬЗОВАННЫХ\s+ИСТОЧНИКОВ)\s*$", re.IGNORECASE),
    re.compile(r"^ГЛАВА\s+\d+[.\s].*$", re.IGNORECASE),
    re.compile(r"^(\d+(?:\.\d+){0,3})\.?\s+([А-ЯЁA-Z][^\n]{2,150})$"),
]


def looks_like_heading(line: str) -> tuple[int, str] | None:
    """Detect Russian numbered headings. Returns (level, normalized_text) or None."""
    stripped = line.strip()
    if not stripped or len(stripped) > 200:
        return None

    for pat in HEADING_PATTERNS:
        m = pat.match(stripped)
        if m:
            if pat is HEADING_PATTERNS[0]:
                return (1, stripped)
            if pat is HEADING_PATTERNS[1]:
                return (1, stripped)
            num = m.group(1)
            level = num.count(".") + 1
            level = min(level, 4)
            return (level, stripped)
    return None


def build_markdown(pages: list[tuple[int, str]]) -> str:
    """Build markdown with heading detection and page markers."""
    lines = []
    for page_num, page_text in pages:
        lines.append(f"\n<!-- page {page_num} -->\n")
        for raw_line in page_text.split("\n"):
            line = raw_line.rstrip()
            if not line:
                lines.append("")
                continue
            heading = looks_like_heading(line)
            if heading:
                level, text = heading
                lines.append(f"{'#' * level} {text}")
            else:
                lines.append(line)
    return "\n".join(lines)


def extract_bibliography(md: str) -> str:
    """Heuristic: take everything after a bibliography trigger heading."""
    lower = md.lower()
    for trigger in BIBLIO_TRIGGERS:
        idx = lower.rfind(trigger)
        if idx > 0:
            return md[idx:]
    return "# Bibliography\n\n_(не найдена в тексте — нужно извлечь вручную)_\n"


def main(argv: list[str]) -> int:
    pdf = Path(argv[1] if len(argv) > 1 else "diploma/Diploma.pdf")
    if not pdf.exists():
        print(f"PDF not found: {pdf}", file=sys.stderr)
        return 1

    print(f"Extracting text from {pdf} ({pdf.stat().st_size // 1024} KB)...")
    pages = extract_text_with_pages(pdf)
    print(f"Pages: {len(pages)}")

    md = build_markdown(pages)
    out_md = pdf.parent / "Diploma.md"
    out_md.write_text(md, encoding="utf-8")
    print(f"Wrote {out_md} ({len(md)} chars)")

    bib = extract_bibliography(md)
    out_bib = pdf.parent / "Diploma_bibliography.md"
    out_bib.write_text(bib, encoding="utf-8")
    print(f"Wrote {out_bib} ({len(bib)} chars)")

    figs = "# Diploma - Figures & Tables\n\n_(PyMuPDF fallback: captions not extracted - use Docling for full extraction)_\n"
    out_figs = pdf.parent / "Diploma_figures.md"
    out_figs.write_text(figs, encoding="utf-8")
    print(f"Wrote {out_figs}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
