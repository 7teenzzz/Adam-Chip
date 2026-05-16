"""
Docling PDF → Markdown конвертер с дополнительной экстракцией.

Использование:
  pip install docling
  python diploma/convert_pdf.py [diploma/Diploma.pdf]

Output:
  diploma/Diploma.md             — полный текст (markdown)
  diploma/Diploma.json           — DoclingDocument (для отладки структуры)
  diploma/Diploma_figures.md     — подписи к рисункам и таблицам
  diploma/Diploma_bibliography.md — список использованных источников (эвристика)
"""

import re
import sys
from pathlib import Path


BIBLIO_TRIGGERS = (
    "список использованных источников",
    "список литературы",
    "references",
    "bibliography",
    "источники",
)


def extract_figures(doc) -> str:
    """Walk pictures and tables, dump captions to markdown."""
    lines = ["# Diploma — Figures & Tables", ""]

    pic_count = 0
    for pic in getattr(doc, "pictures", []) or []:
        captions = getattr(pic, "captions", None) or []
        caption_text = ""
        for cap in captions:
            text = getattr(cap, "text", None) or (cap.resolve(doc).text if hasattr(cap, "resolve") else None)
            if text:
                caption_text = text
                break
        pic_count += 1
        lines.append(f"## Figure {pic_count}")
        if caption_text:
            lines.append(caption_text.strip())
        else:
            lines.append("_(no caption extracted)_")
        lines.append("")

    tab_count = 0
    for tab in getattr(doc, "tables", []) or []:
        captions = getattr(tab, "captions", None) or []
        caption_text = ""
        for cap in captions:
            text = getattr(cap, "text", None) or (cap.resolve(doc).text if hasattr(cap, "resolve") else None)
            if text:
                caption_text = text
                break
        tab_count += 1
        lines.append(f"## Table {tab_count}")
        if caption_text:
            lines.append(caption_text.strip())
        else:
            lines.append("_(no caption extracted)_")
        lines.append("")

    lines.insert(2, f"_{pic_count} figures, {tab_count} tables detected._")
    lines.insert(3, "")
    return "\n".join(lines)


def extract_bibliography(md: str) -> str:
    """Heuristic: take everything from biblio trigger to EOF."""
    lower = md.lower()
    idx = -1
    for trigger in BIBLIO_TRIGGERS:
        pos = lower.find(trigger)
        if pos != -1 and (idx == -1 or pos < idx):
            idx = pos
    if idx == -1:
        return "# Diploma — Bibliography\n\n_(no bibliography section detected)_"

    tail = md[idx:]
    return f"# Diploma — Bibliography\n\n{tail.strip()}"


def convert(pdf_path: Path, out_dir: Path) -> None:
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        print("ERROR: docling not installed. Run: pip install docling")
        sys.exit(1)

    if not pdf_path.exists():
        print(f"ERROR: {pdf_path} not found.")
        sys.exit(1)

    print(f"Converting {pdf_path.name} ...")
    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))
    doc = result.document

    md_text = doc.export_to_markdown()
    md_path = out_dir / "Diploma.md"
    md_path.write_text(md_text, encoding="utf-8")
    print(f"Markdown      → {md_path}  ({len(md_text):,} chars)")

    json_path = out_dir / "Diploma.json"
    json_path.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
    print(f"JSON          → {json_path}  ({json_path.stat().st_size:,} bytes)")

    figures_path = out_dir / "Diploma_figures.md"
    figures_path.write_text(extract_figures(doc), encoding="utf-8")
    print(f"Figures       → {figures_path}")

    biblio_path = out_dir / "Diploma_bibliography.md"
    biblio_path.write_text(extract_bibliography(md_text), encoding="utf-8")
    print(f"Bibliography  → {biblio_path}")

    # Structure summary (first 20 detected section headers)
    headings = []
    try:
        for item in doc.texts:
            label = str(getattr(item, "label", "") or "")
            if "section_header" in label or "title" in label:
                text = (getattr(item, "text", "") or "")[:80]
                headings.append((label, text))
    except Exception as e:
        print(f"WARN: structure summary skipped ({e})")

    print(f"\nDetected {len(headings)} section_header items:")
    for label, text in headings[:20]:
        print(f"  [{label}] {text}")
    if len(headings) > 20:
        print(f"  ... and {len(headings) - 20} more")


if __name__ == "__main__":
    repo_root = Path(__file__).parent.parent
    pdf_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else repo_root / "diploma" / "Diploma.pdf"
    convert(pdf_arg, repo_root / "diploma")
