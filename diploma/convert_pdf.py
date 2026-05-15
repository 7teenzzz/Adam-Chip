"""
Docling PDF → Markdown конвертер.

Использование:
  pip install docling
  python diploma/convert_pdf.py diploma/Diploma.pdf

Результат:
  diploma/Diploma.md       — полный текст
  diploma/Diploma.json     — DoclingDocument (для отладки структуры)
"""

import sys
from pathlib import Path


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

    md_path = out_dir / "Diploma.md"
    md_path.write_text(doc.export_to_markdown(), encoding="utf-8")
    print(f"Markdown → {md_path}")

    json_path = out_dir / "Diploma.json"
    json_path.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
    print(f"JSON     → {json_path}")

    # Print structure summary
    headings = [
        (item.label, item.text[:80])
        for item in doc.texts
        if hasattr(item, "label") and str(item.label).startswith("section_header")
    ]
    print(f"\nDetected {len(headings)} headings:")
    for label, text in headings[:20]:
        print(f"  [{label}] {text}")
    if len(headings) > 20:
        print(f"  ... and {len(headings) - 20} more")


if __name__ == "__main__":
    repo_root = Path(__file__).parent.parent
    pdf_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else repo_root / "diploma" / "Diploma.pdf"
    convert(pdf_arg, repo_root / "diploma")
